# The live demo (Flask) for docker-compose.yml. Code and models are mounted read-only at run time.
# Separate from the root Dockerfile, which is the clean-container reproduction.
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 MPLBACKEND=Agg
WORKDIR /repo
COPY requirements.txt ./
RUN pip install -r requirements.txt
CMD ["gunicorn", "--chdir", "webapp", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
