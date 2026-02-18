from __future__ import annotations

import re
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


def _term_tokens(term: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", term.lower().strip()) if token]


def expand_query(query: str) -> list[str]:
    q = query.strip().lower()
    candidates = [query]
    for cn, aliases in CN_ALIASES.items():
        if q in cn.lower() or any(q in alias.lower() for alias in aliases):
            candidates.extend(aliases)
            candidates.append(cn)

    expanded = list(dict.fromkeys(candidates))
    token_terms: list[str] = []
    for term in expanded:
        token_terms.extend(_term_tokens(term))

    merged = list(dict.fromkeys([*expanded, *token_terms]))
    if "鸡" in q:
        if "chicken" in merged:
            merged.remove("chicken")
        insert_idx = 1 if len(merged) >= 1 else 0
        if "egg" in merged:
            insert_idx = min(insert_idx, merged.index("egg"))
        merged.insert(insert_idx, "chicken")
    return merged




def _term_weight(term: str, query: str) -> float:
    normalized = term.lower().strip()
    if normalized == query.lower().strip():
        return 100.0
    if any("一" <= ch <= "鿿" for ch in term):
        return 80.0
    if normalized in {"chicken", "breast", "drumstick", "poultry", "chicken breast"}:
        return 70.0
    if normalized in {"egg", "whole egg", "white egg", "whole", "white"}:
        return 40.0
    return 50.0


def search_foods_cn(conn, query: str, limit: int = 20) -> list[SearchResult]:
    candidates: dict[int, SearchResult] = {}
    for term in expand_query(query):
        term_base = _char_overlap_score(query, term)
        weight = _term_weight(term, query)
        for food in search_foods(conn, term, limit=limit):
            score = weight + max(_char_overlap_score(query, food.name), _char_overlap_score(term, food.name), term_base)
            prev = candidates.get(food.id)
            if prev is None or score > prev.score:
                candidates[food.id] = SearchResult(food=food, score=score)
    return sorted(candidates.values(), key=lambda x: (-x.score, x.food.name))[:limit]
