"""``GET /api/catalog`` contract tests (read-only catalog dump).

Mirrors the :mod:`tests.test_api_sse` conventions (ASGI ``client`` fixture,
mock mode) and pins the wire contract the frontend mirror depends on:
camelCase keys, price-ascending deterministic order, `count == len(products)`,
and NO review quotes in the payload (quotes only ever flow through chat).
"""

from __future__ import annotations

import json

import pytest

from app.catalog.loader import load_catalog

pytestmark = pytest.mark.usefixtures("mock_settings")

_PRODUCT_KEYS = {
    "id",
    "name",
    "brand",
    "category",
    "priceUsd",
    "batteryHours",
    "weightG",
    "ancType",
    "reviewScores",
    "multipoint",
    "folding",
    "codecs",
}
_SCORE_KEYS = {"comfort", "anc", "sound", "battery", "value"}


async def test_catalog_returns_200_with_documented_shape(client) -> None:
    response = await client.get("/api/catalog")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body) == {"count", "products"}
    assert body["count"] == 38 == len(body["products"])
    for product in body["products"]:
        assert set(product) == _PRODUCT_KEYS
        assert set(product["reviewScores"]) == _SCORE_KEYS
        assert isinstance(product["multipoint"], bool)
        assert isinstance(product["folding"], bool)
        assert isinstance(product["codecs"], list)
        assert product["priceUsd"] > 0


async def test_catalog_is_sorted_by_price_ascending_and_ids_unique(client) -> None:
    response = await client.get("/api/catalog")
    body = response.json()
    prices = [product["priceUsd"] for product in body["products"]]
    assert prices == sorted(prices)
    ids = [product["id"] for product in body["products"]]
    assert len(ids) == len(set(ids))


async def test_catalog_is_deterministic_across_calls(client) -> None:
    first = (await client.get("/api/catalog")).json()
    second = (await client.get("/api/catalog")).json()
    assert first == second


async def test_catalog_carries_no_review_quotes(client) -> None:
    response = await client.get("/api/catalog")
    raw = response.text
    assert "quotes" not in raw
    assert all("quotes" not in json.dumps(product) for product in response.json()["products"])


async def test_catalog_matches_the_loaded_catalog_and_categories(client) -> None:
    response = await client.get("/api/catalog")
    body = response.json()
    catalog = {product.id: product for product in load_catalog()}
    assert body["count"] == len(catalog)
    assert {product["id"] for product in body["products"]} == set(catalog)

    categories = {product["category"] for product in body["products"]}
    assert categories == {"headphones", "earbuds"}
    assert sum(1 for p in body["products"] if p["category"] == "earbuds") == 10
    assert sum(1 for p in body["products"] if p["category"] == "headphones") == 28

    # Spot-check one wire record against the validated catalog record.
    pebble = next(p for p in body["products"] if p["id"] == "pebble-hush-anc")
    source = catalog["pebble-hush-anc"]
    assert pebble == {
        "id": "pebble-hush-anc",
        "name": source.name,
        "brand": source.brand,
        "category": source.category,
        "priceUsd": source.price_usd,
        "batteryHours": source.battery_hours,
        "weightG": source.weight_g,
        "ancType": str(source.anc_type),
        "reviewScores": source.review_scores.model_dump(),
        "multipoint": source.multipoint,
        "folding": source.folding,
        "codecs": source.codecs,
    }


async def test_catalog_is_plain_json_not_sse(client) -> None:
    """The catalog endpoint is a regular GET — never an event stream."""
    response = await client.get("/api/catalog")
    assert not response.headers["content-type"].startswith("text/event-stream")
    assert "data:" not in response.text
