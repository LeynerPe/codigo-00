"""Autenticación de comercios por llave de API.

Las llaves nunca se guardan en claro: se cargan desde la variable de entorno
CODIGO00_API_KEYS (JSON {"llave": "id_comercio"}) y se conservan como hash
SHA-256. La comparación se hace en tiempo constante.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

from fastapi import Header, HTTPException, Request, status

API_KEYS_ENV = "CODIGO00_API_KEYS"


def load_key_hashes() -> dict[str, str]:
    raw = os.environ.get(API_KEYS_ENV, "{}")
    keys = json.loads(raw)
    return {hashlib.sha256(key.encode()).hexdigest(): merchant for key, merchant in keys.items()}


def resolve_merchant(key_hashes: dict[str, str], api_key: str | None) -> str | None:
    if not api_key:
        return None
    candidate = hashlib.sha256(api_key.encode()).hexdigest()
    for stored_hash, merchant in key_hashes.items():
        if hmac.compare_digest(stored_hash, candidate):
            return merchant
    return None


def current_merchant(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    merchant = resolve_merchant(request.app.state.key_hashes, x_api_key)
    if merchant is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Llave de API ausente o inválida",
        )
    return merchant
