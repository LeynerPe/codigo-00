"""Reglas de negocio de la API de pagos simulada.

Las funciones de este módulo son puras (no dependen de la base de datos ni de
la red), lo que permite probarlas con pruebas unitarias rápidas.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import date
from decimal import Decimal

from app.codes import ResponseCode

MAX_AMOUNT = Decimal("10000000.00")  # Tope por transacción (COP)

# Tarjetas de prueba con resultado determinístico (todas cumplen Luhn).
TEST_CARD_OUTCOMES = {
    "4000000000000002": ResponseCode.DO_NOT_HONOR,
    "4000000000009995": ResponseCode.INSUFFICIENT_FUNDS,
}


def luhn_is_valid(pan: str) -> bool:
    """Valida el dígito de chequeo de un PAN con el algoritmo de Luhn."""
    if not pan.isdigit() or not 13 <= len(pan) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(pan)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def mask_pan(pan: str) -> str:
    """Enmascara el PAN dejando visibles los primeros 6 y los últimos 4 dígitos."""
    if len(pan) < 10:
        return "*" * len(pan)
    return f"{pan[:6]}{'*' * (len(pan) - 10)}{pan[-4:]}"


# Si no se configura CODIGO00_TOKEN_KEY, se usa una llave aleatoria por proceso.
_PROCESS_KEY = secrets.token_bytes(32)


def tokenize_pan(pan: str, key: bytes | None = None) -> str:
    """Genera un token irreversible del PAN con HMAC-SHA256."""
    secret = key or os.environ.get("CODIGO00_TOKEN_KEY", "").encode() or _PROCESS_KEY
    return hmac.new(secret, pan.encode(), hashlib.sha256).hexdigest()


def is_expired(exp_month: int, exp_year: int, today: date | None = None) -> bool:
    """Una tarjeta vence al terminar el mes indicado."""
    today = today or date.today()
    return (exp_year, exp_month) < (today.year, today.month)


def evaluate_authorization(
    pan: str,
    exp_month: int,
    exp_year: int,
    amount: Decimal,
    today: date | None = None,
) -> ResponseCode:
    """Decide el código de respuesta de una autorización.

    El orden de las validaciones replica el de un autorizador real: primero el
    formato de la tarjeta, luego el monto, la vigencia y por último el emisor.
    """
    if not luhn_is_valid(pan):
        return ResponseCode.INVALID_CARD_NUMBER
    if amount <= 0 or amount.as_tuple().exponent < -2:
        return ResponseCode.INVALID_AMOUNT
    if amount > MAX_AMOUNT:
        return ResponseCode.EXCEEDS_AMOUNT_LIMIT
    if is_expired(exp_month, exp_year, today):
        return ResponseCode.EXPIRED_CARD
    return TEST_CARD_OUTCOMES.get(pan, ResponseCode.APPROVED)


def evaluate_reversal(original: dict | None, amount: Decimal) -> ResponseCode:
    """Decide si un reverso procede sobre la transacción original."""
    if original is None:
        return ResponseCode.UNABLE_TO_LOCATE_RECORD
    if original["response_code"] != ResponseCode.APPROVED.value or original["status"] != "APPROVED":
        return ResponseCode.INVALID_TRANSACTION
    if Decimal(original["amount"]) != amount:
        return ResponseCode.ORIGINAL_AMOUNT_INCORRECT
    return ResponseCode.APPROVED


def new_auth_code() -> str:
    """Código de autorización de 6 dígitos (campo 38 de ISO 8583)."""
    return f"{secrets.randbelow(1_000_000):06d}"
