from dog_nutrition.search import expand_query


def test_expand_query_egg_not_polluted_by_chicken() -> None:
    result = expand_query("鸡蛋")
    assert "egg" in result
    assert "chicken" not in result
    assert "whole" not in result


def test_expand_query_egg_variants_do_not_inject_chicken() -> None:
    yolk = expand_query("鸡蛋黄")
    white = expand_query("鸡蛋白")
    assert "chicken" not in yolk
    assert "chicken" not in white
    assert any("egg" in item for item in yolk)
    assert any("egg" in item for item in white)


def test_expand_query_chicken_breast_still_has_chicken_and_breast() -> None:
    result = expand_query("鸡胸肉")
    assert "chicken" in result
    assert "breast" in result
