"""Esquemas de entrada y salida de la API."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AuthorizationRequest(BaseModel):
    # extra="forbid" evita la asignación masiva: el cliente no puede enviar
    # campos como status o response_code para forzar un resultado.
    model_config = ConfigDict(extra="forbid")

    card_number: str = Field(min_length=13, max_length=19, pattern=r"^\d+$", examples=["4111111111111112"],
                             json_schema_extra={"example": "4111111111111112"},
                             description="PAN de 13 a 19 dígitos. El ejemplo no supera Luhn a propósito: "
                                         "el contrato nunca publica números de tarjeta válidos.")
    exp_month: int = Field(ge=1, le=12, examples=[12], json_schema_extra={"example": 12})
    exp_year: int = Field(ge=2000, le=2099, examples=[2030], json_schema_extra={"example": 2030})
    amount: Decimal = Field(max_digits=14, examples=["150000.00"], json_schema_extra={"example": "150000.00"})
    currency: Literal["COP", "USD"] = Field(default="COP", examples=["COP"], json_schema_extra={"example": "COP"})
    stan: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$", examples=["123456"], json_schema_extra={"example": "123456"},
                      description="System Trace Audit Number (campo 11 de ISO 8583)")


class ReversalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_transaction_id: str = Field(min_length=36, max_length=36,
                                         examples=["3f2b9c1e-7d4a-4e8b-9c55-0a1b2c3d4e5f"], json_schema_extra={"example": "3f2b9c1e-7d4a-4e8b-9c55-0a1b2c3d4e5f"})
    amount: Decimal = Field(max_digits=14, examples=["150000.00"], json_schema_extra={"example": "150000.00"})


class TransactionResponse(BaseModel):
    transaction_id: str
    type: Literal["AUTHORIZATION", "REVERSAL"]
    response_code: str
    response_message: str
    approved: bool
    status: str
    amount: str
    currency: str
    masked_pan: str | None = None
    stan: str | None = None
    auth_code: str | None = None
    original_transaction_id: str | None = None
    created_at: str


class ErrorResponse(BaseModel):
    detail: str
