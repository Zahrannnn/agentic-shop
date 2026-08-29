"""Catalog domain models (see specs/001-backend-agent-scaffold/data-model.md).

These Pydantic v2 models are the single validation gate for catalog records:
``app.catalog.loader`` validates every JSON record against :class:`Product`
at load time and fails loudly on the first malformed item (D5, R10).
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

#: Slug pattern for stable product identifiers, e.g. "aurora-hush-pro".
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Codec vocabulary allowed by the data model (subset constraint).
KNOWN_CODECS: frozenset[str] = frozenset({"sbc", "aac", "aptx", "aptx_hd", "ldac", "lc3"})

_MIN_QUOTE_CHARS = 5
_MAX_QUOTE_CHARS = 160


class ANCType(StrEnum):
    """Noise-control category of a headphone.

    Members double as an ordinal scale for the deterministic scorer
    (research.md R6): ``none`` < ``passive`` < ``active`` < ``adaptive``.
    """

    NONE = "none"
    PASSIVE = "passive"
    ACTIVE = "active"
    ADAPTIVE = "adaptive"


class ReviewScores(BaseModel):
    """Pre-scored review attributes (D5), each on a 0.0-5.0 scale, one decimal.

    The research node reads these values verbatim; it never parses quote
    text at runtime (FR-005).
    """

    model_config = ConfigDict(extra="forbid")

    comfort: float = Field(description="Wearing comfort over long sessions.")
    anc: float = Field(description="Noise cancelling / isolation effectiveness.")
    sound: float = Field(description="Sound quality: tuning, detail, staging.")
    battery: float = Field(description="Battery life as experienced by reviewers.")
    value: float = Field(description="Bang for the buck at the asking price.")

    @field_validator("comfort", "anc", "sound", "battery", "value")
    @classmethod
    def _check_score_range(cls, value: float, info: ValidationInfo) -> float:
        """Clamp-check each score into [0.0, 5.0] and normalize to one decimal."""
        if not 0.0 <= value <= 5.0:
            raise ValueError(
                f"review score '{info.field_name}' must be between 0.0 and 5.0, got {value}"
            )
        return round(value, 1)


class Product(BaseModel):
    """One curated catalog item (headphones in the MVP catalog)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable unique slug, e.g. 'aurora-hush-pro'.")
    name: str = Field(description="Human-readable display name.")
    brand: str = Field(description="Brand name.")
    category: str = Field(description="Catalog category; 'headphones' in the MVP.")
    price_usd: float = Field(gt=0, description="Street price in US dollars.")
    battery_hours: float = Field(gt=0, description="Rated battery life in hours.")
    weight_g: float = Field(gt=0, description="Headphone weight in grams.")
    anc_type: ANCType = Field(description="Noise-control category (ordinal for scoring).")
    driver_mm: float = Field(gt=0, description="Driver diameter in millimeters.")
    codecs: list[str] = Field(description="Supported Bluetooth codecs, lowercase.")
    multipoint: bool = Field(description="Supports two-device multipoint pairing.")
    folding: bool = Field(description="Folds or lays flat for transport.")
    review_scores: ReviewScores = Field(description="Pre-scored review attributes.")
    quotes: list[str] = Field(description="4-6 short review quotes.")

    @field_validator("id")
    @classmethod
    def _validate_slug(cls, value: str) -> str:
        """Require a lowercase hyphenated slug so ids are URL- and diff-friendly."""
        cleaned = value.strip()
        if not _SLUG_RE.fullmatch(cleaned):
            raise ValueError(f"'id' must be a lowercase slug like 'aurora-hush-pro', got {value!r}")
        return cleaned

    @field_validator("name", "brand", "category")
    @classmethod
    def _validate_non_empty(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank strings; the MVP category is 'headphones'."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"'{info.field_name}' must be a non-empty string")
        return cleaned

    @field_validator("codecs")
    @classmethod
    def _validate_codecs(cls, value: list[str]) -> list[str]:
        """Normalize codecs to lowercase and restrict them to the known set."""
        cleaned = [codec.strip().lower() for codec in value]
        unknown = [codec for codec in cleaned if codec not in KNOWN_CODECS]
        if unknown:
            allowed = ", ".join(sorted(KNOWN_CODECS))
            raise ValueError(f"unknown codec(s) {unknown}; allowed codecs: {allowed}")
        return cleaned

    @field_validator("quotes")
    @classmethod
    def _validate_quotes(cls, value: list[str]) -> list[str]:
        """Require 4-6 quotes, each 5-160 characters after trimming."""
        if not 4 <= len(value) <= 6:
            raise ValueError(f"'quotes' must contain 4-6 quotes, got {len(value)}")
        cleaned = [quote.strip() for quote in value]
        for quote in cleaned:
            if not _MIN_QUOTE_CHARS <= len(quote) <= _MAX_QUOTE_CHARS:
                raise ValueError(
                    "each quote must be "
                    f"{_MIN_QUOTE_CHARS}-{_MAX_QUOTE_CHARS} characters, "
                    f"got {len(quote)}: {quote!r}"
                )
        return cleaned
