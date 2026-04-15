# app/services/scoring/signal_context.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set

@dataclass
class SignalContext:
    image_counts: Dict[str, int] = field(default_factory=dict)
    menu_item_counts: Dict[str, int] = field(default_factory=dict)
    has_primary: Set[str] = field(default_factory=set)
    hitlist_scores: Dict[str, float] = field(default_factory=dict)
    creator_scores: Dict[str, float] = field(default_factory=dict)
    creator_mention_counts: Dict[str, int] = field(default_factory=dict)
    awards_scores: Dict[str, float] = field(default_factory=dict)
    blog_scores: Dict[str, float] = field(default_factory=dict)
    blog_mention_counts: Dict[str, int] = field(default_factory=dict)

    def image_count(self, place_id: str) -> int:
        return self.image_counts.get(place_id, 0)

    def menu_item_count(self, place_id: str) -> int:
        return self.menu_item_counts.get(place_id, 0)

    def has_primary_image(self, place_id: str) -> bool:
        return place_id in self.has_primary

    def hitlist_score(self, place_id: str) -> float:
        return self.hitlist_scores.get(place_id, 0.0)

    def creator_score(self, place_id: str) -> float:
        return self.creator_scores.get(place_id, 0.0)

    def creator_mention_count(self, place_id: str) -> int:
        return self.creator_mention_counts.get(place_id, 0)

    def awards_score(self, place_id: str) -> float:
        return self.awards_scores.get(place_id, 0.0)

    def blog_score(self, place_id: str) -> float:
        return self.blog_scores.get(place_id, 0.0)

    def blog_mention_count(self, place_id: str) -> int:
        return self.blog_mention_counts.get(place_id, 0)
