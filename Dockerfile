FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock* ./
RUN pip install --upgrade pip && pip install uv && uv sync --frozen

COPY backend/app ./app
COPY backend/.python-version* ./
COPY ./.env* ./

EXPOSE 8000
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
