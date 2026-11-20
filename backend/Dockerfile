FROM python:3.13-slim

WORKDIR /app

ARG APP_REVISION
ENV APP_REVISION=${APP_REVISION}
RUN python -c 'import os, re, sys; re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", os.environ.get("APP_REVISION", "")) or sys.exit("Supply APP_REVISION as the full source Git SHA build argument")'

ARG SUPERCRONIC_VERSION=v0.2.48
ARG SUPERCRONIC_SHA1SUM=016b7c9aebfc8d9fd9526e8ba33b191fc524485f

COPY pyproject.toml ./
COPY backend ./backend

RUN apt-get update \
    && apt-get install --no-install-recommends --yes curl supervisor \
    && curl --fail --silent --show-error --location \
        --output /usr/local/bin/supercronic \
        "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
    && echo "${SUPERCRONIC_SHA1SUM}  /usr/local/bin/supercronic" | sha1sum --check \
    && chmod 0755 /usr/local/bin/supercronic \
    && pip install --no-cache-dir . \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

CMD ["supervisord", "--configuration", "/app/backend/infra/supervisord.conf"]
