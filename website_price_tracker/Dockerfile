ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

# Systeempakketten (geen pip-upgrade in systeem-Python i.v.m. PEP 668)
RUN apk add --no-cache python3 py3-pip jq

WORKDIR /app
# requirements eerst kopiëren voor betere layer-caching
COPY app/requirements.txt /app/requirements.txt

# Maak een geïsoleerde venv en gebruik die voor pip
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Pip binnen de venv (hier mag je wel upgraden/installeren)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r /app/requirements.txt

# App code + s6 services
COPY app /app
COPY rootfs/ /

ENV PYTHONUNBUFFERED=1
