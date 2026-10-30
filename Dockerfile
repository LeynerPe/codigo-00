FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY requirements.txt .
# setuptools y wheel solo sirven para instalar paquetes: se retiran de la imagen final porque Trivy (G9)
# reportó vulnerabilidades HIGH con corrección en wheel 0.45.1 y en jaraco.context 5.3.0 (incluido en setuptools).
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y setuptools wheel

COPY app ./app

# El servicio no corre como root.
RUN useradd --create-home --uid 10001 codigo00
USER codigo00

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
