from __future__ import annotations

import csv
import re
from pathlib import Path

_ZH_ALIAS_SEED_PATH = Path("data/aliases/zh_seed.csv")
_TERM_SPLIT_RE = re.compile(r"[\s,;，；、|]+")
_STOPWORDS = {"and", "or", "&", "the", "whole"}
_CHICKEN_INTENT_TOKENS = ("鸡胸", "鸡肉", "鸡腿", "鸡翅")
_EGG_INTENT_TOKENS = ("蛋", "蛋黄", "蛋白", "全蛋", "鸡蛋")


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

    # longest key first: “鸡蛋” should win over “鸡”
    for alias in sorted(seed_map.keys(), key=len, reverse=True):
        alias_lower = alias.lower()
        if alias_lower in q or q == alias_lower or alias_lower in q.replace(" ", ""):
            expanded.extend(seed_map[alias])

    has_egg_intent = any(token in q for token in _EGG_INTENT_TOKENS)
    has_chicken_intent = q == "鸡" or any(token in q for token in _CHICKEN_INTENT_TOKENS)

    # chicken injection only for chicken intent, and forbidden for egg intent
    if has_chicken_intent and not has_egg_intent:
        expanded.extend(["chicken", "chicken breast", "chicken drumstick"])

    # ensure egg queries keep egg coverage and do not drift to chicken
    if has_egg_intent:
        expanded.extend(["egg", "whole egg", "egg yolk", "egg white"])

    # add noise-cleaned tokens (without words like whole)
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
