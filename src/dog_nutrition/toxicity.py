from __future__ import annotations

_TOXIC_KEYWORDS = (
    "onion",
    "chocolate",
    "grape",
    "xylitol",
    "葡萄",
    "木糖醇",
    "洋葱",
    "巧克力",
)


def is_toxic_food_name(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in _TOXIC_KEYWORDS)
