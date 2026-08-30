"""DSL contract tests (US3): fixture corpus + known-bad mutations.

The fixture corpus ``backend/fixtures/ui-plans/*.json`` is the single source
of truth for the plan contract (``contracts/ui-dsl.md``): every fixture must
load through the Pydantic DSL and pass catalog-aware validation with the REAL
catalog ids, and every known-bad mutation must be rejected. Round-trips must
be semantically stable and serialization must emit the camelCase wire format.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import load_catalog
from app.dsl.models import UIPlan
from app.dsl.validate import PlanValidationError, serialize_plan, validate_plan

FIXTURES_DIR: Path = Path(__file__).resolve().parent.parent / "fixtures" / "ui-plans"
FIXTURE_FILES: list[Path] = sorted(FIXTURES_DIR.glob("*.json"))

#: Ids referenced by the fixtures (subset of the real catalog).
FIXTURE_PRODUCT_IDS: list[str] = [
    "aurora-hush-pro",
    "cloudline-air",
    "maple-ridge-comfort-150",
    "skyline-hush",
]


def _catalog_ids() -> set[str]:
    """The REAL catalog id set (import of the loader is the point, US3)."""
    return {product.id for product in load_catalog()}


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _fixture_dict(name: str) -> dict:
    return json.loads(_read_fixture(name))


# ---------------------------------------------------------------------------
# Fixture corpus: all fixtures validate against the real catalog
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda path: path.name)
def test_every_fixture_loads_and_validates_against_real_catalog(path: Path) -> None:
    plan = UIPlan.model_validate_json(path.read_text(encoding="utf-8"))
    validate_plan(plan, _catalog_ids())


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda path: path.name)
def test_camel_case_round_trip_is_semantically_stable(path: Path) -> None:
    original = json.loads(path.read_text(encoding="utf-8"))
    plan = UIPlan.model_validate_json(path.read_text(encoding="utf-8"))
    # model_validate(serialize(plan)) must yield an equal document, and the
    # serialized wire dict must equal the fixture byte-semantically.
    assert serialize_plan(plan) == original
    assert UIPlan.model_validate(serialize_plan(plan)) == plan


def test_fixture_grid_ids_exist_in_real_catalog() -> None:
    """Guard for FIXTURE_PRODUCT_IDS drift: fixtures only reference real ids."""
    assert set(FIXTURE_PRODUCT_IDS) <= _catalog_ids()


def test_serialization_uses_camel_case_aliases() -> None:
    doc = _read_fixture("product-grid-flights.json")
    serialized = serialize_plan(UIPlan.model_validate_json(doc))
    assert "planVersion" in serialized
    assert "sessionId" in serialized
    assert "turnId" in serialized
    assert "productIds" in serialized["root"]["props"]
    assert "plan_version" not in serialized


# ---------------------------------------------------------------------------
# Known-bad mutations: each must be rejected
# ---------------------------------------------------------------------------


def test_unknown_component_type_is_rejected() -> None:
    doc = _fixture_dict("product-grid-flights.json")
    doc["root"]["type"] = "hologram"
    with pytest.raises(ValidationError):
        UIPlan.model_validate(doc)


def test_foreign_product_id_in_props_is_rejected() -> None:
    doc = _fixture_dict("product-grid-flights.json")
    doc["root"]["props"]["productIds"] = ["aurora-hush-pro", "definitely-not-a-product"]
    plan = UIPlan.model_validate(doc)
    with pytest.raises(PlanValidationError):
        validate_plan(plan, _catalog_ids())


def test_seven_grid_product_ids_are_rejected() -> None:
    doc = _fixture_dict("product-grid-flights.json")
    ids = sorted(_catalog_ids())[:7]
    assert len(ids) == 7  # seven REAL ids: the bound, not the catalog, rejects
    doc["root"]["props"]["productIds"] = ids
    with pytest.raises(ValidationError):
        UIPlan.model_validate(doc)


def test_disallowed_action_on_text_block_is_rejected() -> None:
    doc = _fixture_dict("product-grid-flights.json")
    doc["root"] = {
        "type": "text_block",
        "props": {"body": "Assumptions and disclosures."},
        "actions": [{"type": "compare", "label": "Compare", "payload": {}}],
    }
    plan = UIPlan.model_validate(doc)  # structurally fine...
    with pytest.raises(PlanValidationError):
        validate_plan(plan, _catalog_ids())  # ...the catalog rule rejects it


def test_picker_option_without_matching_action_is_rejected() -> None:
    doc = _fixture_dict("preference-picker-category.json")
    doc["root"]["props"]["options"] = ["Headphones", "Laptops", "Something else"]
    plan = UIPlan.model_validate(doc)
    with pytest.raises(PlanValidationError, match="without a matching select_preference"):
        validate_plan(plan, _catalog_ids())


def test_dangling_picker_action_is_rejected() -> None:
    doc = _fixture_dict("preference-picker-category.json")
    doc["root"]["actions"].append(
        {"type": "select_preference", "label": "Laptops", "payload": {"value": "laptops"}}
    )
    plan = UIPlan.model_validate(doc)
    with pytest.raises(PlanValidationError, match="not options"):
        validate_plan(plan, _catalog_ids())


def test_plan_version_2_is_rejected() -> None:
    doc = _fixture_dict("product-grid-flights.json")
    doc["planVersion"] = "2"
    with pytest.raises(ValidationError):
        UIPlan.model_validate(doc)


def test_action_payload_with_unknown_product_is_rejected() -> None:
    doc = _fixture_dict("comparison-two.json")
    doc["root"]["actions"][0]["payload"] = {"productId": "not-in-catalog"}
    plan = UIPlan.model_validate(doc)
    with pytest.raises(PlanValidationError, match="unknown productId"):
        validate_plan(plan, _catalog_ids())


def test_validation_error_lists_every_violation() -> None:
    """One failing plan reports all catalog-rule violations, not just the first."""
    doc = _fixture_dict("product-grid-flights.json")
    doc["root"]["props"]["productIds"] = ["nope-one", "nope-two"]
    doc["root"]["actions"].append({"type": "choose", "label": "Choose", "payload": {}})
    plan = UIPlan.model_validate(doc)
    with pytest.raises(PlanValidationError) as exc_info:
        validate_plan(plan, _catalog_ids())
    message = str(exc_info.value)
    assert "nope-one" in message and "nope-two" in message
    assert "not allowed" in message


# ---------------------------------------------------------------------------
# Bounded amendment (D2 amendment): optional amendsTurnId, cart_view only
# ---------------------------------------------------------------------------


def test_amends_turn_id_is_accepted_on_cart_view_and_serialized() -> None:
    doc = _fixture_dict("cart-one-item.json")
    doc["amendsTurnId"] = 2
    plan = UIPlan.model_validate(doc)
    validate_plan(plan, _catalog_ids())
    assert plan.amends_turn_id == 2
    serialized = serialize_plan(plan)
    assert serialized["amendsTurnId"] == 2
    assert UIPlan.model_validate(serialized) == plan


def test_amends_turn_id_zero_is_rejected() -> None:
    doc = _fixture_dict("cart-one-item.json")
    doc["amendsTurnId"] = 0
    with pytest.raises(ValidationError):
        UIPlan.model_validate(doc)


def test_amends_turn_id_on_non_cart_view_is_rejected() -> None:
    """The bounded amendment is cart_view-only in the MVP (full-replace D2)."""
    doc = _fixture_dict("product-grid-flights.json")
    doc["amendsTurnId"] = 1
    plan = UIPlan.model_validate(doc)  # structurally fine (int >= 1)...
    with pytest.raises(PlanValidationError, match="only allowed on cart_view"):
        validate_plan(plan, _catalog_ids())  # ...the catalog rule rejects it


def test_fixtures_stay_non_amending() -> None:
    """The fixture corpus predates the amendment and carries no amendsTurnId."""
    for path in FIXTURE_FILES:
        assert "amendsTurnId" not in json.loads(path.read_text(encoding="utf-8"))
