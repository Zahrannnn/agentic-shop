"""Structured-output models requested from the LLM by graph nodes.

Every ``call_structured`` call in the graph binds exactly one of these models
(data-model.md "Node structured-output models"). The field sets match the
deterministic mock handlers in ``app.llm.client`` one-to-one, so the whole
pipeline is exercisable keyless and offline (research R5).

The LLM *configures* — it never free-writes products, orders, or plans
(DECISIONS.md D3): weights feed the pure scorer and narration quotes
code-generated highlights. UI plans are assembled entirely by code
(``app.graph.nodes`` + ``app.graph.followups``); the model never chooses plan
structure (architecture-review fix: the PlanSelection call was removed as
dead weight — only its constant title was ever used).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IntentExtraction(BaseModel):
    """What the user stated in THIS message (merged into intent by code)."""

    model_config = ConfigDict(extra="ignore")

    category: str | None = Field(default=None, description="Product category, e.g. 'headphones'.")
    budget_usd: float | None = Field(default=None, description="Stated budget in US dollars.")
    use_case: str | None = Field(
        default=None, description="Free-text use case, e.g. 'long flights'."
    )
    priorities: dict[str, float] = Field(
        default_factory=dict,
        description="Attribute name -> salience in [0, 1] for attributes the user mentioned.",
    )


class PreferenceWeights(BaseModel):
    """One weight per scorable attribute, each in [0, 1].

    Normalized to sum 1 by the pure scorer (research R6) — the model is never
    trusted with sums.
    """

    model_config = ConfigDict(extra="ignore")

    anc: float = Field(default=0.0, ge=0.0, le=1.0, description="Noise cancellation preference.")
    comfort: float = Field(default=0.0, ge=0.0, le=1.0, description="Wearing comfort preference.")
    battery: float = Field(default=0.0, ge=0.0, le=1.0, description="Battery life preference.")
    sound: float = Field(default=0.0, ge=0.0, le=1.0, description="Sound quality preference.")
    value: float = Field(default=0.0, ge=0.0, le=1.0, description="Value-for-money preference.")


class NarrationItem(BaseModel):
    """One grounded per-product sentence; ``reason`` may only restate the
    supplied highlights, never invent facts."""

    model_config = ConfigDict(extra="ignore")

    product_id: str
    reason: str = Field(min_length=1)


class Narration(BaseModel):
    """The spoken answer: intro, one sentence per recommended product, outro."""

    model_config = ConfigDict(extra="ignore")

    intro: str = Field(min_length=1)
    per_product: list[NarrationItem] = Field(default_factory=list)
    outro: str = Field(min_length=1)
