"""Pruebas funcionales de los flujos de pago a través de la API."""

import pytest

from tests.conftest import APPROVED_PAN, auth_body


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_approved_authorization(authorize):
    response = authorize()
    assert response.status_code == 201
    data = response.json()
    assert data["response_code"] == "00"
    assert data["approved"] is True
    assert data["status"] == "APPROVED"
    assert len(data["auth_code"]) == 6
    assert data["masked_pan"] == "411111******1111"
    assert data["amount"] == "150000.00"


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"card_number": "4000000000000002"}, "05"),
        ({"card_number": "4000000000009995"}, "51"),
        ({"card_number": "4111111111111112"}, "14"),
        ({"exp_year": 2020}, "54"),
        ({"amount": "0"}, "13"),
        ({"amount": "-100"}, "13"),
        ({"amount": "100.555"}, "13"),
        ({"amount": "10000000.01"}, "61"),
    ],
)
def test_declined_authorizations(authorize, overrides, code):
    response = authorize(**overrides)
    assert response.status_code == 201
    data = response.json()
    assert data["response_code"] == code
    assert data["approved"] is False
    assert data["auth_code"] is None


def test_duplicate_stan_is_rejected(client, headers_a):
    body = auth_body(stan="777777")
    first = client.post("/v1/authorizations", json=body, headers=headers_a)
    second = client.post("/v1/authorizations", json=body, headers=headers_a)
    assert first.json()["response_code"] == "00"
    assert second.json()["response_code"] == "94"


def test_same_stan_allowed_for_different_merchants(client, headers_a, headers_b):
    body = auth_body(stan="888888")
    assert client.post("/v1/authorizations", json=body, headers=headers_a).json()["response_code"] == "00"
    assert client.post("/v1/authorizations", json=body, headers=headers_b).json()["response_code"] == "00"


def test_query_own_transaction(client, authorize, headers_a):
    tx = authorize().json()
    response = client.get(f"/v1/transactions/{tx['transaction_id']}", headers=headers_a)
    assert response.status_code == 200
    assert response.json()["transaction_id"] == tx["transaction_id"]


def test_query_unknown_transaction(client, headers_a):
    response = client.get("/v1/transactions/00000000-0000-0000-0000-000000000000", headers=headers_a)
    assert response.status_code == 404


def test_full_reversal_flow(client, authorize, headers_a):
    tx = authorize(amount="250000.00").json()
    reversal = client.post(
        "/v1/reversals",
        json={"original_transaction_id": tx["transaction_id"], "amount": "250000.00"},
        headers=headers_a,
    )
    assert reversal.status_code == 201
    assert reversal.json()["response_code"] == "00"
    assert reversal.json()["type"] == "REVERSAL"
    original = client.get(f"/v1/transactions/{tx['transaction_id']}", headers=headers_a).json()
    assert original["status"] == "REVERSED"


def test_double_reversal_is_rejected(client, authorize, headers_a):
    tx = authorize().json()
    body = {"original_transaction_id": tx["transaction_id"], "amount": "150000.00"}
    assert client.post("/v1/reversals", json=body, headers=headers_a).json()["response_code"] == "00"
    assert client.post("/v1/reversals", json=body, headers=headers_a).json()["response_code"] == "12"


def test_reversal_amount_must_match(client, authorize, headers_a):
    tx = authorize().json()
    body = {"original_transaction_id": tx["transaction_id"], "amount": "149999.99"}
    assert client.post("/v1/reversals", json=body, headers=headers_a).json()["response_code"] == "64"


def test_reversal_of_declined_authorization(client, authorize, headers_a):
    tx = authorize(card_number="4000000000000002").json()
    body = {"original_transaction_id": tx["transaction_id"], "amount": "150000.00"}
    assert client.post("/v1/reversals", json=body, headers=headers_a).json()["response_code"] == "12"


def test_reversal_of_unknown_transaction(client, headers_a):
    body = {"original_transaction_id": "00000000-0000-0000-0000-000000000000", "amount": "1.00"}
    response = client.post("/v1/reversals", json=body, headers=headers_a)
    assert response.json()["response_code"] == "25"


def test_reversal_record_cannot_be_reversed(client, authorize, headers_a):
    tx = authorize().json()
    rev = client.post("/v1/reversals", json={"original_transaction_id": tx["transaction_id"],
                                             "amount": "150000.00"}, headers=headers_a).json()
    again = client.post("/v1/reversals", json={"original_transaction_id": rev["transaction_id"],
                                               "amount": "150000.00"}, headers=headers_a)
    assert again.json()["response_code"] == "25"


@pytest.mark.parametrize(
    "field,value",
    [("currency", "EUR"), ("stan", "12"), ("exp_month", 13), ("card_number", "4111-1111"), ("amount", "abc")],
)
def test_schema_validation(client, headers_a, field, value):
    response = client.post("/v1/authorizations", json=auth_body(**{field: value}), headers=headers_a)
    assert response.status_code == 422


def test_usd_currency_supported(authorize):
    data = authorize(currency="USD", amount="20.50").json()
    assert data["response_code"] == "00"
    assert data["currency"] == "USD"


def test_approved_pan_constant_is_valid():
    from app.rules import luhn_is_valid
    assert luhn_is_valid(APPROVED_PAN)
