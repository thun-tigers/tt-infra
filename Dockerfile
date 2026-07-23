FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Docker-CLI + Compose-Plugin (kein Daemon) fuer die Ops-Buttons (/ops/apply,
# /ops/restart), die ueber den gemounteten Docker-Socket generate-env.sh/
# deploy.sh auf dem Host anstossen - offizielles Docker-Apt-Repo, funktioniert
# automatisch fuer amd64 und arm64.
RUN apt-get update && apt-get install -y ca-certificates gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
ARG TT_COMMON_REF=v0.2.2
RUN sed -i "s#@v[0-9][0-9.]*#@${TT_COMMON_REF}#" requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/instance
# Laeuft bewusst als root (kein USER-Wechsel): der gemountete Docker-Socket
# (/ops/apply, /ops/restart) macht den Container ohnehin root-aequivalent auf
# dem Host, ein separater appuser wuerde daran nichts aendern, aber je nach
# Host-GID des Sockets (macOS Docker Desktop vs. Linux-VPS) brechen.

ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Zurich

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
