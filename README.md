# Código 00 — ni un peso sin probar

**Compuertas automatizadas de calidad y seguridad para software de pagos e infraestructura en la nube.**
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
| `infra/codigo00-infra.yaml` | Infraestructura en AWS como código (CloudFormation): VPC, ECR, ECS Fargate, ALB con TLS, WAF, Secrets Manager, KMS y CloudWatch (G8) |
| `.github/workflows/codigo00.yml` | El mismo pipeline en GitHub Actions, con despliegue en AWS |
| `demo/inyectar.py` | Genera los escenarios con defectos inyectados (`vulnerable`, `funcional` e `infraestructura`) |
| `evidencias/` | Resultados de las 16 ejecuciones oficiales del 14 de octubre de 2026 |

## Compuertas

| Id | Compuerta | Herramienta | Criterio para responder 00 |
|---|---|---|---|
| G1 | Pruebas unitarias y funcionales | pytest + coverage | 100 % aprobadas y cobertura ≥ 85 % |
| G2 | SAST | Bandit | 0 hallazgos de severidad media o alta |
| G3 | SCA + SBOM | pip-audit + CycloneDX | 0 vulnerabilidades conocidas |
| G5 | Seguridad de negocio | pytest (`-m security`) | 100 % aprobadas |
| G8 | Infraestructura como código | cfn-lint + Checkov | 0 errores de cfn-lint y 0 controles fallidos de Checkov |
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

# Pipeline completo (requiere newman, k6, OWASP ZAP, cfn-lint y Checkov instalados)
export NEWMAN_BIN=newman K6_BIN=k6 ZAP_SH=/ruta/a/zap.sh CFNLINT_BIN=cfn-lint CHECKOV_BIN=checkov
python pipeline/run_pipeline.py --src . --out reports/limpio --scenario limpio

# Demostración: escenario con vulnerabilidades inyectadas
python demo/inyectar.py vulnerable /tmp/codigo00-vulnerable
python pipeline/run_pipeline.py --src /tmp/codigo00-vulnerable --out reports/vulnerable --scenario vulnerable

# Demostración: plantilla de infraestructura insegura (solo G8 debe responder 05)
python demo/inyectar.py infraestructura /tmp/codigo00-infra
python pipeline/run_pipeline.py --src /tmp/codigo00-infra --out reports/infra --scenario infraestructura
```

Cada ejecución deja en la carpeta `--out` el archivo `results.json`, el reporte `reporte.html` y la
evidencia de cada herramienta (JUnit, Bandit, pip-audit, SBOM, Newman, ZAP, k6, cfn-lint y Checkov).

## Evidencias de la evaluación

Las 16 ejecuciones oficiales (5 limpio, 5 vulnerable, 3 funcional y 3 infraestructura) se hicieron el
14 de octubre de 2026 sobre el commit `7c3fb6f`. Sus resultados están en
[`evidencias/ejecuciones-2026-10-14`](evidencias/ejecuciones-2026-10-14/README.md).

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

El job `desplegar` del workflow publica la imagen en Amazon ECR y despliega la plantilla
`infra/codigo00-infra.yaml` con AWS CloudFormation solo cuando todas las compuertas responden 00 en la
rama `main`. La preparación (certificado, `LabRole` y credenciales de AWS Academy) está en
[`docs/despliegue-aws.md`](docs/despliegue-aws.md).
