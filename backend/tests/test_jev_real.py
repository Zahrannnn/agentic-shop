"""D9 — real-mode Jev measurements (manual; NEVER in CI).

Opt in explicitly::

    cd backend && JEV_MODE=real JEV_API_KEY=... uv run pytest -m jev_real -rA -s

(Or put ``JEV_MODE=real`` + ``JEV_API_KEY`` in your local ``.env``.) The
default suite excludes these via ``addopts = "-m 'not jev_real'"``.

Reports, for a small message battery: per-call latency, p50/p95, and category
agreement between the live Jev judgment and the deterministic regex baseline.
These are observations, not gates — the only hard assertion is that every
call parses (a live service may legitimately disagree with the regex).
"""

from __future__ import annotations

import time

import pytest

from app.llm.intent_rules import extract_category
from app.llm.jev import jev_ask_intent

pytestmark = pytest.mark.jev_real

_MESSAGES = [
    "Best headphones for long flights under $200",
    "earbuds with great battery and noise cancelling",
    "cheap comfortable headphones",
    "I want something nice please",
    "over-ear headphones for the office with strong noise cancellation",
]


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def test_real_intent_latency_and_agreement() -> None:
    from app.config import get_settings, require_jev_config

    settings = get_settings()
    if settings.JEV_MODE != "real":
        pytest.skip("JEV_MODE != real — set JEV_MODE=real and JEV_API_KEY to measure")
    require_jev_config()  # fail fast on a missing key

    latencies: list[float] = []
    rows: list[tuple[str, str | None, str | None, float]] = []
    for message in _MESSAGES:
        start = time.perf_counter()
        answers = jev_ask_intent(message, ["earbuds", "headphones"])
        latencies.append(time.perf_counter() - start)
        baseline = extract_category(message)
        rows.append((message, answers.category, baseline, answers.priorities.get("anc", 0.0)))

    print("\n— Jev real-mode intent measurements —")
    for message, category, baseline, anc in rows:
        agreement = "agree" if category == baseline else "DIFFERS"
        print(
            f"  {agreement:8} jev={str(category):10} regex={str(baseline):10} "
            f"p_anc={anc:.2f}  {message}"
        )
    p50 = _percentile(latencies, 0.5) * 1000
    p95 = _percentile(latencies, 0.95) * 1000
    print(f"  p50={p50:.0f}ms p95={p95:.0f}ms")

    assert len(latencies) == len(_MESSAGES)  # every call parsed and returned
    assert all(isinstance(row[3], float) for row in rows)
