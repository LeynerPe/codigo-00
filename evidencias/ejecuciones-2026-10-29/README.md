# Evidencias de las 16 ejecuciones oficiales (29 de octubre de 2026)

Evaluación final del informe. Ejecuciones del pipeline local (`pipeline/run_pipeline.py`) sobre el commit
`2011327`, con Bandit y Semgrep en G2. Los escenarios con defectos se
generan con `demo/inyectar.py` (`vulnerable`, `funcional` e `infraestructura`) sobre una copia del repositorio.
G9 (Trivy) necesita Docker y se ejecuta solo en GitHub Actions, por lo que no aparece en estas ejecuciones.

Cada carpeta contiene `results.json` (código, duración y métricas de cada compuerta),
`reporte.html` (reporte consolidado), los reportes JUnit y de cobertura (G1, G5), Bandit y Semgrep (G2),
pip-audit y la SBOM CycloneDX (G3), Newman (G4), ZAP (G6), k6 (G7), cfn-lint y Checkov (G8) y el
registro de cada compuerta (`gN.log`). Se omitieron la base de datos temporal, el registro de acceso
del servicio de pruebas y el plan de ZAP generado (que incluye la llave de API de prueba).

| Ejecución | Escenario | Global | Total (s) | Compuertas |
|---|---|---|---|---|
| `funcional-01` | funcional | **05** | 96.9 | G1 05 · G2 00 · G3 00 · G5 05 · G8 00 · G4 05 · G6 00 · G7 00 |
| `funcional-02` | funcional | **05** | 95.9 | G1 05 · G2 00 · G3 00 · G5 05 · G8 00 · G4 05 · G6 00 · G7 00 |
| `funcional-03` | funcional | **05** | 97.6 | G1 05 · G2 00 · G3 00 · G5 05 · G8 00 · G4 05 · G6 00 · G7 00 |
| `infraestructura-01` | infraestructura | **05** | 98.1 | G1 00 · G2 00 · G3 00 · G5 00 · G8 05 · G4 00 · G6 00 · G7 00 |
| `infraestructura-02` | infraestructura | **05** | 96.5 | G1 00 · G2 00 · G3 00 · G5 00 · G8 05 · G4 00 · G6 00 · G7 00 |
| `infraestructura-03` | infraestructura | **05** | 97.5 | G1 00 · G2 00 · G3 00 · G5 00 · G8 05 · G4 00 · G6 00 · G7 00 |
| `limpio-01` | limpio | **00** | 97.9 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `limpio-02` | limpio | **00** | 101.3 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `limpio-03` | limpio | **00** | 99.6 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `limpio-04` | limpio | **00** | 98.0 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `limpio-05` | limpio | **00** | 98.6 | G1 00 · G2 00 · G3 00 · G5 00 · G8 00 · G4 00 · G6 00 · G7 00 |
| `vulnerable-01` | vulnerable | **05** | 102.4 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |
| `vulnerable-02` | vulnerable | **05** | 105.7 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 05 · G6 05 · G7 00 |
| `vulnerable-03` | vulnerable | **05** | 97.0 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |
| `vulnerable-04` | vulnerable | **05** | 97.2 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |
| `vulnerable-05` | vulnerable | **05** | 99.2 | G1 00 · G2 05 · G3 05 · G5 05 · G8 00 · G4 00 · G6 05 · G7 00 |

00 = aprobada; 05 = rechazada.

En `vulnerable-02`, G4 respondió 05 porque la primera autorización tardó 2.277 ms y no cumplió la
aserción de tiempo de respuesta (< 500 ms) del contrato; las otras 94 aserciones aprobaron. Fue una
demora transitoria del equipo de pruebas y no cambió el resultado global (sección 10.2 del informe).
