"""Persistencia en SQLite con consultas parametrizadas."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id              TEXT PRIMARY KEY,
    merchant_id     TEXT NOT NULL,
    type            TEXT NOT NULL,            -- AUTHORIZATION | REVERSAL
    stan            TEXT,
    masked_pan      TEXT,
    pan_token       TEXT,
    amount          TEXT NOT NULL,
    currency        TEXT NOT NULL,
    response_code   TEXT NOT NULL,
    status          TEXT NOT NULL,            -- APPROVED | DECLINED | REVERSED
    auth_code       TEXT,
    original_id     TEXT,
    created_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_merchant_stan
    ON transactions (merchant_id, stan) WHERE type = 'AUTHORIZATION' AND response_code <> '94';
"""

COLUMNS = (
    "id", "merchant_id", "type", "stan", "masked_pan", "pan_token", "amount",
    "currency", "response_code", "status", "auth_code", "original_id", "created_at",
)

INSERT_SQL = (
    "INSERT INTO transactions (id, merchant_id, type, stan, masked_pan, pan_token, amount, "
    "currency, response_code, status, auth_code, original_id, created_at) VALUES "
    "(:id, :merchant_id, :type, :stan, :masked_pan, :pan_token, :amount, "
    ":currency, :response_code, :status, :auth_code, :original_id, :created_at)"
)


class Repository:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def insert(self, row: dict) -> None:
        with self._tx() as conn:
            conn.execute(INSERT_SQL, {column: row.get(column) for column in COLUMNS})

    def stan_exists(self, merchant_id: str, stan: str) -> bool:
        with self._tx() as conn:
            cur = conn.execute(
                "SELECT 1 FROM transactions WHERE merchant_id = ? AND stan = ? "
                "AND type = 'AUTHORIZATION' AND response_code <> '94'",
                (merchant_id, stan),
            )
            return cur.fetchone() is not None

    def get_for_merchant(self, transaction_id: str, merchant_id: str) -> dict | None:
        """Busca una transacción solo dentro de las del comercio autenticado."""
        with self._tx() as conn:
            cur = conn.execute(
                "SELECT * FROM transactions WHERE id = ? AND merchant_id = ?",
                (transaction_id, merchant_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def mark_reversed(self, transaction_id: str) -> bool:
        """Marca como reversada una autorización aprobada (operación atómica)."""
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE transactions SET status = 'REVERSED' WHERE id = ? AND status = 'APPROVED'",
                (transaction_id,),
            )
            return cur.rowcount == 1
