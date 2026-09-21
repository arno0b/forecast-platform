FROM python:3.13-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.13-slim
RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /install /usr/local
COPY src /app/src
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 
WORKDIR /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "forecast_platform.api:app", "--host", "0.0.0.0", "--port", "8000"]
    

