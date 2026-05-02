"""Sale-scenario shared types: hold distribution + sale-scenario inputs.

The engine's ``backend.engine.finance.sale`` step consumes these shapes,
and the ``backend.providers.hold_distribution`` adapter populates the
``HoldYearProbability`` list. Keeping the types here lets the engine
stay pure (no ``backend.providers`` imports) and lets providers fill in
the same shape without reaching into the engine — same convention as
``backend.domain.tariff`` and ``backend.domain.tmy``.

The provider port (``HoldDistributionProvider``) and lookup-key model
(``HoldDistributionQuery``) stay in ``backend.providers.hold_distribution``:
they're IO contracts, not pure-math shapes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

#: LBNL Hoen et al. 2015 — US home-sale PV premium.
DEFAULT_HOME_VALUE_UPLIFT_PER_W_DC = 4.0

#: US realtor + title-fee rule of thumb.
DEFAULT_TRANSACTION_COSTS_PCT = 0.06


class HoldYearProbability(BaseModel):
    """One node in the discrete sale-year distribution.

    ``year`` is 1-indexed (year 1 = "sold after one year"). ``probability``
    is the prior over this candidate sale year; the consumer is
    expected to provide a list summing to 1.0 (validated on
    :class:`SaleScenarioInputs`).
    """

    year: int = Field(..., ge=1, le=40)
    probability: float = Field(..., ge=0.0, le=1.0)


class SaleScenarioInputs(BaseModel):
    """User-tweakable knobs for the sale-scenario math.

    Defaults reflect the headline LBNL Hoen number plus a no-decay
    assumption — callers who want a more conservative read can pass
    ``home_value_decay_per_year`` >0 to fade the uplift.
    """

    home_value_uplift_per_w_dc: float = Field(
        DEFAULT_HOME_VALUE_UPLIFT_PER_W_DC,
        ge=0.0,
        le=20.0,
    )
    home_value_decay_per_year: float = Field(0.0, ge=0.0, le=0.10)
    transaction_costs_pct: float = Field(DEFAULT_TRANSACTION_COSTS_PCT, ge=0.0, le=0.20)
    hold_year_probabilities: list[HoldYearProbability]

    @model_validator(mode="after")
    def _probabilities_sum_to_one(self) -> SaleScenarioInputs:
        if not self.hold_year_probabilities:
            raise ValueError("hold_year_probabilities must be non-empty")
        total = sum(p.probability for p in self.hold_year_probabilities)
        if not 0.999 <= total <= 1.001:
            raise ValueError(f"hold_year_probabilities must sum to 1.0; got {total:.4f}")
        return self


__all__ = [
    "DEFAULT_HOME_VALUE_UPLIFT_PER_W_DC",
    "DEFAULT_TRANSACTION_COSTS_PCT",
    "HoldYearProbability",
    "SaleScenarioInputs",
]
