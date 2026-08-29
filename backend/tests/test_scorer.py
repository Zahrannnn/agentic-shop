"""Unit tests for the pure deterministic scorer (app.ranking.scorer, R6).

Covers: contribution accounting, weight normalization and fallbacks, min-max
behavior (including cost-attribute inversion and the optional ``price`` /
``weight`` / ``anc_type`` attributes), the total tie-break order, byte-level
determinism, the catalog's flights-scenario winners, and absence of side
effects on the input.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.catalog.loader import load_catalog, min_max
from app.catalog.models import ANCType, Product, ReviewScores
from app.ranking.scorer import SCORABLE_ATTRIBUTES, ScoredProduct, score_products

_QUOTES: tuple[str, ...] = (
    "Comfortable for hours.",
    "Noise simply fades.",
    "Sound is balanced.",
    "Battery lasts all week.",
)


def make_product(
    product_id: str,
    *,
    price_usd: float = 100.0,
    battery_hours: float = 20.0,
    weight_g: float = 250.0,
    anc_type: ANCType = ANCType.ACTIVE,
    comfort: float = 4.0,
    anc: float = 4.0,
    sound: float = 4.0,
    battery: float = 4.0,
    value: float = 4.0,
) -> Product:
    """Build a schema-valid ``Product`` with defaults every test can override."""
    return Product(
        id=product_id,
        name=product_id.replace("-", " ").title(),
        brand="Test Brand",
        category="headphones",
        price_usd=price_usd,
        battery_hours=battery_hours,
        weight_g=weight_g,
        anc_type=anc_type,
        driver_mm=40.0,
        codecs=["sbc"],
        multipoint=False,
        folding=False,
        review_scores=ReviewScores(
            comfort=comfort, anc=anc, sound=sound, battery=battery, value=value
        ),
        quotes=list(_QUOTES),
    )


@pytest.fixture
def pair() -> list[Product]:
    """Two contrasting products whose min-max math is hand-computable.

    alpha-one: 10 h battery, $100, 200 g, active ANC, reviews comfort 3.0 /
    anc 4.0 / sound 4.0 / battery 4.0 / value 4.0.
    beta-two: 20 h battery, $200, 400 g, no ANC, reviews comfort 4.0 /
    anc 2.0 / sound 2.0 / battery 2.0 / value 2.0.
    """
    return [
        make_product(
            "alpha-one",
            price_usd=100.0,
            battery_hours=10.0,
            weight_g=200.0,
            anc_type=ANCType.ACTIVE,
            comfort=3.0,
            anc=4.0,
            sound=4.0,
            battery=4.0,
            value=4.0,
        ),
        make_product(
            "beta-two",
            price_usd=200.0,
            battery_hours=20.0,
            weight_g=400.0,
            anc_type=ANCType.NONE,
            comfort=4.0,
            anc=2.0,
            sound=2.0,
            battery=2.0,
            value=2.0,
        ),
    ]


def under_budget(catalog: list[Product], cap: float = 200.0) -> list[Product]:
    """Filter the catalog to products at or under ``cap`` dollars."""
    return [product for product in catalog if product.price_usd <= cap]


# ---------------------------------------------------------------------------
# Basic contracts
# ---------------------------------------------------------------------------


def test_empty_candidates_return_empty_list() -> None:
    """No candidates -> no scored products."""
    assert score_products([], {"anc": 1.0}) == []


def test_single_candidate_is_fully_neutral() -> None:
    """A lone candidate min-maxes to 0.5 on every attribute, so score == 0.5."""
    results = score_products([make_product("solo")], {"anc": 2.0, "price": 1.0})
    assert len(results) == 1
    assert results[0].product_id == "solo"
    assert results[0].rank == 1
    assert results[0].score == pytest.approx(0.5, abs=1e-12)
    assert results[0].contributions["anc"] == pytest.approx(1.0 / 3.0, abs=1e-9)
    assert results[0].contributions["price"] == pytest.approx(1.0 / 6.0, abs=1e-9)


def test_scored_product_is_frozen() -> None:
    """ScoredProduct is an immutable record."""
    item = ScoredProduct(product_id="x", score=0.5, contributions={"anc": 0.5}, rank=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.score = 0.9  # type: ignore[misc]


@pytest.mark.parametrize(
    "weights",
    [
        {"battery": 0.1, "comfort": 0.2, "anc": 0.4, "sound": 0.2, "value": 0.1},
        {"anc": 2.0, "comfort": 1.0},
        {"anc": 1.0},
        {},
        {"price": 1.0},
        {"weight": 0.6, "price": 0.4},
        {"anc_type": 1.0},
        {"anc": 3.0, "price": 1.0, "anc_type": 2.0, "weight": 0.5},
    ],
)
def test_contributions_sum_to_score_over_fixtures(
    pair: list[Product], weights: dict[str, float]
) -> None:
    """Contributions add up to the score for hand-built sets (within 1e-9)."""
    for result in score_products(pair, weights):
        assert sum(result.contributions.values()) == pytest.approx(result.score, abs=1e-9)
        assert 0.0 <= result.score <= 1.0


@pytest.mark.parametrize(
    "weights",
    [
        {"battery": 0.1, "comfort": 0.2, "anc": 0.4, "sound": 0.2, "value": 0.1},
        {"anc": 2.0, "comfort": 1.0},
        {"anc": 1.0},
        {},
        {"price": 1.0},
        {"weight": 0.6, "price": 0.4},
        {"anc_type": 1.0},
        {"anc": 3.0, "price": 1.0, "anc_type": 2.0, "weight": 0.5},
    ],
)
def test_contributions_sum_to_score_over_catalog(
    weights: dict[str, float],
) -> None:
    """Same accounting holds across a realistic slice of the catalog."""
    candidates = load_catalog()[:10]
    for result in score_products(candidates, weights):
        assert sum(result.contributions.values()) == pytest.approx(result.score, abs=1e-9)


def test_zero_weight_attributes_are_excluded_from_contributions(
    pair: list[Product],
) -> None:
    """Only attributes with weight > 0 appear in the contributions dict."""
    results = score_products(pair, {"anc": 1.0})
    for result in results:
        assert set(result.contributions) == {"anc"}


# ---------------------------------------------------------------------------
# Weight normalization
# ---------------------------------------------------------------------------


def test_proportional_weights_are_equivalent(pair: list[Product]) -> None:
    """{anc: 2, comfort: 1} ranks and scores like {anc: 2/3, comfort: 1/3}."""
    scaled = score_products(pair, {"anc": 2.0, "comfort": 1.0})
    direct = score_products(pair, {"anc": 2.0 / 3.0, "comfort": 1.0 / 3.0})
    assert [item.product_id for item in scaled] == [item.product_id for item in direct]
    for left, right in zip(scaled, direct, strict=True):
        assert left.score == pytest.approx(right.score, abs=1e-12)
        assert left.contributions == pytest.approx(right.contributions, abs=1e-12)


def test_all_zero_weights_fall_back_to_uniform(pair: list[Product]) -> None:
    """All-zero weights behave exactly like missing weights (uniform 0.2)."""
    assert score_products(pair, {}) == score_products(
        pair,
        {"battery": 0.0, "comfort": 0.0, "anc": 0.0, "sound": 0.0, "value": 0.0},
    )


def test_uniform_fallback_matches_explicit_even_weights(pair: list[Product]) -> None:
    """The uniform fallback scores like explicitly even 0.2 weights."""
    fallback = score_products(pair, {})
    explicit = score_products(
        pair, {"battery": 0.2, "comfort": 0.2, "anc": 0.2, "sound": 0.2, "value": 0.2}
    )
    for left, right in zip(fallback, explicit, strict=True):
        assert left.score == pytest.approx(right.score, abs=1e-12)
        assert left.contributions == pytest.approx(right.contributions, abs=1e-12)


def test_uniform_fallback_covers_exactly_the_scorable_attributes(
    pair: list[Product],
) -> None:
    """With no weights, exactly the five scorable attributes are weighted."""
    results = score_products(pair, {})
    for result in results:
        assert set(result.contributions) == set(SCORABLE_ATTRIBUTES)


def test_unknown_weight_keys_are_ignored(pair: list[Product]) -> None:
    """Unrecognized keys neither participate nor disturb known-key weights."""
    with_unknown = score_products(pair, {"anc": 1.0, "wibble": 9.0})
    baseline = score_products(pair, {"anc": 1.0})
    assert with_unknown == baseline


def test_weights_with_only_unknown_keys_fall_back_to_uniform(
    pair: list[Product],
) -> None:
    """A weights dict of only unknown keys behaves like an empty one."""
    assert score_products(pair, {"wibble": 5.0, "wonk": 2.0}) == score_products(pair, {})


def test_negative_and_nonfinite_weights_are_treated_as_zero(
    pair: list[Product],
) -> None:
    """Defensive: negative / NaN / inf weights are dropped, falling back to uniform."""
    assert score_products(pair, {"anc": -2.0}) == score_products(pair, {})
    assert score_products(pair, {"anc": float("inf")}) == score_products(pair, {})
    assert score_products(pair, {"anc": float("nan")}) == score_products(pair, {})


# ---------------------------------------------------------------------------
# Min-max normalization semantics
# ---------------------------------------------------------------------------


def test_exact_two_product_scores_for_review_attributes(pair: list[Product]) -> None:
    """Hand-computed: anc 0.75 weight + comfort 0.25 -> 0.75 vs 0.25."""
    results = score_products(pair, {"anc": 0.75, "comfort": 0.25})
    assert [(item.product_id, item.score) for item in results] == [
        ("alpha-one", 0.75),
        ("beta-two", 0.25),
    ]
    assert [item.rank for item in results] == [1, 2]
    assert results[0].contributions == {"anc": 0.75, "comfort": 0.0}
    assert results[1].contributions == {"anc": 0.0, "comfort": 0.25}


def test_battery_attribute_uses_battery_hours(pair: list[Product]) -> None:
    """battery min-maxes rated hours, not the review score (10 h vs 20 h)."""
    results = score_products(pair, {"battery": 1.0})
    assert [(item.product_id, item.score) for item in results] == [
        ("beta-two", 1.0),
        ("alpha-one", 0.0),
    ]
    assert [item.rank for item in results] == [1, 2]


def test_constant_attribute_scores_neutral() -> None:
    """Identical attribute values across the set normalize to neutral 0.5."""
    twins = [
        make_product("twin-a", battery_hours=15.0),
        make_product("twin-b", battery_hours=15.0),
    ]
    results = score_products(twins, {"battery": 1.0})
    assert [item.score for item in results] == [0.5, 0.5]
    # Equal scores -> lexicographic id tie-break.
    assert [item.product_id for item in results] == ["twin-a", "twin-b"]


def test_price_attribute_is_inverted(pair: list[Product]) -> None:
    """Cheaper candidate gets full contribution when 'price' is weighted."""
    results = score_products(pair, {"price": 1.0})
    by_id = {item.product_id: item for item in results}
    assert by_id["alpha-one"].score == 1.0  # $100 of {$100, $200}
    assert by_id["beta-two"].score == 0.0  # $200 of {$100, $200}
    assert results[0].product_id == "alpha-one"


def test_weight_attribute_is_inverted(pair: list[Product]) -> None:
    """Lighter candidate gets full contribution when 'weight' is weighted."""
    results = score_products(pair, {"weight": 1.0})
    by_id = {item.product_id: item for item in results}
    assert by_id["alpha-one"].score == 1.0  # 200 g of {200 g, 400 g}
    assert by_id["beta-two"].score == 0.0  # 400 g of {200 g, 400 g}
    assert results[0].product_id == "alpha-one"


def test_anc_type_optional_ordinal_attribute(pair: list[Product]) -> None:
    """anc_type ordinals (active 0.66 vs none 0.0) min-max to 1.0 / 0.0."""
    results = score_products(pair, {"anc_type": 1.0})
    by_id = {item.product_id: item for item in results}
    assert by_id["alpha-one"].score == 1.0
    assert by_id["beta-two"].score == 0.0


def test_optional_attributes_normalize_alongside_core_attributes(
    pair: list[Product],
) -> None:
    """Mixed core + optional weights split mass proportionally."""
    results = score_products(pair, {"value": 3.0, "weight": 1.0})
    alpha = next(item for item in results if item.product_id == "alpha-one")
    # value: alpha=1.0 (weight 0.75), weight: alpha=1.0 (weight 0.25).
    assert alpha.score == 1.0
    assert alpha.contributions == {"value": 0.75, "weight": 0.25}


def test_min_max_helper_contract() -> None:
    """The loader's min_max: empty -> [], degenerate -> 0.5s, invert flips."""
    assert min_max([]) == []
    assert min_max([2.0]) == [0.5]
    assert min_max([7.0, 7.0, 7.0]) == [0.5, 0.5, 0.5]
    assert min_max([1.0, 2.0, 3.0]) == [0.0, 0.5, 1.0]
    assert min_max([1.0, 3.0], invert=True) == [1.0, 0.0]


