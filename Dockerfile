ARG AIRFLOW_VERSION=2.8.1
FROM apache/airflow:${AIRFLOW_VERSION}-python3.11

ARG AIRFLOW_VERSION=2.8.1
ARG DBT_POSTGRES_SPEC=dbt-postgres

# 1. Install project requirements into Airflow (uses default PIP_USER=true)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /tmp/requirements.txt

# 2. Temporarily disable PIP_USER so virtualenv pip install doesn't throw a user-install error
ENV PIP_USER=false
RUN python -m venv /home/airflow/dbt-venv \
 && /home/airflow/dbt-venv/bin/pip install --no-cache-dir ${DBT_POSTGRES_SPEC}
ENV PIP_USER=true

ENV PATH="${PATH}:/home/airflow/dbt-venv/bin"

# 3. Writable cache for the Kaggle archive
RUN mkdir -p /opt/airflow/kagglehub_cache && chmod 775 /opt/airflow/kagglehub_cache