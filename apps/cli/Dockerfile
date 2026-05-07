FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend:/app/apps/cli

WORKDIR /app

COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY apps/cli/requirements.txt /tmp/cli-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt -r /tmp/cli-requirements.txt

COPY backend/src /app/backend/src
COPY apps/cli /app/apps/cli

CMD ["python", "/app/apps/cli/main.py"]
