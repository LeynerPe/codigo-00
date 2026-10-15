#!/usr/bin/env python3
"""Evalúa el reporte JSON de OWASP ZAP (compuerta G6).

Termina con código 1 si existe al menos una alerta de riesgo medio o alto.
Uso: python pipeline/evaluar_zap.py ruta/zap-report.json
"""

import json
import sys

RISK_NAMES = {0: "informativo", 1: "bajo", 2: "medio", 3: "alto"}


def main(path: str) -> int:
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    blocking = 0
    for site in report.get("site", []):
        for alert in site.get("alerts", []):
            risk = int(alert["riskcode"])
            print(f"[{RISK_NAMES[risk]}] {alert['name']} (regla {alert['pluginid']}, {alert['count']} instancias)")
            blocking += risk >= 2
    print(f"Alertas bloqueantes: {blocking} → {'05 Rechazada' if blocking else '00 Aprobada'}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
