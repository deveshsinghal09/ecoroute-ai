ARG PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.11-slim
FROM ${PYTHON_BASE_IMAGE}
WORKDIR /app
COPY requirements-runtime.txt requirements-ml.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements-runtime.txt -r requirements-ml.txt -c requirements.lock awslambdaric==3.1.1
COPY src ./src
COPY scripts/train.py ./scripts/train.py
ENV PYTHONPATH=/app/src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
ENTRYPOINT ["python", "-m", "ecoroute.ml.container"]
CMD ["train"]
