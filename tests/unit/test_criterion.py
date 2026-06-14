import pytest

from stone.selector.criterion import safe_eval_criterion


def test_simple_gte():
    assert safe_eval_criterion("value >= 0.5", 0.6) is True
    assert safe_eval_criterion("value >= 0.5", 0.4) is False


def test_combined_and():
    expr = "value >= 0.3 and value <= 0.7"
    assert safe_eval_criterion(expr, 0.5) is True
    assert safe_eval_criterion(expr, 0.2) is False
    assert safe_eval_criterion(expr, 0.9) is False


def test_injection_import_blocked():
    with pytest.raises(ValueError, match="非法表达式"):
        safe_eval_criterion("__import__('os').system('rm -rf /')", 1.0)


def test_injection_attribute_access_blocked():
    with pytest.raises(ValueError, match="非法表达式"):
        safe_eval_criterion("value.__class__", 1.0)


def test_injection_call_blocked():
    with pytest.raises(ValueError, match="非法表达式"):
        safe_eval_criterion("open('/etc/passwd').read()", 1.0)


def test_equality():
    assert safe_eval_criterion("value == 1.0", 1.0) is True
    assert safe_eval_criterion("value == 1.0", 2.0) is False
