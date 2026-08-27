from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.places import PlaceOut


class DecisionSessionCardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    place: PlaceOut
    role: str
    reason_codes: List[str] = Field(default_factory=list)


class DecisionSessionOut(BaseModel):
    """
    0-3 cards -- never padded. See docs/decision_session_spec.md.
    `degraded=True` means fewer than 3 roles could be filled from real
    diversity in the candidate pool (thin catalog for this area), not an
    error -- callers render however many cards are present.
    """

    model_config = ConfigDict(frozen=True)

    cards: List[DecisionSessionCardOut] = Field(default_factory=list)
    degraded: bool = False
