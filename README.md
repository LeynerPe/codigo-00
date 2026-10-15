# Código 00 — ni un peso sin probar

**Compuertas automatizadas de calidad y seguridad para la entrega continua de software de pagos.**
Proyecto final del Diplomado en Seguridad en DevOps (UNIMINUTO) — Leyner Perea Palma, 2026.

En ISO 8583 el código de respuesta `00` significa *transacción aprobada*. Este repositorio aplica esa
idea al ciclo de entrega: un cambio solo se despliega si **todas** las compuertas responden `00`.
Si alguna responde `05`, el despliegue se bloquea.

## Qué contiene

| Ruta | Contenido |
|---|---|
| `app/` | API de pagos simulada (FastAPI): autorización, reverso y consulta con códigos ISO 8583 |
| `tests/unit`, `tests/functional` | Pruebas unitarias y funcionales (compuerta G1) |
| `tests/security` | Pruebas de seguridad de la lógica de negocio: BOLA, montos, PAN, inyección (G5) |
| `postman/` | Colección de pruebas de contrato para Newman (G4) |
| `zap/plan-dast.yaml` | Plan de automatización de OWASP ZAP (G6) |
| `perf/carga_pagos.js` | Prueba de rendimiento con k6 (G7) |
| `pipeline/run_pipeline.py` | Ejecutor local de todas las compuertas con reporte consolidado |
| `.github/workflows/codigo00.yml` | El mismo pipeline en GitHub Actions, con despliegue en AWS |
| `demo/inyectar.py` | Genera los escenarios con defectos inyectados (vulnerable y funcional) |

## Compuertas

| Id | Compuerta | Herramienta | Criterio para responder 00 |
|---|---|---|---|
| G1 | Pruebas unitarias y funcionales | pytest + coverage | 100 % aprobadas y cobertura ≥ 85 % |
| G2 | SAST | Bandit | 0 hallazgos de severidad media o alta |
| G3 | SCA + SBOM | pip-audit + CycloneDX | 0 vulnerabilidades conocidas |
| G5 | Seguridad de negocio | pytest (`-m security`) | 100 % aprobadas |
| G4 | Contrato de la API | Postman/Newman | 0 aserciones fallidas |
| G6 | DAST | OWASP ZAP | 0 alertas de riesgo medio o alto |
| G7 | Rendimiento | k6 | p95 < 300 ms, errores < 1 % |

## Uso rápido

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# API local
export CODIGO00_API_KEYS='{"mi-llave-a": "COMERCIO_A", "mi-llave-b": "COMERCIO_B"}'
uvicorn app.main:app --reload

# Pruebas
pytest --cov=app

# Pipeline completo (requiere newman, k6 y OWASP ZAP instalados)
export NEWMAN_BIN=newman K6_BIN=k6 ZAP_SH=/ruta/a/zap.sh
python pipeline/run_pipeline.py --src . --out reports/limpio --scenario limpio

# Demostración: escenario con vulnerabilidades inyectadas
python demo/inyectar.py vulnerable /tmp/codigo00-vulnerable
python pipeline/run_pipeline.py --src /tmp/codigo00-vulnerable --out reports/vulnerable --scenario vulnerable
```

Cada ejecución deja en la carpeta `--out` el archivo `results.json`, el reporte `reporte.html` y la
evidencia de cada herramienta (JUnit, Bandit, pip-audit, SBOM, Newman, ZAP y k6).

## Tarjetas de prueba

| PAN | Resultado |
|---|---|
| 4111111111111111 | 00 Aprobada |
| 4000000000000002 | 05 No aprobada |
| 4000000000009995 | 51 Fondos insuficientes |
| Cualquier PAN que no cumpla Luhn | 14 Número de tarjeta inválido |

Otros códigos: 13 monto inválido, 54 tarjeta vencida, 61 excede el tope, 64 monto distinto al
original en un reverso, 12 reverso inválido, 25 transacción original no encontrada, 94 STAN duplicado.

## Despliegue en AWS

El job `desplegar` del workflow publica la imagen en Amazon ECR y actualiza un servicio de Amazon ECS
(Fargate) solo cuando todas las compuertas responden 00 en la rama `main`. La preparación de la cuenta
está en [`docs/despliegue-aws.md`](docs/despliegue-aws.md).
