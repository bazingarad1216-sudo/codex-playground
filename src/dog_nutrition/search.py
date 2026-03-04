from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .foods_db import FoodRecord, search_foods

_ZH_ALIAS_SEED_PATH = Path("data/aliases/zh_seed.csv")
_TERM_SPLIT_RE = re.compile(r"[\s,;，；、|]+")
_STOPWORDS = {"and", "or", "&", "the", "whole"}
_CHICKEN_INTENT_TOKENS = ("鸡", "鸡肉", "鸡胸", "鸡腿", "鸡翅", "鸡胗", "鸡心", "鸡肝", "鸡爪")
_EGG_INTENT_TOKENS = ("蛋", "鸡蛋", "蛋黄", "蛋白", "全蛋", "蛋清", "蛋液")


@dataclass(frozen=True)
class SearchResult:
    food: FoodRecord
    score: float


def _load_seed_alias_map() -> dict[str, list[str]]:
    if not _ZH_ALIAS_SEED_PATH.exists():
        return {}

    mapping: dict[str, list[str]] = {}
    with _ZH_ALIAS_SEED_PATH.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            alias = (row.get("alias") or "").strip().lower()
            expands_to = (row.get("expands_to") or "").strip()
            if not alias or not expands_to:
                continue
            candidates = [item.strip().lower() for item in expands_to.split("|") if item.strip()]
            if candidates:
                mapping[alias] = candidates
    return mapping


def _term_tokens(terms: list[str]) -> list[str]:
    tokens: list[str] = []
    for term in terms:
        for raw in _TERM_SPLIT_RE.split(term.lower()):
            token = raw.strip()
            if not token or token in _STOPWORDS:
                continue
            tokens.append(token)
    return tokens


def expand_query(query: str) -> list[str]:
    q = query.strip().lower()
    if not q:
        return []

    seed_map = _load_seed_alias_map()
    expanded: list[str] = [q]

    for alias in sorted(seed_map.keys(), key=len, reverse=True):
        alias_lower = alias.lower()
        if alias_lower in q or q == alias_lower:
            expanded.extend(seed_map[alias])

    has_egg_intent = any(token in q for token in _EGG_INTENT_TOKENS)
    has_chicken_intent = q == "鸡" or any(token in q for token in _CHICKEN_INTENT_TOKENS)

    if has_chicken_intent and not has_egg_intent:
        expanded.extend(["chicken", "chicken breast", "chicken drumstick"])

    if has_egg_intent:
        expanded.extend(["egg", "whole egg", "egg yolk", "egg white"])

    expanded.extend(_term_tokens(expanded))

    deduped: list[str] = []
    seen: set[str] = set()
    for item in expanded:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        if has_egg_intent and normalized == "chicken":
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _intent_bonus(query: str, food_name: str) -> float:
    q = query.strip()
    n = food_name.lower()
    score = 0.0
    egg_query = any(token in q for token in _EGG_INTENT_TOKENS)
    chicken_query = q == "鸡" or any(token in q for token in _CHICKEN_INTENT_TOKENS)
    breast_query = "鸡胸" in q

    if egg_query and "egg" in n:
        score += 20.0
    if egg_query and "chicken" in n and "egg" not in n:
        score -= 20.0
    if chicken_query and "chicken" in n:
        score += 10.0
    if breast_query and "breast" in n:
        score += 10.0
    return score


def search_foods_cn(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[SearchResult]:
    merged: dict[int, SearchResult] = {}
    candidates = expand_query(query)
    for idx, term in enumerate(candidates):
        term_weight = max(1.0, float(len(term))) - idx * 0.1
        for food in search_foods(conn, term, limit=limit):
            score = term_weight + _intent_bonus(query, food.name)
            prev = merged.get(food.id)
            if prev is None or score > prev.score:
                merged[food.id] = SearchResult(food=food, score=score)

    ranked = sorted(merged.values(), key=lambda x: (-x.score, x.food.name.lower()))
    return ranked[:limit]
