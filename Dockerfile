ARG PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.11-slim
FROM ${PYTHON_BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-runtime.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements-runtime.txt -c requirements.lock \
    && useradd --create-home --uid 10001 appuser \
    && mkdir /app/work && chown appuser:appuser /app/work
COPY src ./src
ENV PYTHONPATH=/app/src
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "ecoroute.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
