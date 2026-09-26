# Airflow 3.3.0 with Python 3.13, matching the Spark workers (docker/spark/Dockerfile)
FROM apache/airflow:3.3.0-python3.13

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    openjdk-17-jre-headless \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for Spark (Java 17 works with Spark 4.0 and 4.1)
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Copy Spark (for spark-submit) from the same image the cluster runs.
# archive.apache.org throttles to ~80KB/s and dlcdn no longer hosts 4.1.0.
ENV SPARK_VERSION=4.1.0
ENV SPARK_HOME=/opt/spark
COPY --from=apache/spark:4.1.0-scala2.13-java21-python3-r-ubuntu --chown=airflow:root /opt/spark ${SPARK_HOME}

ENV PATH="${SPARK_HOME}/bin:${PATH}"

USER airflow

# Install Airflow providers (latest versions compatible with Airflow 3.x).
# pyspark[connect] pulls pandas>=2.2, pyarrow and grpcio; bare pyspark
# leaves the Connect client unimportable inside the image. The spark provider
# pulls an unpinned pyspark-client that shares the `pyspark` package dir, so
# pin it to the same version or the two overwrite each other's files.
# cryptography is above the 3.3.0 constraints (48.0.1) since its open
# advisories are only fixed in 49/50. pyopenssl and gcloud-aio-auth get bumped
# along with it since the constrained versions cap cryptography below 49.
RUN pip install --no-cache-dir \
    apache-airflow-providers-apache-spark==6.2.0 \
    apache-airflow-providers-postgres==6.8.0 \
    apache-airflow-providers-apache-kafka==1.14.0 \
    apache-airflow-providers-docker==4.5.7 \
    apache-airflow-providers-http==6.0.4 \
    "pyspark[connect]==4.1.0" \
    pyspark-client==4.1.0 \
    "cryptography>=50" \
    "pyopenssl>=26.4" \
    "gcloud-aio-auth>=5.5"

# MLflow client for DAG tasks, pinned to the tracking server version. Skinny
# because full mlflow drags in its server deps (SQLAlchemy/alembic), which
# would fight Airflow's own. boto3 is for the S3 artifact uploads.
RUN pip install --no-cache-dir \
    "mlflow-skinny==3.13.0" \
    boto3

# Create directories
RUN mkdir -p /opt/airflow/dags /opt/airflow/logs /opt/airflow/config

WORKDIR /opt/airflow
