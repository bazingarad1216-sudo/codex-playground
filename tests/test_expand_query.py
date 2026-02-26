from dog_nutrition.search import expand_query


def test_expand_query_egg_not_polluted() -> None:
    result = expand_query("鸡蛋")
    assert "egg" in result
    assert "chicken" not in result
    assert "whole" not in result


def test_expand_query_chicken_breast_kept() -> None:
    result = expand_query("鸡胸肉")
    assert "chicken" in result
    assert "breast" in result
