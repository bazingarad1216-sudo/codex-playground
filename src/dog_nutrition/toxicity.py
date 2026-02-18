TOXIC_KEYWORDS = {
    "onion", "garlic", "chive", "leek", "chocolate", "cocoa", "grape", "raisin",
    "xylitol", "alcohol", "macadamia", "avocado pit", "coffee", "tea leaf",
    "洋葱", "大蒜", "韭菜", "巧克力", "可可", "葡萄", "葡萄干", "木糖醇", "酒精", "夏威夷果",
}


def is_toxic_food_name(name: str) -> bool:
    lowered = name.strip().lower()
    if not lowered:
        return False
    return any(keyword in lowered for keyword in TOXIC_KEYWORDS)
