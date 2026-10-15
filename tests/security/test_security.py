"""Pruebas de seguridad de la lógica de negocio (compuerta G5).

Cubren riesgos que un analizador estático o un escáner dinámico genérico no
detectan porque dependen de las reglas del dominio de pagos.
"""

import logging

import pytest

from tests.conftest import APPROVED_PAN, auth_body

pytestmark = pytest.mark.security


# --- Autenticación -----------------------------------------------------------

@pytest.mark.parametrize("headers", [{}, {"X-API-Key": ""}, {"X-API-Key": "llave-falsa"}])
def test_authentication_required(client, headers):
    assert client.post("/v1/authorizations", json=auth_body(), headers=headers).status_code == 401
    assert client.get("/v1/transactions/x", headers=headers).status_code == 401


# --- OWASP API1:2023 — autorización a nivel de objeto (BOLA) ----------------

def test_merchant_cannot_read_foreign_transaction(client, authorize, headers_b):
    tx = authorize().json()
    response = client.get(f"/v1/transactions/{tx['transaction_id']}", headers=headers_b)
    assert response.status_code == 404


def test_merchant_cannot_reverse_foreign_transaction(client, authorize, headers_a, headers_b):
    tx = authorize().json()
    body = {"original_transaction_id": tx["transaction_id"], "amount": "150000.00"}
    attack = client.post("/v1/reversals", json=body, headers=headers_b).json()
    assert attack["response_code"] == "25"
    original = client.get(f"/v1/transactions/{tx['transaction_id']}", headers=headers_a).json()
    assert original["status"] == "APPROVED"


# --- Integridad del monto y asignación masiva --------------------------------

@pytest.mark.parametrize("amount", ["-1", "0", "0.001", "99999999999.99", "NaN", "Infinity"])
def test_tampered_amounts_are_never_approved(authorize, amount):
    response = authorize(amount=amount)
    assert response.status_code in (201, 422)
    if response.status_code == 201:
        assert response.json()["approved"] is False


def test_partial_reversal_is_not_allowed(client, authorize, headers_a):
    tx = authorize(amount="500000.00").json()
    body = {"original_transaction_id": tx["transaction_id"], "amount": "1.00"}
    assert client.post("/v1/reversals", json=body, headers=headers_a).json()["response_code"] == "64"


@pytest.mark.parametrize("extra", [{"status": "APPROVED"}, {"response_code": "00"}, {"merchant_id": "COMERCIO_B"}])
def test_mass_assignment_is_rejected(client, headers_a, extra):
    body = auth_body(card_number="4000000000000002")
    body.update(extra)
    assert client.post("/v1/authorizations", json=body, headers=headers_a).status_code == 422


# --- Protección de datos de tarjeta (PCI DSS req. 3) -------------------------

def test_full_pan_never_returned(client, authorize, headers_a):
    tx = authorize()
    assert APPROVED_PAN not in tx.text
    query = client.get(f"/v1/transactions/{tx.json()['transaction_id']}", headers=headers_a)
    assert APPROVED_PAN not in query.text


def test_full_pan_never_logged(authorize, caplog):
    with caplog.at_level(logging.DEBUG):
        authorize()
    assert APPROVED_PAN not in caplog.text


def test_pan_not_stored_in_clear(app, authorize):
    authorize()
    rows = app.state.repo._conn.execute("SELECT * FROM transactions").fetchall()
    for row in rows:
        assert APPROVED_PAN not in " ".join(str(value) for value in tuple(row))


# --- Inyección y manejo de errores -------------------------------------------

@pytest.mark.parametrize(
    "payload",
    ["' OR '1'='1", "1; DROP TABLE transactions--", "\" OR 1=1 --", "x' UNION SELECT * FROM transactions--"],
)
def test_sql_injection_in_path(client, authorize, headers_a, payload):
    authorize()
    response = client.get(f"/v1/transactions/{payload}", headers=headers_a)
    assert response.status_code == 404


def test_sql_injection_in_stan_is_rejected(client, headers_a):
    response = client.post("/v1/authorizations", json=auth_body(stan="1' OR 1=1--"), headers=headers_a)
    assert response.status_code == 422


def test_errors_do_not_leak_internals(client, headers_a):
    response = client.post("/v1/authorizations", content="{malformado", headers=headers_a)
    assert response.status_code == 422
    assert "Traceback" not in response.text and "sqlite" not in response.text.lower()


# --- Cabeceras de seguridad ---------------------------------------------------

@pytest.mark.parametrize(
    "header",
    ["X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy", "Cache-Control",
     "Strict-Transport-Security"],
)
def test_security_headers_present(client, header):
    assert header in client.get("/health").headers
    assert header in client.get("/v1/transactions/x").headers  # también en respuestas de error


# --- Superficie expuesta ------------------------------------------------------

def test_contract_not_exposed_by_default(client):
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404


def test_contract_has_no_valid_pan_examples(monkeypatch):
    import json as _json

    from app.main import create_app
    from app.rules import luhn_is_valid

    monkeypatch.setenv("CODIGO00_ENABLE_DOCS", "1")
    spec = _json.dumps(create_app(":memory:").openapi())
    import re
    candidates = re.findall(r"\b\d{13,19}\b", spec)
    assert not [c for c in candidates if luhn_is_valid(c)]
