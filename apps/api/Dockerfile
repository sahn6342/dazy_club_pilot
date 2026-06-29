FROM python:3.12-alpine
RUN pip install uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --frozen --no-dev
COPY . .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
