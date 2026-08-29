"""US1 API contract tests for ``GET /health`` and ``POST /api/chat`` (D7).

Asserts the wire behavior the future frontend depends on: exact status-stage
order, one validated ``ui_update``, a single ``turn_end`` terminator, the
FR-016 busy guard (real 409 before the stream starts), the additive
``resume`` flag (404 ``unknown_session`` before the busy guard — review
fix), the CORS allowlist (review fix), FastAPI 422 validation, and
byte-level ``event:/data:`` frame formatting.
"""

from __future__ import annotations

import json
import re

import pytest

from app.api.schemas import STAGE_ORDER
from app.catalog.loader import load_catalog
from tests.conftest import collect_sse

pytestmark = pytest.mark.usefixtures("mock_settings")

#: The canonical US1 request (complete request scenario).
FLIGHTS_MESSAGE: str = (
    "Help me find the best headphones for long flights under $200. "
    "Noise cancellation and comfort matter most."
)

_TOP_PICK: str = "aurora-hush-pro"


async def _post_stream(
    client, payload: dict[str, object]
) -> tuple[int, list[tuple[str, dict[str, object]]]]:
    """POST a chat turn and collect its parsed SSE events plus the status."""
    async with client.stream("POST", "/api/chat", json=payload) as response:
        events = await collect_sse(response)
        return response.status_code, events


async def test_health_reports_mock_mode(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "mock"}


async def test_us1_happy_path_frame_order(client) -> None:
    status, events = await _post_stream(
        client, {"session_id": "us1-happy-path-1", "message": FLIGHTS_MESSAGE}
    )
    assert status == 200
    kinds = [name for name, _data in events]
    statuses = [data["stage"] for name, data in events if name == "status"]

    # Stages: full contract order, no gaps, stream opens with intent_parsed.
    assert statuses == list(STAGE_ORDER)
    assert kinds[0] == "status"

    found_n = [data for name, data in events if name == "status" and data["stage"] == "found_n"]
    assert len(found_n) == 1
    assert found_n[0]["count"] >= 1

    assert kinds.count("message_delta") >= 1
    assert len([1 for name, _ in events if name == "ui_update"]) == 1
    assert "error" not in kinds
    assert kinds[-1] == "turn_end"


async def test_us1_plan_is_validated_grid_within_budget(client) -> None:
    status, events = await _post_stream(
        client, {"session_id": "us1-plan-check-1", "message": FLIGHTS_MESSAGE}
    )
    assert status == 200
    plan = next(data for name, data in events if name == "ui_update")
    assert plan["planVersion"] == "1"
    assert plan["sessionId"] == "us1-plan-check-1"
    assert plan["turnId"] == 1

    root = plan["root"]
    assert root["type"] == "product_grid"
    props = root["props"]
    assert props["ranked"] is True

    catalog = {product.id: product for product in load_catalog()}
    product_ids = props["productIds"]
    assert 1 <= len(product_ids) <= 6
    assert set(product_ids) <= set(catalog)
    assert all(catalog[pid].price_usd <= 200.0 for pid in product_ids)
    assert product_ids[0] == _TOP_PICK

    assert [action["type"] for action in root["actions"]] == [
        "compare",
        "details",
        "add_to_cart",
    ]


async def test_us1_narration_is_grounded_in_top_pick(client) -> None:
    status, events = await _post_stream(
        client, {"session_id": "us1-narration-1", "message": FLIGHTS_MESSAGE}
    )
    assert status == 200
    text = "".join(data["text"] for name, data in events if name == "message_delta")
    assert text
    assert "Aurora Hush Pro" in text


async def test_busy_session_gets_409_and_other_sessions_proceed(client) -> None:
    import app.api.routes as routes

    session_id = "busy-session-01"
    routes._in_flight.add(session_id)  # hold the slot deterministically
    try:
        response = await client.post(
            "/api/chat", json={"session_id": session_id, "message": "hello there"}
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "turn_in_flight"}
    finally:
        routes._in_flight.discard(session_id)

    status, events = await _post_stream(
        client, {"session_id": "busy-other-session", "message": FLIGHTS_MESSAGE}
    )
    assert status == 200
    assert events[-1][0] == "turn_end"


