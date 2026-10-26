FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

USER 10001

# Container Apps pick their worker via WORKER_MODULE, so the placeholder image needs no command.
CMD ["sh", "-c", "exec python -m ${WORKER_MODULE:-calacat_narrator.agent_worker}"]
