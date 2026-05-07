FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
COPY apps/cli/requirements.txt /app/cli-requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/cli-requirements.txt

# Reconstruct unified `src/` namespace expected by current imports.
COPY backend/src /app/src
COPY apps/cli/interfaces /app/src/interfaces
COPY apps/cli/dial_interaction /app/src/application/dial_interaction
COPY apps/cli/main.py /app/main.py

CMD ["python", "/app/main.py"]
