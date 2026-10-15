"""Código 00 — API de pagos simulada.

Operaciones: autorización, reverso y consulta. No se conecta a ninguna red
transaccional real; los resultados se deciden con reglas determinísticas para
que el comportamiento sea verificable por las pruebas automatizadas.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.responses import JSONResponse

from app import rules
from app.auth import current_merchant, load_key_hashes
from app.codes import ResponseCode, message_for
from app.db import Repository
from app.models import (
    AuthorizationRequest,
    ErrorResponse,
    ReversalRequest,
    TransactionResponse,
)

logger = logging.getLogger("codigo00")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_response(row: dict) -> TransactionResponse:
    code = ResponseCode(row["response_code"])
    return TransactionResponse(
        transaction_id=row["id"],
        type=row["type"],
        response_code=code.value,
        response_message=message_for(code),
        approved=code is ResponseCode.APPROVED,
        status=row["status"],
        amount=row["amount"],
        currency=row["currency"],
        masked_pan=row.get("masked_pan"),
        stan=row.get("stan"),
        auth_code=row.get("auth_code"),
        original_transaction_id=row.get("original_id"),
        created_at=row["created_at"],
    )


def create_app(db_path: str | None = None) -> FastAPI:
    enable_docs = os.environ.get("CODIGO00_ENABLE_DOCS") == "1"
    app = FastAPI(
        title="Código 00 — API de pagos simulada",
        version="1.0.0",
        description="Autorización, reverso y consulta con códigos de respuesta inspirados en ISO 8583.",
        # El contrato y la documentación solo se exponen en entornos de prueba.
        docs_url="/docs" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
        redoc_url=None,
    )
    app.state.repo = Repository(db_path or os.environ.get("CODIGO00_DB", ":memory:"))
    app.state.key_hashes = load_key_hashes()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):  # pragma: no cover - ruta defensiva
        logger.exception("Error no controlado en %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno", "response_code": ResponseCode.SYSTEM_MALFUNCTION.value},
        )

    @app.get("/health", tags=["operación"])
    def health() -> dict:
        return {"status": "ok"}

    @app.post(
        "/v1/authorizations",
        response_model=TransactionResponse,
        status_code=status.HTTP_201_CREATED,
        responses={401: {"model": ErrorResponse}},
        tags=["pagos"],
    )
    def authorize(body: AuthorizationRequest, request: Request,
                  merchant: str = Depends(current_merchant)) -> TransactionResponse:
        repo: Repository = request.app.state.repo
        if repo.stan_exists(merchant, body.stan):
            code = ResponseCode.DUPLICATE_TRANSMISSION
        else:
            code = rules.evaluate_authorization(body.card_number, body.exp_month, body.exp_year, body.amount)

        row = {
            "id": str(uuid.uuid4()),
            "merchant_id": merchant,
            "type": "AUTHORIZATION",
            "stan": body.stan,
            "masked_pan": rules.mask_pan(body.card_number),
            "pan_token": rules.tokenize_pan(body.card_number),
            "amount": str(body.amount),
            "currency": body.currency,
            "response_code": code.value,
            "status": "APPROVED" if code is ResponseCode.APPROVED else "DECLINED",
            "auth_code": rules.new_auth_code() if code is ResponseCode.APPROVED else None,
            "original_id": None,
            "created_at": _now(),
        }
        try:
            repo.insert(row)
        except sqlite3.IntegrityError:
            # Dos solicitudes simultáneas con el mismo STAN: la segunda es duplicada.
            row.update(response_code=ResponseCode.DUPLICATE_TRANSMISSION.value,
                       status="DECLINED", auth_code=None)
            repo.insert(row)
        logger.info("Autorización %s comercio=%s pan=%s codigo=%s",
                    row["id"], merchant, row["masked_pan"], row["response_code"])
        return _to_response(row)

    @app.post(
        "/v1/reversals",
        response_model=TransactionResponse,
        status_code=status.HTTP_201_CREATED,
        responses={401: {"model": ErrorResponse}},
        tags=["pagos"],
    )
    def reverse(body: ReversalRequest, request: Request,
                merchant: str = Depends(current_merchant)) -> TransactionResponse:
        repo: Repository = request.app.state.repo
        # La búsqueda filtra por comercio: un comercio no puede reversar
        # operaciones ajenas (OWASP API1:2023, autorización a nivel de objeto).
        original = repo.get_for_merchant(body.original_transaction_id, merchant)
        if original is not None and original["type"] != "AUTHORIZATION":
            original = None
        code = rules.evaluate_reversal(original, body.amount)
        if code is ResponseCode.APPROVED and not repo.mark_reversed(original["id"]):
            code = ResponseCode.INVALID_TRANSACTION  # ya fue reversada en paralelo

        row = {
            "id": str(uuid.uuid4()),
            "merchant_id": merchant,
            "type": "REVERSAL",
            "stan": None,
            "masked_pan": original["masked_pan"] if original else None,
            "pan_token": None,
            "amount": str(body.amount),
            "currency": original["currency"] if original else "COP",
            "response_code": code.value,
            "status": "APPROVED" if code is ResponseCode.APPROVED else "DECLINED",
            "auth_code": None,
            "original_id": body.original_transaction_id,
            "created_at": _now(),
        }
        repo.insert(row)
        logger.info("Reverso %s comercio=%s original=%s codigo=%s",
                    row["id"], merchant, body.original_transaction_id, code.value)
        return _to_response(row)

    @app.get(
        "/v1/transactions/{transaction_id}",
        response_model=TransactionResponse,
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
        tags=["pagos"],
    )
    def get_transaction(request: Request,
                        transaction_id: str = Path(
                            openapi_examples={"transaccion": {"value": "3f2b9c1e-7d4a-4e8b-9c55-0a1b2c3d4e5f"}}),
                        merchant: str = Depends(current_merchant)) -> TransactionResponse:
        row = request.app.state.repo.get_for_merchant(transaction_id, merchant)
        if row is None:
            raise HTTPException(status_code=404, detail="Transacción no encontrada")
        return _to_response(row)

    return app


app = create_app()