async def test_schema_violating_bodies_return_422(client) -> None:
    for body in (
        {"message": "hi"},  # session_id missing
        {"session_id": "short", "message": "hi"},  # session_id < 8 chars
        {"session_id": "x" * 65, "message": "hi"},  # session_id > 64 chars
        {"session_id": "valid-id-001"},  # neither message nor ui_action
        {"session_id": "valid-id-001", "message": "   "},  # whitespace-only message
    ):
        response = await client.post("/api/chat", json=body)
        assert response.status_code == 422, body


# ---------------------------------------------------------------------------
# Resume flag: additive 404 unknown_session (review fix — restart story)
# ---------------------------------------------------------------------------


async def test_resume_false_fresh_session_proceeds_and_registers(client) -> None:
    """A brand-new session with resume=false always streams and registers."""
    import app.api.routes as routes

    session_id = "resume-fresh-0001"
    status, events = await _post_stream(
        client, {"session_id": session_id, "message": FLIGHTS_MESSAGE, "resume": False}
    )
    assert status == 200
    assert events[-1][0] == "turn_end"
    assert session_id in routes._live_sessions


async def test_resume_true_on_known_session_proceeds(client) -> None:
    """Same session: start without resume, reattach with resume=true."""
    session_id = "resume-cycle-0001"
    status, first_events = await _post_stream(
        client, {"session_id": session_id, "message": FLIGHTS_MESSAGE, "resume": False}
    )
    assert status == 200
    assert first_events[-1][0] == "turn_end"

    status, second_events = await _post_stream(
        client, {"session_id": session_id, "message": "compare the first two", "resume": True}
    )
    assert status == 200
    assert second_events[-1][0] == "turn_end"
    plan = next(data for name, data in second_events if name == "ui_update")
    assert plan["root"]["type"] == "comparison_table"


async def test_resume_true_on_unknown_session_returns_404(client) -> None:
    """resume=true for a session this process never saw -> 404, no turn."""
    import app.api.routes as routes

    session_id = "resume-unkn-0001"
    response = await client.post(
        "/api/chat", json={"session_id": session_id, "message": FLIGHTS_MESSAGE, "resume": True}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "unknown_session"}
    # The 404 fired BEFORE any turn started: nothing registered, nothing busy.
    assert session_id not in routes._live_sessions
    assert session_id not in routes._in_flight

    # The contract's restart story: the client starts fresh WITHOUT the flag.
    status, events = await _post_stream(
        client, {"session_id": session_id, "message": FLIGHTS_MESSAGE, "resume": False}
    )
    assert status == 200
    assert events[-1][0] == "turn_end"


async def test_resume_404_takes_precedence_over_busy_409(client) -> None:
    """Unknown + somehow-in-flight: the 404 check runs before the busy guard."""
    import app.api.routes as routes

    ghost = "ghost-resume-01"
    routes._in_flight.add(ghost)  # busy, but never registered as live
    try:
        response = await client.post(
            "/api/chat", json={"session_id": ghost, "message": "hello there", "resume": True}
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "unknown_session"}

        # Without the flag the same request reaches the busy guard instead.
        response = await client.post(
            "/api/chat", json={"session_id": ghost, "message": "hello there"}
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "turn_in_flight"}
    finally:
        routes._in_flight.discard(ghost)


# ---------------------------------------------------------------------------
# CORS allowlist (review fix): the Next.js frontend is a browser client
# ---------------------------------------------------------------------------


