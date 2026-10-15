"""Genera la colección Postman de pruebas de contrato (compuerta G4).

Se mantiene como script para que la colección sea legible en el repositorio y
fácil de regenerar. Salida: postman/codigo00.postman_collection.json
"""

import json
from pathlib import Path

TX_SCHEMA = {
    "type": "object",
    "required": ["transaction_id", "type", "response_code", "response_message", "approved",
                 "status", "amount", "currency", "created_at"],
    "properties": {
        "transaction_id": {"type": "string", "pattern": "^[0-9a-f-]{36}$"},
        "type": {"enum": ["AUTHORIZATION", "REVERSAL"]},
        "response_code": {"type": "string", "pattern": "^[0-9]{2}$"},
        "response_message": {"type": "string"},
        "approved": {"type": "boolean"},
        "status": {"enum": ["APPROVED", "DECLINED", "REVERSED"]},
        "amount": {"type": "string"},
        "currency": {"enum": ["COP", "USD"]},
        "masked_pan": {"type": ["string", "null"], "pattern": "^[0-9]{6}\\*+[0-9]{4}$"},
        "auth_code": {"type": ["string", "null"]},
        "created_at": {"type": "string"},
    },
}

COMMON_TESTS = [
    "pm.test('Tiempo de respuesta < 500 ms', () => pm.expect(pm.response.responseTime).to.be.below(500));",
    "pm.test('Cabeceras de seguridad presentes', () => {",
    "  ['X-Content-Type-Options','X-Frame-Options','Content-Security-Policy','Cache-Control']",
    "    .forEach(h => pm.response.to.have.header(h));",
    "});",
    "pm.test('No expone el PAN completo', () => pm.expect(pm.response.text()).to.not.include('4111111111111111'));",
]


def card_body(card="4111111111111111", amount="150000.00", exp_year="{{expYear}}", stan="{{$randomStan}}"):
    return (
        "{\n"
        f'  "card_number": "{card}",\n'
        '  "exp_month": 12,\n'
        f'  "exp_year": {exp_year},\n'
        f'  "amount": "{amount}",\n'
        '  "currency": "COP",\n'
        f'  "stan": "{stan}"\n'
        "}"
    )


