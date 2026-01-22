FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY integrations/ ./integrations/
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 9753
CMD ["uv", "run", "python", "run.py", "--host", "0.0.0.0", "--port", "9753"]