# ---------------------------------------------------------------------------
# Ordering, determinism, side effects
# ---------------------------------------------------------------------------


def test_tie_break_is_lexicographic_by_product_id() -> None:
    """Identical products order by id ascending with ranks 1 and 2."""
    candidates = [
        make_product("zeta-unit", anc=3.5),
        make_product("alpha-unit", anc=3.5),
    ]
    results = score_products(candidates, {"anc": 1.0})
    assert [item.product_id for item in results] == ["alpha-unit", "zeta-unit"]
    assert [item.rank for item in results] == [1, 2]
    assert results[0].score == results[1].score


def test_determinism_is_byte_identical_across_calls() -> None:
    """Same inputs -> repr-identical output (FR-015)."""
    candidates = load_catalog()[:10]
    first = score_products(candidates, {"anc": 1.0})
    second = score_products(candidates, {"anc": 1.0})
    assert repr(first) == repr(second)


def test_output_is_independent_of_input_order() -> None:
    """Reversing the candidate list does not change the scored output."""
    candidates = load_catalog()[:12]
    forward = score_products(candidates, {"comfort": 0.6, "value": 0.4})
    backward = score_products(list(reversed(candidates)), {"comfort": 0.6, "value": 0.4})
    assert repr(forward) == repr(backward)


def test_input_list_is_not_mutated(pair: list[Product]) -> None:
    """Scoring leaves the candidates sequence untouched."""
    before = [product.id for product in pair]
    score_products(pair, {"anc": 0.5, "comfort": 0.5})
    assert [product.id for product in pair] == before


