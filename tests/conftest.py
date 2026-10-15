import json
import os
from datetime import date

import pytest

# Llaves de prueba (solo para el entorno de pruebas; en despliegue se inyectan
# como secreto del pipeline).
KEY_A = "test-comercio-a-7f3c"
KEY_B = "test-comercio-b-91d2"
os.environ["CODIGO00_API_KEYS"] = json.dumps({KEY_A: "COMERCIO_A", KEY_B: "COMERCIO_B"})

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402

APPROVED_PAN = "4111111111111111"
NEXT_YEAR = date.today().year + 1


@pytest.fixture()
def app():
    return create_app(":memory:")


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def headers_a():
    return {"X-API-Key": KEY_A}


@pytest.fixture()
def headers_b():
    return {"X-API-Key": KEY_B}


_stan_counter = iter(range(100000, 999999))


def auth_body(**overrides):
    body = {
        "card_number": APPROVED_PAN,
        "exp_month": 12,
        "exp_year": NEXT_YEAR,
        "amount": "150000.00",
        "currency": "COP",
        "stan": f"{next(_stan_counter):06d}",
    }
    body.update(overrides)
    return body


@pytest.fixture()
def authorize(client, headers_a):
    def _authorize(headers=None, **overrides):
        return client.post("/v1/authorizations", json=auth_body(**overrides), headers=headers or headers_a)
    return _authorize