def request(name, method, path, tests, body=None, key="{{apiKeyA}}", prerequest=None):
    headers = [{"key": "Content-Type", "value": "application/json"}]
    if key is not None:
        headers.append({"key": "X-API-Key", "value": key})
    item = {
        "name": name,
        "request": {
            "method": method,
            "header": headers,
            "url": {"raw": "{{baseUrl}}" + path, "host": ["{{baseUrl}}"], "path": [p for p in path.split("/") if p]},
        },
        "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": COMMON_TESTS + tests}}],
    }
    if body:
        item["request"]["body"] = {"mode": "raw", "raw": body}
    pre = ["pm.variables.set('$randomStan', String(Math.floor(100000 + Math.random() * 900000)));"]
    if prerequest:
        pre += prerequest
    item["event"].insert(0, {"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre}})
    return item


def expect_code(code, http=201):
    return [
        f"pm.test('HTTP {http}', () => pm.response.to.have.status({http}));",
        f"pm.test('Código de respuesta {code}', () => pm.expect(pm.response.json().response_code).to.eql('{code}'));",
        "pm.test('Cumple el contrato', () => pm.response.to.have.jsonSchema(pm.collectionVariables.get('txSchema') ? JSON.parse(pm.collectionVariables.get('txSchema')) : {}));",
    ]


items = [
    request("01 Salud del servicio", "GET", "/health",
            ["pm.test('HTTP 200', () => pm.response.to.have.status(200));",
             "pm.test('status ok', () => pm.expect(pm.response.json().status).to.eql('ok'));"], key=None),
    request("02 Autorización aprobada (00)", "POST", "/v1/authorizations",
            expect_code("00") + [
                "const r = pm.response.json();",
                "pm.test('Código de autorización de 6 dígitos', () => pm.expect(r.auth_code).to.match(/^\\d{6}$/));",
                "pm.test('PAN enmascarado', () => pm.expect(r.masked_pan).to.eql('411111******1111'));",
                "pm.collectionVariables.set('txId', r.transaction_id);",
                "pm.collectionVariables.set('fixedStan', r.stan);",
            ], body=card_body()),
    request("03 STAN duplicado (94)", "POST", "/v1/authorizations", expect_code("94"),
            body=card_body(stan="{{fixedStan}}")),
    request("04 Fondos insuficientes (51)", "POST", "/v1/authorizations", expect_code("51"),
            body=card_body(card="4000000000009995")),
    request("05 No aprobada por emisor (05)", "POST", "/v1/authorizations", expect_code("05"),
            body=card_body(card="4000000000000002")),
    request("06 Tarjeta vencida (54)", "POST", "/v1/authorizations", expect_code("54"),
            body=card_body(exp_year="2020")),
    request("07 Número de tarjeta inválido (14)", "POST", "/v1/authorizations", expect_code("14"),
            body=card_body(card="4111111111111112")),
    request("08 Monto inválido (13)", "POST", "/v1/authorizations", expect_code("13"),
            body=card_body(amount="0")),
    request("09 Excede el tope (61)", "POST", "/v1/authorizations", expect_code("61"),
            body=card_body(amount="10000000.01")),
    request("10 Consulta propia", "GET", "/v1/transactions/{{txId}}",
            ["pm.test('HTTP 200', () => pm.response.to.have.status(200));",
             "pm.test('Es la misma transacción', () => pm.expect(pm.response.json().transaction_id).to.eql(pm.collectionVariables.get('txId')));"]),
    request("11 Consulta de otro comercio (BOLA)", "GET", "/v1/transactions/{{txId}}",
            ["pm.test('HTTP 404 para transacción ajena', () => pm.response.to.have.status(404));"], key="{{apiKeyB}}"),
    request("12 Reverso con monto distinto (64)", "POST", "/v1/reversals", expect_code("64"),
            body='{\n  "original_transaction_id": "{{txId}}",\n  "amount": "1.00"\n}'),
    request("13 Reverso aprobado (00)", "POST", "/v1/reversals",
            expect_code("00") + ["pm.test('Tipo REVERSAL', () => pm.expect(pm.response.json().type).to.eql('REVERSAL'));"],
            body='{\n  "original_transaction_id": "{{txId}}",\n  "amount": "150000.00"\n}'),
    request("14 Reverso doble (12)", "POST", "/v1/reversals", expect_code("12"),
            body='{\n  "original_transaction_id": "{{txId}}",\n  "amount": "150000.00"\n}'),
    request("15 Estado REVERSED tras el reverso", "GET", "/v1/transactions/{{txId}}",
            ["pm.test('Estado REVERSED', () => pm.expect(pm.response.json().status).to.eql('REVERSED'));"]),
    request("16 Sin llave de API (401)", "POST", "/v1/authorizations",
            ["pm.test('HTTP 401', () => pm.response.to.have.status(401));"], body=card_body(), key=None),
    request("17 Moneda no soportada (422)", "POST", "/v1/authorizations",
            ["pm.test('HTTP 422', () => pm.response.to.have.status(422));"],
            body=card_body().replace('"COP"', '"EUR"')),
]

collection = {
    "info": {
        "name": "Código 00 — Pruebas de contrato",
        "description": "Compuerta G4: valida contrato, códigos de respuesta y reglas de negocio de la API.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [
        {"key": "baseUrl", "value": "http://127.0.0.1:8000"},
        {"key": "apiKeyA", "value": ""},
        {"key": "apiKeyB", "value": ""},
        {"key": "expYear", "value": "2030"},
        {"key": "txSchema", "value": json.dumps(TX_SCHEMA)},
    ],
    "item": items,
}

out = Path(__file__).with_name("codigo00.postman_collection.json")
out.write_text(json.dumps(collection, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Colección generada: {out} ({len(items)} solicitudes)")