def test_ranks_are_one_through_n_with_sorted_scores() -> None:
    """Ranks run 1..n in output order and scores never increase."""
    results = score_products(load_catalog(), {"anc": 0.4, "battery": 0.3, "value": 0.3})
    assert [item.rank for item in results] == list(range(1, len(results) + 1))
    scores = [item.score for item in results]
    assert scores == sorted(scores, reverse=True)
    assert len({item.product_id for item in results}) == len(results)


def test_scores_stay_within_unit_interval() -> None:
    """A weighted mean of [0, 1] min-max values is itself within [0, 1]."""
    results = score_products(load_catalog(), {"anc": 3.0, "price": 1.0, "weight": 2.0})
    assert all(0.0 <= item.score <= 1.0 for item in results)


# ---------------------------------------------------------------------------
# Realistic flights scenario (R10 winners)
# ---------------------------------------------------------------------------


def test_anc_leading_weights_pick_aurora_hush_pro() -> None:
    """ANC-led weights over <= $200 candidates crown the ANC flagship."""
    candidates = under_budget(load_catalog())
    results = score_products(
        candidates,
        {"anc": 0.45, "comfort": 0.35, "battery": 0.1, "sound": 0.05, "value": 0.05},
    )
    assert results[0].product_id == "aurora-hush-pro"


def test_comfort_leading_weights_pick_cloudline_air() -> None:
    """Comfort-dominated weights over <= $200 candidates crown the lightest pick."""
    candidates = under_budget(load_catalog())
    results = score_products(
        candidates,
        {"comfort": 0.7, "anc": 0.1, "battery": 0.1, "sound": 0.05, "value": 0.05},
    )
    assert results[0].product_id == "cloudline-air"
