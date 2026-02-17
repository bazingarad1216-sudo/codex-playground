from __future__ import annotations

from dog_nutrition.search import expand_query

TERMS = ["鸡胸肉", "鸡肉", "鸡蛋", "鸡", "红薯"]


def main() -> None:
    for term in TERMS:
        expanded = expand_query(term)
        print(f"query={term} expanded_top10={expanded[:10]}")


if __name__ == "__main__":
    main()
