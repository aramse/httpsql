FROM python:2.7.18

RUN pip install web.py
RUN pip install jsonschema
RUN pip install psycopg2
RUN pip install prometheus_client
RUN pip install cassandra-driver

WORKDIR /app
COPY . .

CMD exec python -u serve.py
