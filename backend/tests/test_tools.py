"""Tests for ``app.tools.search`` and ``app.tools.research`` (Phase 1).

Layout note for future waves: sections are search, research, and cart, each
kept behind its own banner comment so appends stay trivial.

Everything under test is pure; all tests use the real curated catalog via
``load_catalog()`` (fixture ``catalog``) and the packaged catalog JSON.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from app.catalog.loader import DEFAULT_DATA_PATH, load_catalog
from app.catalog.models import ANCType, Product
from app.tools.cart import (
    MAX_QUANTITY,
    CartItem,
    CartLine,
    CartSummary,
    add_to_cart,
    get_cart,
    remove_from_cart,
    set_quantity,
)
from app.tools.research import (
    ReviewSummary,
    get_product_reviews,
    get_product_specs,
    summarize_candidates,
)
from app.tools.search import SearchFilters, relax_filters, search_products


@pytest.fixture
def catalog() -> list[Product]:
    """The real curated catalog (28 validated products, sorted by id)."""
    return load_catalog()


# ---------------------------------------------------------------------------
# search — app.tools.search
# ---------------------------------------------------------------------------


class TestSearchProducts:
    """``search_products``: pure filtering, catalog order, inclusive bounds."""

    def test_filter_by_category(self, catalog: list[Product]) -> None:
        results = search_products(catalog, SearchFilters(category="headphones"))
        assert [p.id for p in results] == [p.id for p in catalog]

    def test_category_is_case_insensitive_and_stripped(self, catalog: list[Product]) -> None:
        upper = search_products(catalog, SearchFilters(category="HEADPHONES"))
        padded = search_products(catalog, SearchFilters(category="  Headphones "))
        assert [p.id for p in upper] == [p.id for p in catalog]
        assert [p.id for p in padded] == [p.id for p in catalog]

    def test_unknown_category_returns_empty(self, catalog: list[Product]) -> None:
        assert search_products(catalog, SearchFilters(category="speakers")) == []

    def test_max_price_is_inclusive(self, catalog: list[Product]) -> None:
        results = search_products(catalog, SearchFilters(max_price=149.0))
        ids = {p.id for p in results}
        # Both $149.00 products sit exactly on the boundary and must be kept.
        assert "maple-ridge-comfort-150" in ids
        assert "vesper-mini-anc" in ids
        assert all(p.price_usd <= 149.0 for p in results)
        # Just below the boundary the two boundary products drop out.
        below = {p.id for p in search_products(catalog, SearchFilters(max_price=148.99))}
        assert "maple-ridge-comfort-150" not in below
        assert "vesper-mini-anc" not in below

    def test_min_battery_hours_is_inclusive(self, catalog: list[Product]) -> None:
        results = search_products(catalog, SearchFilters(min_battery_hours=60.0))
        # onward-travel-max is rated at exactly 60.0 h and must be kept.
        assert {p.id for p in results} == {"onward-travel-max", "volt-enduro-70"}

    def test_require_anc_excludes_anc_type_none(self, catalog: list[Product]) -> None:
        results = search_products(catalog, SearchFilters(require_anc=True))
        assert len(results) == 22  # 28 catalog items minus the 6 with anc_type "none"
        assert all(p.anc_type != ANCType.NONE for p in results)
        # "passive" counts as noise control (require_anc := anc_type != none).
        passive_ids = {p.id for p in results if p.anc_type == ANCType.PASSIVE}
        assert passive_ids == {"coralfield-flex", "harbor-lite-anc", "velvetone-jazz-1"}

    def test_default_filters_keep_everything(self, catalog: list[Product]) -> None:
        results = search_products(catalog, SearchFilters())
        assert len(results) == 28

    def test_codecs_single(self, catalog: list[Product]) -> None:
        results = search_products(catalog, SearchFilters(codecs=("ldac",)))
        assert {p.id for p in results} == {
            "bravenorth-arc",
            "cascadia-reference",
            "cobalt-harbor-anc",
            "heliostudio-pro-400",
            "lumen-acoustics-air-3",
            "meridian-sound-lux",
            "obsidian-audio-flag-8",
            "summit-labs-aether",
        }

    def test_codecs_multiple_require_all_requested(self, catalog: list[Product]) -> None:
        results = search_products(catalog, SearchFilters(codecs=("aptx", "ldac")))
        assert {p.id for p in results} == {
            "bravenorth-arc",
            "cobalt-harbor-anc",
            "heliostudio-pro-400",
            "lumen-acoustics-air-3",
            "obsidian-audio-flag-8",
            "summit-labs-aether",
        }

    def test_codecs_matching_is_case_insensitive(self, catalog: list[Product]) -> None:
        upper = search_products(catalog, SearchFilters(codecs=("LDAC",)))
        lower = search_products(catalog, SearchFilters(codecs=("ldac",)))
        assert [p.id for p in upper] == [p.id for p in lower]

    def test_multipoint_flag(self, catalog: list[Product]) -> None:
        yes = search_products(catalog, SearchFilters(multipoint=True))
        no = search_products(catalog, SearchFilters(multipoint=False))
        assert all(p.multipoint for p in yes)
        assert not any(p.multipoint for p in no)
        assert len(yes) + len(no) == 28

    def test_folding_flag(self, catalog: list[Product]) -> None:
        yes = search_products(catalog, SearchFilters(folding=True))
        no = search_products(catalog, SearchFilters(folding=False))
        assert all(p.folding for p in yes)
        assert not any(p.folding for p in no)
        assert len(yes) + len(no) == 28

    def test_combined_filters(self, catalog: list[Product]) -> None:
        filters = SearchFilters(
            category="Headphones",
            max_price=150.0,
            min_battery_hours=30.0,
            require_anc=True,
        )
        results = search_products(catalog, filters)
        assert [p.id for p in results] == [
            "cloudline-air",
            "coralfield-flex",
            "emberwave-mid",
            "maple-ridge-comfort-150",
            "skyline-hush",
        ]

    def test_no_match_returns_empty_list(self, catalog: list[Product]) -> None:
        assert search_products(catalog, SearchFilters(max_price=10.0)) == []

    def test_catalog_order_is_preserved(self, catalog: list[Product]) -> None:
        results = search_products(catalog, SearchFilters(max_price=100.0))
        expected = [p.id for p in catalog if p.price_usd <= 100.0]
        assert [p.id for p in results] == expected

    def test_search_filters_are_frozen(self) -> None:
        filters = SearchFilters(max_price=100.0)
        with pytest.raises(FrozenInstanceError):
            filters.max_price = 200.0


class TestRelaxFilters:
    """``relax_filters``: deterministic, cumulative, non-mutating progression."""

    def test_progression_is_deterministic_and_cumulative(self) -> None:
        filters = SearchFilters(
            max_price=150.0,
            min_battery_hours=30.0,
            require_anc=True,
            codecs=("ldac",),
            multipoint=True,
        )
        relaxed = relax_filters(filters)
        assert relaxed == relax_filters(filters)  # deterministic: same input, same list
        # Attribute drops in fixed order: codecs -> require_anc -> min_battery ->
        # multipoint (folding is unset, so it contributes no step).
        assert relaxed[0] == SearchFilters(
            max_price=150.0, min_battery_hours=30.0, require_anc=True, multipoint=True
        )
        assert relaxed[1] == SearchFilters(max_price=150.0, min_battery_hours=30.0, multipoint=True)
        assert relaxed[2] == SearchFilters(max_price=150.0, multipoint=True)
        assert relaxed[3] == SearchFilters(max_price=150.0)
        # Then price: +$50, +$100, and finally the cap is removed entirely.
        assert relaxed[4] == SearchFilters(max_price=200.0)
        assert relaxed[5] == SearchFilters(max_price=250.0)
        assert relaxed[6] == SearchFilters(max_price=None)
        assert len(relaxed) == 7

    def test_original_filter_is_never_mutated(self) -> None:
        filters = SearchFilters(max_price=100.0, codecs=("aptx",), multipoint=False)
        relaxed = relax_filters(filters)
        assert filters == SearchFilters(max_price=100.0, codecs=("aptx",), multipoint=False)
        assert all(entry is not filters for entry in relaxed)

    def test_final_relaxation_removes_price_cap(self) -> None:
        relaxed = relax_filters(SearchFilters(max_price=100.0, folding=True))
        assert relaxed[-1].max_price is None
        assert relaxed[-1].folding is None

    def test_absent_constraints_are_skipped(self) -> None:
        # Only a price cap is set: no attribute-drop no-ops, just the price steps.
        relaxed = relax_filters(SearchFilters(max_price=120.0))
        assert relaxed == [
            SearchFilters(max_price=170.0),
            SearchFilters(max_price=220.0),
            SearchFilters(max_price=None),
        ]

    def test_fully_default_filter_has_nothing_to_relax(self) -> None:
        assert relax_filters(SearchFilters()) == []

    def test_results_never_shrink_as_filters_relax(self, catalog: list[Product]) -> None:
        filters = SearchFilters(
            max_price=200.0,
            min_battery_hours=40.0,
            require_anc=True,
            codecs=("aptx",),
        )
        steps = [filters, *relax_filters(filters)]
        result_sets = [{p.id for p in search_products(catalog, step)} for step in steps]
        assert all(result_sets[i] <= result_sets[i + 1] for i in range(len(result_sets) - 1))
        # And the fully relaxed search strictly widens the original result set.
        assert len(result_sets[-1]) > len(result_sets[0])


# ---------------------------------------------------------------------------
# research — app.tools.research
# ---------------------------------------------------------------------------


class TestGetProductSpecs:
    def test_known_id_returns_full_product(self, catalog: list[Product]) -> None:
        expected = next(p for p in catalog if p.id == "aurora-hush-pro")
        specs = get_product_specs(catalog, "aurora-hush-pro")
        assert specs == expected
        assert specs is expected  # the catalog record itself, not a copy
        assert specs is not None
        assert specs.name == "Aurora Hush Pro"
        assert specs.price_usd == 179.0

    def test_unknown_id_returns_none(self, catalog: list[Product]) -> None:
        assert get_product_specs(catalog, "no-such-product") is None


class TestGetProductReviews:
    def test_reviews_match_catalog_json_for_aurora_hush_pro(self, catalog: list[Product]) -> None:
        records = {
            record["id"]: record
            for record in json.loads(DEFAULT_DATA_PATH.read_text(encoding="utf-8"))
        }
        summary = get_product_reviews(catalog, "aurora-hush-pro")
        assert summary is not None
        assert isinstance(summary, ReviewSummary)
        assert summary.product_id == "aurora-hush-pro"
        assert summary.review_scores == records["aurora-hush-pro"]["review_scores"]
        assert list(summary.quotes) == records["aurora-hush-pro"]["quotes"]

    def test_scores_cover_all_five_attributes(self, catalog: list[Product]) -> None:
        summary = get_product_reviews(catalog, "cloudline-air")
        assert summary is not None
        assert set(summary.review_scores) == {"comfort", "anc", "sound", "battery", "value"}

    def test_unknown_id_returns_none(self, catalog: list[Product]) -> None:
        assert get_product_reviews(catalog, "no-such-product") is None

    def test_summary_is_frozen_and_detached_from_catalog(self, catalog: list[Product]) -> None:
        summary = get_product_reviews(catalog, "aurora-hush-pro")
        assert summary is not None
        with pytest.raises(FrozenInstanceError):
            summary.product_id = "tampered"
        # Mutating the copied scores must not leak into the shared catalog.
        summary.review_scores["anc"] = 0.0
        product = get_product_specs(catalog, "aurora-hush-pro")
        assert product is not None
        assert product.review_scores.anc == 4.9


class TestSummarizeCandidates:
    def test_preserves_input_order_and_skips_unknown_ids(self, catalog: list[Product]) -> None:
        summaries = summarize_candidates(
            catalog,
            ["skyline-hush", "ghost-product", "aurora-hush-pro", "another-ghost"],
        )
        assert [s.product_id for s in summaries] == ["skyline-hush", "aurora-hush-pro"]

    def test_all_known_ids(self, catalog: list[Product]) -> None:
        summaries = summarize_candidates(catalog, ["volt-enduro-70", "cloudline-air"])
        assert [s.product_id for s in summaries] == ["volt-enduro-70", "cloudline-air"]

    def test_empty_input_yields_empty_list(self, catalog: list[Product]) -> None:
        assert summarize_candidates(catalog, []) == []

    def test_all_unknown_ids_yield_empty_list(self, catalog: list[Product]) -> None:
        assert summarize_candidates(catalog, ["ghost-1", "ghost-2"]) == []


# ---------------------------------------------------------------------------
# ## cart — app.tools.cart
# ---------------------------------------------------------------------------


class TestAddToCart:
    """``add_to_cart``: new lists only, merge-then-clamp, strict quantity."""

    def test_add_to_empty_cart_creates_new_line(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro", 2)
        assert cart == [{"product_id": "aurora-hush-pro", "quantity": 2}]

    def test_add_merges_into_existing_line_and_preserves_position(
        self, catalog: list[Product]
    ) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro")
        cart = add_to_cart(cart, catalog, "maple-ridge-comfort-150")
        cart = add_to_cart(cart, catalog, "aurora-hush-pro")
        assert cart == [
            {"product_id": "aurora-hush-pro", "quantity": 2},
            {"product_id": "maple-ridge-comfort-150", "quantity": 1},
        ]

    def test_add_clamps_merged_quantity_at_max(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro", 8)
        cart = add_to_cart(cart, catalog, "aurora-hush-pro", 5)
        assert cart == [{"product_id": "aurora-hush-pro", "quantity": MAX_QUANTITY}]

    def test_add_clamps_directly_oversized_quantity(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro", 25)
        assert cart == [{"product_id": "aurora-hush-pro", "quantity": MAX_QUANTITY}]

    def test_add_accepts_integral_float_quantity(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro", 2.0)
        assert cart == [{"product_id": "aurora-hush-pro", "quantity": 2}]

    @pytest.mark.parametrize("bad_quantity", [0, -1, 1.5, True, "2", None])
    def test_add_rejects_invalid_quantity(
        self, catalog: list[Product], bad_quantity: object
    ) -> None:
        with pytest.raises(ValueError, match="quantity"):
            add_to_cart([], catalog, "aurora-hush-pro", bad_quantity)  # type: ignore[arg-type]

    def test_add_unknown_product_raises_key_error(self, catalog: list[Product]) -> None:
        with pytest.raises(KeyError) as excinfo:
            add_to_cart([], catalog, "ghost-product")
        assert excinfo.value.args[0] == "ghost-product"

    def test_add_does_not_mutate_input_cart(self, catalog: list[Product]) -> None:
        cart: list[CartItem] = [CartItem(product_id="aurora-hush-pro", quantity=2)]
        snapshot = [dict(line) for line in cart]
        updated = add_to_cart(cart, catalog, "vesper-mini-anc", 3)
        assert cart == snapshot
        assert updated is not cart
        # Every returned line dict is freshly built, never aliased to the input
        # (the updated cart is one line longer, hence strict=False).
        assert all(new is not old for new, old in zip(updated, cart, strict=False))


class TestRemoveFromCart:
    """``remove_from_cart``: line removal, idempotent for absent valid ids."""

    def test_remove_drops_only_the_target_line(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro", 2)
        cart = add_to_cart(cart, catalog, "maple-ridge-comfort-150")
        cart = remove_from_cart(cart, catalog, "aurora-hush-pro")
        assert cart == [{"product_id": "maple-ridge-comfort-150", "quantity": 1}]

    def test_remove_absent_but_valid_product_is_idempotent(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro")
        again = remove_from_cart(cart, catalog, "vesper-mini-anc")
        assert again == cart
        assert again is not cart

    def test_remove_unknown_product_raises_key_error(self, catalog: list[Product]) -> None:
        with pytest.raises(KeyError) as excinfo:
            remove_from_cart([], catalog, "ghost-product")
        assert excinfo.value.args[0] == "ghost-product"

    def test_remove_does_not_mutate_input_cart(self, catalog: list[Product]) -> None:
        cart: list[CartItem] = [
            CartItem(product_id="aurora-hush-pro", quantity=2),
            CartItem(product_id="maple-ridge-comfort-150", quantity=1),
        ]
        snapshot = [dict(line) for line in cart]
        remove_from_cart(cart, catalog, "aurora-hush-pro")
        assert cart == snapshot


class TestSetQuantity:
    """``set_quantity``: set/clamp/remove semantics on a NEW list."""

    def test_set_quantity_updates_existing_line(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro", 2)
        updated = set_quantity(cart, catalog, "aurora-hush-pro", 7)
        assert updated == [{"product_id": "aurora-hush-pro", "quantity": 7}]

    def test_set_quantity_clamps_to_max(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro", 2)
        updated = set_quantity(cart, catalog, "aurora-hush-pro", 99)
        assert updated == [{"product_id": "aurora-hush-pro", "quantity": MAX_QUANTITY}]

    def test_set_quantity_zero_removes_line(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro", 2)
        cart = add_to_cart(cart, catalog, "maple-ridge-comfort-150")
        updated = set_quantity(cart, catalog, "aurora-hush-pro", 0)
        assert updated == [{"product_id": "maple-ridge-comfort-150", "quantity": 1}]

    def test_set_quantity_zero_on_absent_line_is_idempotent(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro")
        updated = set_quantity(cart, catalog, "vesper-mini-anc", 0)
        assert updated == cart
        assert updated is not cart

    def test_set_quantity_positive_on_absent_line_appends_it(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro")
        updated = set_quantity(cart, catalog, "vesper-mini-anc", 4)
        assert updated == [
            {"product_id": "aurora-hush-pro", "quantity": 1},
            {"product_id": "vesper-mini-anc", "quantity": 4},
        ]

    @pytest.mark.parametrize("bad_quantity", [-1, 1.5, True, "2", None])
    def test_set_quantity_rejects_invalid_quantity(
        self, catalog: list[Product], bad_quantity: object
    ) -> None:
        with pytest.raises(ValueError, match="quantity"):
            set_quantity([], catalog, "aurora-hush-pro", bad_quantity)  # type: ignore[arg-type]

    def test_set_quantity_unknown_product_raises_key_error(self, catalog: list[Product]) -> None:
        with pytest.raises(KeyError) as excinfo:
            set_quantity([], catalog, "ghost-product", 3)
        assert excinfo.value.args[0] == "ghost-product"


class TestGetCart:
    """``get_cart``: catalog-priced totals, cart order preserved, 2 decimals."""

    def test_totals_for_known_product(self, catalog: list[Product]) -> None:
        summary = get_cart([CartItem(product_id="aurora-hush-pro", quantity=2)], catalog)
        assert isinstance(summary, CartSummary)
        assert summary.lines == (CartLine("aurora-hush-pro", 2, 358.0),)
        assert summary.total_usd == 358.0

    def test_multi_line_order_is_preserved_and_totals_sum(self, catalog: list[Product]) -> None:
        cart = add_to_cart([], catalog, "aurora-hush-pro")
        cart = add_to_cart(cart, catalog, "maple-ridge-comfort-150", 2)
        summary = get_cart(cart, catalog)
        assert summary.lines == (
            CartLine("aurora-hush-pro", 1, 179.0),
            CartLine("maple-ridge-comfort-150", 2, 298.0),
        )
        assert summary.total_usd == 477.0

    def test_empty_cart_has_zero_total(self, catalog: list[Product]) -> None:
        summary = get_cart([], catalog)
        assert summary.lines == ()
        assert summary.total_usd == 0.0

    def test_unknown_product_in_cart_is_a_key_error(self, catalog: list[Product]) -> None:
        # A corrupt cart (line referencing a foreign id) is a programming error.
        corrupt: list[CartItem] = [CartItem(product_id="ghost-product", quantity=1)]
        with pytest.raises(KeyError) as excinfo:
            get_cart(corrupt, catalog)
        assert excinfo.value.args[0] == "ghost-product"

    def test_summary_is_frozen(self, catalog: list[Product]) -> None:
        summary = get_cart([], catalog)
        with pytest.raises(FrozenInstanceError):
            summary.total_usd = 1.0  # type: ignore[misc]


class TestCartDeterminism:
    """The cart tools are pure: identical ops must yield identical results."""

    def test_same_operations_produce_identical_results(self, catalog: list[Product]) -> None:
        def run() -> tuple[list[CartItem], CartSummary]:
            cart: list[CartItem] = []
            cart = add_to_cart(cart, catalog, "aurora-hush-pro", 2)
            cart = add_to_cart(cart, catalog, "skyline-hush")
            cart = set_quantity(cart, catalog, "aurora-hush-pro", 1)
            cart = remove_from_cart(cart, catalog, "skyline-hush")
            return cart, get_cart(cart, catalog)

        assert run() == run()

    def test_repeated_calls_on_same_input_are_equal_and_unmutating(
        self, catalog: list[Product]
    ) -> None:
        cart: list[CartItem] = [CartItem(product_id="aurora-hush-pro", quantity=3)]
        assert add_to_cart(cart, catalog, "maple-ridge-comfort-150") == add_to_cart(
            cart, catalog, "maple-ridge-comfort-150"
        )
        assert get_cart(cart, catalog) == get_cart(cart, catalog)
        assert cart == [CartItem(product_id="aurora-hush-pro", quantity=3)]
