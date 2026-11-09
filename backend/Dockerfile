FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Ho_Chi_Minh \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "google-auth[requests]>=2.38.0,<3" \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "sqlalchemy[asyncio]>=2.0.36" \
    "asyncpg>=0.30.0" \
    "alembic>=1.14.0" \
    "pydantic>=2.10.0" \
    "pydantic-settings>=2.6.0" \
    "redis>=5.2.0" \
    "arq>=0.26.1" \
    "httpx>=0.28.0" \
    "argon2-cffi>=23.1.0" \
    "PyJWT>=2.10.0" \
    "cryptography>=44.0.0" \
    "python-multipart>=0.0.17" \
    "email-validator>=2.2.0" \
    "pyotp>=2.9.0" \
    "python-slugify>=8.0.0" \
    "Pillow>=11.0.0" \
    "psutil>=6.1.0,<8"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY entrypoint.sh ./
COPY scripts ./scripts
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
