#!/usr/bin/env python3
"""Ejecutor local del pipeline Código 00.

Reproduce, en una sola máquina, las compuertas que el flujo de GitHub Actions
(.github/workflows/codigo00.yml) ejecuta en la nube. Cada compuerta responde
como un autorizador ISO 8583: "00" si el cambio cumple el criterio y "05" si
no lo cumple. El cambio solo queda listo para desplegar si todas responden 00.

Uso:
    python pipeline/run_pipeline.py --src . --out reports/run-01 --scenario limpio

Variables de entorno opcionales: PYTHON_BIN, NEWMAN_BIN, K6_BIN, ZAP_SH, CHECKOV_BIN, CFNLINT_BIN.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess  # nosec B404
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET  # nosec B405
from datetime import datetime, timezone
from pathlib import Path

PY = os.environ.get("PYTHON_BIN", sys.executable)
BIN_DIR = Path(PY).parent
NEWMAN = os.environ.get("NEWMAN_BIN", "newman")
K6 = os.environ.get("K6_BIN", "k6")
ZAP = os.environ.get("ZAP_SH", "zap.sh")
CHECKOV = os.environ.get("CHECKOV_BIN", "checkov")
CFNLINT = os.environ.get("CFNLINT_BIN", "cfn-lint")

COVERAGE_MIN = 85          # G1: cobertura mínima de líneas y ramas (%)
SAST_BLOCKING = {"MEDIUM", "HIGH"}   # G2: severidades que bloquean
DAST_BLOCKING_RISK = 2     # G6: riesgo ZAP >= 2 (medio) bloquea

TEST_KEYS = {"pipeline-key-a-31f0": "COMERCIO_A", "pipeline-key-b-8c2d": "COMERCIO_B"}


def run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 1200) -> tuple[int, str, float]:
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)  # nosec B603
    return proc.returncode, proc.stdout + proc.stderr, time.perf_counter() - start


def base_env() -> dict:
    env = dict(os.environ)
    env["CODIGO00_API_KEYS"] = json.dumps(TEST_KEYS)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def junit_counts(path: Path) -> dict:
    root = ET.parse(path).getroot()  # nosec B314
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    total = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    failed_names = [
        f"{case.get('classname')}::{case.get('name')}"
        for case in suite.iter("testcase")
        if case.find("failure") is not None or case.find("error") is not None
    ]
    return {"total": total, "passed": total - failures - skipped, "failed": failures, "failed_tests": failed_names}


# --- Compuertas ---------------------------------------------------------------

def gate_tests(src: Path, out: Path) -> dict:
    junit = out / "g1-junit.xml"
    cov_json = out / "g1-coverage.json"
    code, log, secs = run(
        [PY, "-m", "pytest", "tests/unit", "tests/functional", "-p", "no:warnings", "-p", "no:cacheprovider",
         f"--junitxml={junit}", "--cov=app", "--cov-branch", f"--cov-report=json:{cov_json}"],
        src, base_env())
    counts = junit_counts(junit)
    coverage = json.loads(cov_json.read_text())["totals"]["percent_covered"]
    ok = code == 0 and counts["failed"] == 0 and coverage >= COVERAGE_MIN
    return {"ok": ok, "seconds": secs, "metrics": {**counts, "coverage_pct": round(coverage, 1),
                                                     "coverage_min": COVERAGE_MIN}, "log": log}


def gate_sast(src: Path, out: Path) -> dict:
    report = out / "g2-bandit.json"
    _, log, secs = run([str(BIN_DIR / "bandit"), "-r", "app", "-f", "json", "-o", str(report), "-q"], src)
    data = json.loads(report.read_text())
    by_sev = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    findings = []
    for issue in data["results"]:
        by_sev[issue["issue_severity"]] += 1
        findings.append({"id": issue["test_id"], "severity": issue["issue_severity"],
                         "confidence": issue["issue_confidence"], "file": issue["filename"],
                         "line": issue["line_number"], "text": issue["issue_text"]})
    blocking = sum(by_sev[s] for s in SAST_BLOCKING)
    loc = data["metrics"]["_totals"]["loc"]
    return {"ok": blocking == 0, "seconds": secs,
            "metrics": {**{f"sev_{k.lower()}": v for k, v in by_sev.items()}, "blocking": blocking, "loc": loc},
            "findings": findings, "log": log}


def gate_sca(src: Path, out: Path) -> dict:
    report = out / "g3-pip-audit.json"
    sbom = out / "g3-sbom.cdx.json"
    _, log, secs = run([str(BIN_DIR / "pip-audit"), "-r", "requirements.txt", "-f", "json", "-o", str(report),
                        "--progress-spinner", "off"], src)
    _, log2, secs2 = run([str(BIN_DIR / "cyclonedx-py"), "requirements", "requirements.txt",
                          "--of", "JSON", "-o", str(sbom)], src)
    data = json.loads(report.read_text())
    vulns = {}
    for dep in data["dependencies"]:
        for vuln in dep.get("vulns", []):
            vulns[(dep["name"], vuln["id"])] = {"package": dep["name"], "version": dep["version"], "id": vuln["id"],
                                                "aliases": vuln.get("aliases", []), "fix": vuln.get("fix_versions", [])}
    components = len(json.loads(sbom.read_text()).get("components", []))
    unique = list(vulns.values())
    return {"ok": not unique, "seconds": secs + secs2,
            "metrics": {"vulnerabilities": len(unique), "packages_audited": len(data["dependencies"]),
                        "sbom_components": components,
                        "vulnerable_packages": sorted({v["package"] for v in unique})},
            "findings": unique, "log": log + log2}


def gate_iac(src: Path, out: Path) -> dict:
    """G8: la infraestructura como código, el Dockerfile y el flujo de CI deben pasar cfn-lint y Checkov."""
    lint_report = out / "g8-cfn-lint.json"
    code_l, log_l, secs_l = run([CFNLINT, "-f", "json", "infra/codigo00-infra.yaml"], src)
    lint_report.write_text(log_l if log_l.strip().startswith("[") else "[]", encoding="utf-8")
    lint = json.loads(lint_report.read_text())
    lint_errors = [m for m in lint if m.get("Level") == "Error"]
    ck_report = out / "g8-checkov.json"
    _, log_c, secs_c = run([CHECKOV, "-d", ".", "--framework", "cloudformation", "dockerfile", "github_actions",
                            "--skip-download", "--quiet", "-o", "json"], src)
    start = log_c.find("[") if log_c.lstrip().startswith("[") else log_c.find("{")
    data = json.loads(log_c[start:]) if start >= 0 else []
    data = data if isinstance(data, list) else [data]
    ck_report.write_text(json.dumps(data, indent=1), encoding="utf-8")
    passed = sum(r["summary"]["passed"] for r in data)
    failed = sum(r["summary"]["failed"] for r in data)
    skipped = sum(r["summary"]["skipped"] for r in data)
    findings = [{"id": f["check_id"], "name": f["check_name"], "resource": f["resource"], "framework": r["check_type"]}
                for r in data for f in r.get("results", {}).get("failed_checks", [])]
    return {"ok": not lint_errors and failed == 0, "seconds": secs_l + secs_c,
            "metrics": {"cfn_lint_errors": len(lint_errors), "checkov_passed": passed, "checkov_failed": failed,
                        "checkov_skipped": skipped, "failed_ids": sorted({f["id"] for f in findings})},
            "findings": findings, "log": log_l[-2000:]}


def gate_security_tests(src: Path, out: Path) -> dict:
    junit = out / "g5-junit.xml"
    code, log, secs = run([PY, "-m", "pytest", "tests/security", "-m", "security", "-p", "no:warnings",
                           "-p", "no:cacheprovider", f"--junitxml={junit}"], src, base_env())
    counts = junit_counts(junit)
    return {"ok": code == 0 and counts["failed"] == 0, "seconds": secs, "metrics": counts, "log": log}


def gate_contract(src: Path, out: Path, url: str) -> dict:
    report = out / "g4-newman.json"
    code, log, secs = run(
        [NEWMAN, "run", "postman/codigo00.postman_collection.json", "--env-var", f"baseUrl={url}",
         "--env-var", "apiKeyA=pipeline-key-a-31f0", "--env-var", "apiKeyB=pipeline-key-b-8c2d",
         "--reporters", "json", "--reporter-json-export", str(report)], src)
    stats = json.loads(report.read_text())["run"]["stats"]
    failures = json.loads(report.read_text())["run"]["failures"]
    metrics = {"requests": stats["requests"]["total"], "assertions": stats["assertions"]["total"],
               "assertions_failed": stats["assertions"]["failed"],
               "failed": sorted({f["source"]["name"] + ": " + f["error"]["test"] for f in failures})}
    return {"ok": code == 0 and stats["assertions"]["failed"] == 0, "seconds": secs, "metrics": metrics, "log": log}


def gate_dast(src: Path, out: Path, url: str, access_log: Path) -> dict:
    zap_dir = out / "g6-zap"
    zap_dir.mkdir(exist_ok=True)
    home = out / ".zaphome"
    # El plan es una plantilla: ZAP no sustituye variables dentro de las reglas
    # del job "replacer", así que el ejecutor genera el plan concreto.
    plan = (src / "zap" / "plan-dast.yaml").read_text(encoding="utf-8")
    for var, value in {"TARGET_URL": url, "API_KEY": "pipeline-key-a-31f0", "REPORT_DIR": str(zap_dir)}.items():
        plan = plan.replace("${" + var + "}", value)
    rendered = out / "g6-plan.yaml"
    rendered.write_text(plan, encoding="utf-8")
    before = _count_lines(access_log)
    code, log, secs = run([ZAP, "-cmd", "-silent", "-dir", str(home), "-config", "scanner.injectable=19",
                           "-autorun", str(rendered)], src, timeout=1800)
    requests_sent = _count_lines(access_log) - before
    shutil.rmtree(home, ignore_errors=True)
    data = json.loads((zap_dir / "zap-report.json").read_text())
    alerts = []
    for site in data.get("site", []):
        for alert in site.get("alerts", []):
            alerts.append({"name": alert["name"], "risk": int(alert["riskcode"]), "riskdesc": alert["riskdesc"],
                           "count": int(alert["count"]), "pluginid": alert["pluginid"],
                           "uris": sorted({i["uri"] for i in alert.get("instances", [])})[:5]})
    by_risk = {r: sum(1 for a in alerts if a["risk"] == i) for i, r in enumerate(["info", "low", "medium", "high"])}
    blocking = sum(1 for a in alerts if a["risk"] >= DAST_BLOCKING_RISK)
    return {"ok": code == 0 and blocking == 0, "seconds": secs,
            "metrics": {**{f"alerts_{k}": v for k, v in by_risk.items()}, "blocking": blocking,
                        "requests_sent": requests_sent},
            "findings": alerts, "log": log[-4000:]}


def gate_performance(src: Path, out: Path, url: str) -> dict:
    summary = out / "g7-k6.json"
    env = dict(os.environ, BASE_URL=url, API_KEY_A="pipeline-key-a-31f0", SUMMARY_PATH=str(summary))
    code, log, secs = run([K6, "run", "--quiet", "--no-color", "perf/carga_pagos.js"], src, env)
    metrics = json.loads(summary.read_text())["metrics"]
    dur = metrics["http_req_duration"]["values"]
    thresholds_ok = all(t["ok"] for m in metrics.values() for t in m.get("thresholds", {}).values())
    return {"ok": code == 0 and thresholds_ok, "seconds": secs,
            "metrics": {"requests": metrics["http_reqs"]["values"]["count"],
                        "rps": round(metrics["http_reqs"]["values"]["rate"], 1),
                        "p95_ms": round(dur["p(95)"], 2), "p90_ms": round(dur["p(90)"], 2),
                        "avg_ms": round(dur["avg"], 2), "max_ms": round(dur["max"], 2),
                        "error_rate": metrics["http_req_failed"]["values"]["rate"],
                        "checks_rate": metrics["checks"]["values"]["rate"],
                        "thresholds_ok": thresholds_ok},
            "log": log[-3000:]}


# --- Servicio bajo prueba -----------------------------------------------------

def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", errors="ignore") as handle:
        return sum(1 for line in handle if "HTTP/1.1" in line)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Service:
    def __init__(self, src: Path, out: Path) -> None:
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.access_log = out / "service-access.log"
        env = base_env()
        env["CODIGO00_DB"] = str(out / "service.db")
        env["CODIGO00_ENABLE_DOCS"] = "1"  # entorno de pruebas: expone el contrato para ZAP
        self._log = self.access_log.open("w")
        self.proc = subprocess.Popen(  # nosec B603
            [str(BIN_DIR / "uvicorn"), "app.main:app", "--host", "127.0.0.1", "--port", str(self.port),
             "--no-server-header", "--log-level", "info"],
            cwd=src, env=env, stdout=self._log, stderr=subprocess.STDOUT)
        self._wait_ready()

    def _wait_ready(self) -> None:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=1) as resp:  # nosec B310
                    if resp.status == 200:
                        return
            except OSError:
                time.sleep(0.3)
        raise RuntimeError("El servicio no respondió a /health")

    def stop(self) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=10)
        self._log.close()


# --- Orquestación -------------------------------------------------------------

GATES = [
    ("G1", "Pruebas unitarias y funcionales + cobertura", "estatica"),
    ("G2", "Análisis estático de seguridad (SAST, Bandit)", "estatica"),
    ("G3", "Análisis de dependencias (SCA, pip-audit) + SBOM", "estatica"),
    ("G5", "Pruebas de seguridad de la lógica de negocio", "estatica"),
    ("G8", "Seguridad de la infraestructura como código (cfn-lint + Checkov)", "estatica"),
    ("G4", "Pruebas de contrato de la API (Newman)", "dinamica"),
    ("G6", "Análisis dinámico de seguridad (DAST, OWASP ZAP)", "dinamica"),
    ("G7", "Pruebas de rendimiento (k6)", "dinamica"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", default=".", type=Path)
    parser.add_argument("--out", default="reports/latest", type=Path)
    parser.add_argument("--scenario", default="local")
    parser.add_argument("--fail-fast", action="store_true", help="detenerse en la primera compuerta 05")
    args = parser.parse_args()

    src = args.src.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    results = []
    service = None
    elapsed_first_failure = None

    try:
        for gate_id, name, kind in GATES:
            if kind == "dinamica" and service is None:
                service = Service(src, out)
            print(f"[{gate_id}] {name} ...", flush=True)
            if gate_id == "G1":
                result = gate_tests(src, out)
            elif gate_id == "G2":
                result = gate_sast(src, out)
            elif gate_id == "G3":
                result = gate_sca(src, out)
            elif gate_id == "G5":
                result = gate_security_tests(src, out)
            elif gate_id == "G8":
                result = gate_iac(src, out)
            elif gate_id == "G4":
                result = gate_contract(src, out, service.url)
            elif gate_id == "G6":
                result = gate_dast(src, out, service.url, service.access_log)
            else:
                result = gate_performance(src, out, service.url)
            code = "00" if result["ok"] else "05"
            (out / f"{gate_id.lower()}.log").write_text(result.pop("log", ""), encoding="utf-8")
            results.append({"gate": gate_id, "name": name, "kind": kind, "code": code,
                            "seconds": round(result["seconds"], 2), **{k: v for k, v in result.items()
                                                                        if k not in ("ok", "seconds")}})
            print(f"      → {code} ({result['seconds']:.1f} s) {json.dumps(result.get('metrics', {}), ensure_ascii=False)}",
                  flush=True)
            if code != "00" and elapsed_first_failure is None:
                elapsed_first_failure = round(time.perf_counter() - t0, 2)
                if args.fail_fast:
                    break
    finally:
        if service:
            service.stop()

    overall = "00" if all(r["code"] == "00" for r in results) and len(results) == len(GATES) else "05"
    summary = {
        "scenario": args.scenario,
        "started_at": started.isoformat(timespec="seconds"),
        "total_seconds": round(time.perf_counter() - t0, 2),
        "seconds_to_first_failure": elapsed_first_failure,
        "overall_code": overall,
        "deploy": "Listo para desplegar" if overall == "00" else "Despliegue bloqueado",
        "gates": results,
        "tools": tool_versions(),
    }
    (out / "results.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_html(summary, out / "reporte.html")
    print(f"\nResultado global: {overall} — {summary['deploy']} ({summary['total_seconds']} s)")
    return 0 if overall == "00" else 1


def tool_versions() -> dict:
    def version(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip().splitlines()[0]  # nosec B603
        except (OSError, IndexError, subprocess.TimeoutExpired):
            return "n/d"
    return {
        "python": sys.version.split()[0],
        "pytest": version([PY, "-m", "pytest", "--version"]),
        "bandit": version([str(BIN_DIR / "bandit"), "--version"]),
        "pip-audit": version([str(BIN_DIR / "pip-audit"), "--version"]),
        "newman": version([NEWMAN, "--version"]),
        "k6": version([K6, "version"]),
        "zap": "2.17.0",
        "checkov": version([CHECKOV, "--version"]),
        "cfn-lint": version([CFNLINT, "--version"]),
    }


def write_html(summary: dict, path: Path) -> None:
    rows = "".join(
        f"<tr class='c{r['code']}'><td>{r['gate']}</td><td>{r['name']}</td><td><b>{r['code']}</b></td>"
        f"<td>{r['seconds']}</td><td><code>{json.dumps(r.get('metrics', {}), ensure_ascii=False)}</code></td></tr>"
        for r in summary["gates"])
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Código 00 — Reporte de compuertas</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;color:#1f2933}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #cbd2d9;padding:.4rem;text-align:left;font-size:.9rem;vertical-align:top}}
.c00 td:nth-child(3){{color:#0b7a3e}}.c05 td:nth-child(3){{color:#b42318}}code{{font-size:.8rem;white-space:pre-wrap}}</style>
</head><body><h1>Código 00 — Reporte de compuertas</h1>
<p>Escenario: <b>{summary['scenario']}</b> · Inicio: {summary['started_at']} · Duración: {summary['total_seconds']} s</p>
<h2>Resultado global: {summary['overall_code']} — {summary['deploy']}</h2>
<table><tr><th>Compuerta</th><th>Descripción</th><th>Código</th><th>Segundos</th><th>Métricas</th></tr>{rows}</table>
</body></html>"""
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
