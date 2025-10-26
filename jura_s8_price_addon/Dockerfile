ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip jq &&     python3 -m pip install --no-cache-dir --upgrade pip

WORKDIR /app
COPY app/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt
COPY app /app

COPY rootfs/ /

ENV PYTHONUNBUFFERED=1
