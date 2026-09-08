import pytest

from app.domain import DomainError, evaluate, parse_phone, parse_price, required_text


@pytest.mark.parametrize(
    ("rule", "votes", "expected"),
    [
        ("veto", ["reject", None, None], "rejected"),
        ("veto", ["accept", "accept", None], "pending"),
        ("veto", ["accept", "accept"], "approved"),
        ("majority", ["accept", "accept", None], "approved"),
        ("majority", ["accept", "reject"], "rejected"),
        ("majority", ["reject", "accept", None], "pending"),
        ("majority", ["reject", "reject", None], "rejected"),
        ("unanimous", ["reject", None], "pending"),
        ("unanimous", ["reject", "accept"], "rejected"),
        ("unanimous", ["accept", "accept"], "approved"),
    ],
)
def test_approval_result(rule, votes, expected):
    assert evaluate(rule, votes) == expected


def test_invalid_rule_and_empty_reviewers_never_approve():
    with pytest.raises(DomainError):
        evaluate("invented", ["accept"])
    with pytest.raises(DomainError):
        evaluate("veto", [])


@pytest.mark.parametrize("value", [0, -1, 1.5, "100", 100_000_001])
def test_price_requires_positive_integer_cents(value):
    with pytest.raises(DomainError):
        parse_price(value)
    assert parse_price(12_345) == 12_345


def test_text_is_trimmed_and_bounded():
    assert required_text(" 可以买 ", "评论", 500) == "可以买"
    with pytest.raises(DomainError):
        required_text("   ", "评论", 500)
    with pytest.raises(DomainError):
        required_text("a" * 501, "评论", 500)


@pytest.mark.parametrize("phone", ["138", "00000000000", "+8613800138000", "13800138000x"])
def test_first_release_accepts_only_mainland_mobile_numbers(phone):
    with pytest.raises(DomainError):
        parse_phone(phone)
    assert parse_phone("13800138000") == "13800138000"
