from datetime import date
from decimal import Decimal

import pytest

from app import rules
from app.auth import load_key_hashes, resolve_merchant
from app.codes import MESSAGES, ResponseCode

TODAY = date(2026, 10, 14)


@pytest.mark.parametrize("pan", ["4111111111111111", "5555555555554444", "4000000000000002", "378282246310005"])
def test_luhn_valid(pan):
    assert rules.luhn_is_valid(pan)


@pytest.mark.parametrize("pan", ["4111111111111112", "1234567890123", "41111111111a1111", "411111111111", ""])
def test_luhn_invalid(pan):
    assert not rules.luhn_is_valid(pan)


def test_mask_pan_keeps_bin_and_last_four():
    assert rules.mask_pan("4111111111111111") == "411111******1111"


def test_mask_pan_short_value_fully_masked():
    assert rules.mask_pan("12345") == "*****"


def test_tokenize_is_deterministic_and_hides_pan():
    token = rules.tokenize_pan("4111111111111111", key=b"k")
    assert token == rules.tokenize_pan("4111111111111111", key=b"k")
    assert "4111111111111111" not in token
    assert len(token) == 64


def test_tokenize_changes_with_key():
    assert rules.tokenize_pan("4111111111111111", key=b"a") != rules.tokenize_pan("4111111111111111", key=b"b")


@pytest.mark.parametrize(
    "month,year,expired",
    [(10, 2026, False), (9, 2026, True), (12, 2025, True), (1, 2027, False)],
)
def test_is_expired(month, year, expired):
    assert rules.is_expired(month, year, TODAY) is expired


@pytest.mark.parametrize(
    "pan,amount,month,year,expected",
    [
        ("4111111111111111", Decimal("1000"), 12, 2030, ResponseCode.APPROVED),
        ("4111111111111112", Decimal("1000"), 12, 2030, ResponseCode.INVALID_CARD_NUMBER),
        ("4111111111111111", Decimal("0"), 12, 2030, ResponseCode.INVALID_AMOUNT),
        ("4111111111111111", Decimal("-5"), 12, 2030, ResponseCode.INVALID_AMOUNT),
        ("4111111111111111", Decimal("10.001"), 12, 2030, ResponseCode.INVALID_AMOUNT),
        ("4111111111111111", Decimal("10000000.01"), 12, 2030, ResponseCode.EXCEEDS_AMOUNT_LIMIT),
        ("4111111111111111", Decimal("10000000.00"), 12, 2030, ResponseCode.APPROVED),
        ("4111111111111111", Decimal("1000"), 1, 2020, ResponseCode.EXPIRED_CARD),
        ("4000000000000002", Decimal("1000"), 12, 2030, ResponseCode.DO_NOT_HONOR),
        ("4000000000009995", Decimal("1000"), 12, 2030, ResponseCode.INSUFFICIENT_FUNDS),
    ],
)
def test_evaluate_authorization(pan, amount, month, year, expected):
    assert rules.evaluate_authorization(pan, month, year, amount, TODAY) is expected


def _original(**overrides):
    row = {"response_code": "00", "status": "APPROVED", "amount": "1000.00"}
    row.update(overrides)
    return row


def test_reversal_without_original():
    assert rules.evaluate_reversal(None, Decimal("1")) is ResponseCode.UNABLE_TO_LOCATE_RECORD


def test_reversal_of_declined_transaction():
    assert rules.evaluate_reversal(_original(response_code="05", status="DECLINED"), Decimal("1000.00")) \
        is ResponseCode.INVALID_TRANSACTION


def test_reversal_of_already_reversed():
    assert rules.evaluate_reversal(_original(status="REVERSED"), Decimal("1000.00")) is ResponseCode.INVALID_TRANSACTION


def test_reversal_amount_mismatch():
    assert rules.evaluate_reversal(_original(), Decimal("999.99")) is ResponseCode.ORIGINAL_AMOUNT_INCORRECT


def test_reversal_ok():
    assert rules.evaluate_reversal(_original(), Decimal("1000")) is ResponseCode.APPROVED


def test_auth_code_has_six_digits():
    for _ in range(50):
        code = rules.new_auth_code()
        assert len(code) == 6 and code.isdigit()


def test_every_code_has_message():
    assert set(MESSAGES) == set(ResponseCode)


def test_resolve_merchant(monkeypatch):
    monkeypatch.setenv("CODIGO00_API_KEYS", '{"llave-x": "M1"}')
    hashes = load_key_hashes()
    assert "llave-x" not in hashes  # se guardan hashes, no llaves
    assert resolve_merchant(hashes, "llave-x") == "M1"
    assert resolve_merchant(hashes, "otra") is None
    assert resolve_merchant(hashes, None) is None
