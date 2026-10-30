# Evidencias de GitHub Actions (29 de octubre de 2026)

Los artefactos de GitHub Actions (por ejemplo, `g9-trivy.json`) se borran a los 90 días. Esta carpeta conserva,
como texto, lo que se consultó con la API de GitHub para el informe:

| Archivo | Contenido |
|---|---|
| `g9-trivy-ejecucion-5.txt` | Resumen de Trivy (G9) de la ejecución n.º 5 (run 41000644379, commit `0b98d11`): 46 registros HIGH, 2 con corrección (wheel y jaraco.context). G9 respondió 05. |
| `g9-trivy-ejecucion-6.txt` | Resumen de Trivy de la ejecución n.º 6 (run 41000818185, commit `2011327`), con setuptools y wheel retirados de la imagen: 44 registros HIGH sin corrección publicada. G9 respondió 00. |
| `trabajos-ejecucion-6.txt` | Estado de los trabajos de la ejecución n.º 6 y paso en que se detuvo el despliegue (credenciales de AWS). |

Formato de cada fila de Trivy: `severidad|paquete|versión instalada|versión corregida|CVE|tipo`.
