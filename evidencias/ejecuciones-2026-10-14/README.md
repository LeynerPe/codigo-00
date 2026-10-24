# Evidencias de las 16 ejecuciones oficiales (14 de octubre de 2026)

Ejecuciones del pipeline local (`pipeline/run_pipeline.py`) sobre el commit etiquetado
`evaluacion-2026-10-14`. Los escenarios con defectos se generan con `demo/inyectar.py`
(`vulnerable`, `funcional` e `infraestructura`) sobre una copia del repositorio.

Cada carpeta contiene `results.json` (código, duración y métricas de cada compuerta),
`reporte.html` (reporte consolidado), los reportes JUnit y de cobertura (G1, G5), Bandit (G2),
pip-audit y la SBOM CycloneDX (G3), Newman (G4), ZAP (G6), k6 (G7), cfn-lint y Checkov (G8) y el
registro de cada compuerta (`gN.log`). Se omitieron la base de datos temporal y el registro de acceso
del servicio de pruebas por su tamaño.

| Ejecución | Escenario | Global | Total (s) | Compuertas |
|---|---|---|---|---|
| `funcional-01` | funcional | **05** | 95.9 | G1 05 · G2 00 · G3 00 · G5 05 · G8 00 · G4 05 · G6 00 · G7 00 |
| `funcional-02` | funcional | **05** | 93.0 | G1 05 · G2 00 · G3 00 · G5 05 · G8 00 · G4 05 · G6 00 · G7 00 |
| `funcional-03` | funcional | **05** | 90.5 | G1 05 · G2 00 · G3 00 · G5 05 · G8 00 · G4 05 · G6 00 · G7 00 |
| `infraestructura-01` | infraestructura | **05** | 92.5 | G1 00 · G2 00 · G3 00 · G5 00 · G8 05 · G4 00 · G6 00 · G7 00 |
| `infraestructura-02` | infraestructura | **05** | 93.2 | G1 00 · G2 00 · G3 00 · G5 00 · G8 05 · G4 00 · G6 00 · G7 00 |
| `infraestructura-03` | infraestructura | **05** | 92.5 | G1 00 · G2 00 · G3 00 · G5 00 · G8 05 · G4 00 · G6 00 · G7 00 |
| `limpio-01` | limpio | **00** | 94.9 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `limpio-02` | limpio | **00** | 96.5 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `limpio-03` | limpio | **00** | 95.3 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `limpio-04` | limpio | **00** | 94.6 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `limpio-05` | limpio | **00** | 93.9 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `vulnerable-01` | vulnerable | **05** | 95.1 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |
| `vulnerable-02` | vulnerable | **05** | 93.0 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |
| `vulnerable-03` | vulnerable | **05** | 92.0 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |
| `vulnerable-04` | vulnerable | **05** | 94.7 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |
| `vulnerable-05` | vulnerable | **05** | 97.3 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |

00 = aprobada; 05 = rechazada.
