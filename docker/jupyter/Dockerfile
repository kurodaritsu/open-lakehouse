# JupyterLab on Apache Spark 4.1 (Python 3, Java 21)
# Matches the Spark 4.1 runtime used by the rest of the stack so notebooks
# can execute pyspark 4.1 features (SDP, VARIANT, RTM, etc.) in local mode.
FROM apache/spark:4.1.0-scala2.13-java21-python3-r-ubuntu

USER root

# uv-managed Python 3.13 instead of the base image's 3.10, so notebook UDFs
# match the Spark workers' version (docker/spark/Dockerfile).
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    VIRTUAL_ENV=/opt/jupyter-venv
RUN uv venv --python 3.13 "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN uv pip install --no-cache \
      jupyterlab==4.3.0 \
      ipykernel==6.29.5 \
      pyspark==4.1.0 \
      pandas==2.2.3 \
      pyarrow==18.1.0 \
      matplotlib==3.9.2 \
      "httpx<0.28"   # jupyterlab 4.3 uses httpx AsyncClient(proxies=...) removed in 0.28

ENV JUPYTER_ENABLE_LAB=yes \
    PYSPARK_PYTHON=python3 \
    PYSPARK_DRIVER_PYTHON=python3

WORKDIR /home/jovyan
EXPOSE 8889

CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8889", \
     "--no-browser", \
     "--allow-root", \
     "--ServerApp.token=", \
     "--ServerApp.password=", \
     "--ServerApp.disable_check_xsrf=True"]
