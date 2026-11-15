FROM python:3.11-slim-bookworm
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
COPY app.py ./
COPY assets ./assets
COPY sql ./sql
COPY data/demo ./data/demo
COPY .streamlit ./.streamlit
RUN useradd --create-home dashboard && chown -R dashboard:dashboard /app
USER dashboard
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.headless=true"]
