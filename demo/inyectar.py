#!/usr/bin/env python3
"""Crea copias del proyecto con defectos inyectados de forma controlada.

Escenarios:
  vulnerable  Cuatro errores de seguridad frecuentes en software de pagos:
              V1 inyección SQL en la consulta de transacciones,
              V2 reverso sin control de propiedad (BOLA, OWASP API1:2023),
              V3 PAN completo en los registros de auditoría,
              V4 dependencia con vulnerabilidades conocidas y cliente HTTP
                 sin verificación TLS ni tiempo de espera.
  funcional   Dos defectos funcionales de negocio:
              F1 error de límite en el tope de monto (> cambia a >=),
              F2 el reverso deja de validar que el monto coincida con el original.

Uso:  python demo/inyectar.py vulnerable /tmp/codigo00-vulnerable
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns(".git", "reports", "__pycache__", "*.db", ".pytest_cache", ".coverage")


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"No se encontró el fragmento a reemplazar en {path}:\n{old}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def vulnerable(dst: Path) -> None:
    db = dst / "app" / "db.py"
    main = dst / "app" / "main.py"
    # V1 — consulta construida con f-string (inyección SQL)
    replace(db,
            '''            cur = conn.execute(
                "SELECT * FROM transactions WHERE id = ? AND merchant_id = ?",
                (transaction_id, merchant_id),
            )''',
            '''            cur = conn.execute(
                f"SELECT * FROM transactions WHERE id = '{transaction_id}' AND merchant_id = '{merchant_id}'"
            )''')
    # V2 — el reverso busca la transacción original sin filtrar por comercio
    replace(db, '''    def mark_reversed(''', '''    def get_by_id(self, transaction_id: str) -> dict | None:
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
            return dict(row) if row else None

    def mark_reversed(''')
    replace(main, "original = repo.get_for_merchant(body.original_transaction_id, merchant)",
            "original = repo.get_by_id(body.original_transaction_id)")
    # V3 — PAN completo en el log
    replace(main, '''        logger.info("Autorización %s comercio=%s pan=%s codigo=%s",
                    row["id"], merchant, row["masked_pan"], row["response_code"])''',
            '''        logger.info("Autorización %s comercio=%s pan=%s codigo=%s",
                    row["id"], merchant, body.card_number, row["response_code"])''')
    # V4 — cliente antifraude con dependencia vulnerable, sin TLS ni timeout
    (dst / "app" / "fraud.py").write_text('''"""Consulta a un servicio antifraude externo (opcional)."""
import os

import requests


def score(masked_pan: str, amount: str) -> int:
    url = os.environ.get("FRAUD_URL")
    if not url:
        return 0
    response = requests.post(url, json={"pan": masked_pan, "amount": amount}, verify=False)
    return int(response.json().get("score", 0))
''', encoding="utf-8")
    replace(main, "from app import rules", "from app import fraud, rules")
    replace(main, '''            code = rules.evaluate_authorization(body.card_number, body.exp_month, body.exp_year, body.amount)''',
            '''            code = rules.evaluate_authorization(body.card_number, body.exp_month, body.exp_year, body.amount)
            if code is ResponseCode.APPROVED and fraud.score(rules.mask_pan(body.card_number), str(body.amount)) > 80:
                code = ResponseCode.DO_NOT_HONOR''')
    with (dst / "requirements.txt").open("a", encoding="utf-8") as handle:
        handle.write("requests==2.25.1\n")


def funcional(dst: Path) -> None:
    rules = dst / "app" / "rules.py"
    replace(rules, "    if amount > MAX_AMOUNT:", "    if amount >= MAX_AMOUNT:")  # F1
    replace(rules, '''    if Decimal(original["amount"]) != amount:
        return ResponseCode.ORIGINAL_AMOUNT_INCORRECT
''', "")  # F2


SCENARIOS = {"vulnerable": vulnerable, "funcional": funcional}


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in SCENARIOS:
        raise SystemExit(__doc__)
    dst = Path(sys.argv[2]).resolve()
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT, dst, ignore=IGNORE)
    SCENARIOS[sys.argv[1]](dst)
    print(f"Escenario '{sys.argv[1]}' creado en {dst}")


if __name__ == "__main__":
    main()
