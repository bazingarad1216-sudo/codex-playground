from __future__ import annotations

from dataclasses import dataclass

from .foods_db import FoodRecord, search_foods
from .nutrients import CN_ALIASES


@dataclass(frozen=True)
class SearchResult:
    food: FoodRecord
    score: float


def _char_overlap_score(a: str, b: str) -> float:
    sa = set(a.lower().strip())
    sb = set(b.lower().strip())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def expand_query(query: str) -> list[str]:
    q = query.strip().lower()
    candidates = [query]
    for cn, aliases in CN_ALIASES.items():
        if q in cn.lower() or any(q in alias.lower() for alias in aliases):
            candidates.extend(aliases)
            candidates.append(cn)
    return list(dict.fromkeys(candidates))


def search_foods_cn(conn, query: str, limit: int = 20) -> list[SearchResult]:
    candidates: dict[int, SearchResult] = {}
    for term in expand_query(query):
        for food in search_foods(conn, term, limit=limit):
            score = max(_char_overlap_score(query, food.name), _char_overlap_score(term, food.name))
            prev = candidates.get(food.id)
            if prev is None or score > prev.score:
                candidates[food.id] = SearchResult(food=food, score=score)
    return sorted(candidates.values(), key=lambda x: (-x.score, x.food.name))[:limit]
