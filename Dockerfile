# Transient image
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV TZ="Europe/Berlin"

ENV UV_PYTHON_DOWNLOADS=0
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE="copy"

WORKDIR /app

COPY . .

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Final image
FROM python:3.13-slim

# Copy the environment, but not the source code
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

EXPOSE 8501

CMD ["/app/.venv/bin/streamlit", "run", "--server.headless", "true","/app/src/xpsh/scripts/app.py"]
