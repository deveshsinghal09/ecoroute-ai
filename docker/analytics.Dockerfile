FROM public.ecr.aws/lambda/python:3.11
COPY docker/analytics-requirements.txt /tmp/requirements.txt
COPY docker/analytics.lock /tmp/constraints.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt -c /tmp/constraints.txt
COPY src/ecoroute ${LAMBDA_TASK_ROOT}/ecoroute
# Obtain from the official RDS truststore, review and place in ignored build/ before building.
COPY build/rds-ca.pem /opt/rds-ca.pem
CMD ["ecoroute.analytics.handler"]
