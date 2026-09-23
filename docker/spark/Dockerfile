# Spark 4.1 with the MLflow client, for master, worker and Connect.
#
# Under Spark Connect, `mlflow.pyfunc.spark_udf` loads the model inside the
# executors' Python workers straight from `models:/...`, so the workers need
# the MLflow client and the pandas/pyarrow that pandas UDFs run on. Libraries a
# given model needs (sklearn, xgboost, ...) aren't here; add them when a model
# needs them.
FROM apache/spark:4.1.0-scala2.13-java21-python3-r-ubuntu

USER root

# Skinny to match Airflow and skip MLflow's server deps. Pinned to the tracking
# server version.
RUN pip install --no-cache-dir \
    "mlflow-skinny==3.13.0" \
    boto3 \
    pandas \
    pyarrow

USER spark
