"""Resume el reporte JSON de Trivy (G9) en el resumen del job y en una anotación de GitHub Actions."""

import json
import os
import sys


def main(path: str) -> None:
    data = json.load(open(path, encoding="utf-8"))
    rows = []
    for result in data.get("Results", []):
        for v in result.get("Vulnerabilities") or []:
            rows.append((v["Severity"], v["PkgName"], v.get("InstalledVersion", ""), v.get("FixedVersion", ""),
                         v["VulnerabilityID"], result.get("Type", "")))
    fixable = [r for r in rows if r[3]]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## G9 · Trivy: {len(rows)} vulnerabilidades HIGH/CRITICAL ({len(fixable)} con corrección)\n")
            fh.write("| Severidad | Paquete | Instalada | Corregida en | Id | Tipo |\n|---|---|---|---|---|---|\n")
            for r in rows:
                fh.write("| " + " | ".join(r) + " |\n")
    detail = " ; ".join("|".join(r) for r in rows)
    print(f"::notice title=G9 Trivy {len(rows)} HIGH-CRITICAL, {len(fixable)} con correccion::{detail[:6000]}")


if __name__ == "__main__":
    main(sys.argv[1])