async def test_cors_preflight_allows_configured_origin(client) -> None:
    response = await client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_cors_preflight_rejects_unknown_origin(client) -> None:
    response = await client.options(
        "/api/chat",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 400  # starlette: "Disallowed CORS origin"
    assert "access-control-allow-origin" not in response.headers


async def test_cors_actual_post_from_allowed_origin_works(client) -> None:
    response = await client.post(
        "/api/chat",
        json={"session_id": "cors-post-0001", "message": FLIGHTS_MESSAGE},
        headers={"Origin": "http://127.0.0.1:3000"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


async def test_sse_frames_are_well_formed(client) -> None:
    async with client.stream(
        "POST", "/api/chat", json={"session_id": "raw-frames-001", "message": FLIGHTS_MESSAGE}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = ""
        async for chunk in response.aiter_text():
            raw += chunk

    assert raw.endswith("\n\n")
    frames = raw.split("\n\n")[:-1]
    assert frames
    for frame in frames:
        lines = frame.split("\n")
        assert len(lines) == 2, frame
        assert re.fullmatch(r"event: [a-z_]+", lines[0]) is not None, frame
        assert lines[1].startswith("data: ")
        json.loads(lines[1][len("data: ") :])  # every data line is single-line JSON


# ---------------------------------------------------------------------------
# US4/US5 over SSE: follow-up comparisons and the fail-clean error frame
# ---------------------------------------------------------------------------


async def test_us4_compare_first_two_over_sse(client) -> None:
    """Same session: recommend, then "compare the first two" -> the second
    turn's ui_update is a comparison_table of exactly the first turn's
    top two products, in ranking order."""
    session_id = "us4-sse-compare-01"
    status, first_events = await _post_stream(
        client, {"session_id": session_id, "message": FLIGHTS_MESSAGE}
    )
    assert status == 200
    assert first_events[-1][0] == "turn_end"
    first_plan = next(data for name, data in first_events if name == "ui_update")
    top_two = first_plan["root"]["props"]["productIds"][:2]
    assert top_two == ["aurora-hush-pro", "cloudline-air"]

    status, second_events = await _post_stream(
        client, {"session_id": session_id, "message": "compare the first two"}
    )
    assert status == 200
    kinds = [name for name, _data in second_events]
    assert kinds[-1] == "turn_end"
    assert "error" not in kinds
    assert kinds.count("ui_update") == 1
    plan = next(data for name, data in second_events if name == "ui_update")
    assert plan["turnId"] == 2
    assert plan["root"]["type"] == "comparison_table"
    assert plan["root"]["props"]["productIds"] == top_two
    assert plan["root"]["props"]["attributes"] == [
        "price_usd",
        "battery_hours",
        "weight_g",
        "anc_type",
        "comfort",
    ]
    [(action_type, action_payload)] = [
        (action["type"], action["payload"]) for action in plan["root"]["actions"]
    ]
    assert action_type == "choose"
    assert action_payload == {"productId": top_two[0]}

    text = "".join(data["text"] for name, data in second_events if name == "message_delta")
    assert "side-by-side comparison" in text
    # Wire order: the ui_update frame lands after the prose, before turn_end.
    assert kinds.index("ui_update") > max(
        index for index, name in enumerate(kinds) if name == "message_delta"
    )


async def test_us5_structured_output_fault_yields_single_clean_error_frame(
    client, fake_llm_factory
) -> None:
    """Malformed model output twice -> exactly one clean error frame replaces
    turn_end; no prose, no plan, and no raw model output on the wire."""
    marker = "way-too-loud"
    fake_llm_factory(
        [
            {"schema": "PreferenceWeights", "invalid": {"anc": marker}},
            {"schema": "PreferenceWeights", "invalid": {"anc": marker}},
        ]
    )
    status, events = await _post_stream(
        client, {"session_id": "us5-sse-fault-001", "message": FLIGHTS_MESSAGE}
    )
    assert status == 200
    kinds = [name for name, _data in events]
    statuses = [data["stage"] for name, data in events if name == "status"]
    assert statuses == list(STAGE_ORDER)[:-1]  # the stream dies at ranking
    assert kinds.count("error") == 1
    assert kinds[-1] == "error"  # terminal: replaces turn_end, nothing after
    assert "turn_end" not in kinds
    assert "ui_update" not in kinds
    assert "message_delta" not in kinds
    error = events[-1][1]
    assert error["code"] == "structured_output"
    assert error["message"].startswith("The model returned an invalid response")
    # SC-007: the invalid payload's contents never reach the client.
    assert all(marker not in json.dumps(data) for _name, data in events)
