# Spark 4.1 with the MLflow client, for master, worker and Connect.
#
# Under Spark Connect, `mlflow.pyfunc.spark_udf` loads the model inside the
# executors' Python workers straight from `models:/...`, so the workers need
# the MLflow client and the pandas/pyarrow that pandas UDFs run on. Libraries a
# given model needs (sklearn, xgboost, ...) aren't here; add them when a model
# needs them.
FROM apache/spark:4.1.0-scala2.13-java21-python3-r-ubuntu

USER root

# Python UDFs fail with PYTHON_VERSION_MISMATCH unless the workers run the same
# minor version as the client. The base image ships Ubuntu 22.04's 3.10, so run
# the workers on a uv-managed 3.13 to match the host and Airflow. pyspark itself
# comes from $SPARK_HOME/python, which Spark puts on the workers' path.
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH" \
    PYSPARK_PYTHON=$VIRTUAL_ENV/bin/python \
    PYSPARK_DRIVER_PYTHON=$VIRTUAL_ENV/bin/python

# Skinny to match Airflow and skip MLflow's server deps. Pinned to the tracking
# server version.
RUN uv venv --python 3.13 "$VIRTUAL_ENV" \
    && uv pip install --no-cache \
      "mlflow-skinny==3.13.0" \
      boto3 \
      pandas \
      pyarrow

USER spark
