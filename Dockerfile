# Week 24-25: clean-container reproduction. Builds from a `git archive` of a commit (no venv, no
# local data beyond what git tracks; Git LFS files arrive as pointers, as in CI) and runs the small
# reproduction. Usage: scripts/v2/docker_repro.sh
# Base image pinned by digest after the first pull (5 Oct 2026); bump deliberately.
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 MPLBACKEND=Agg
WORKDIR /repo
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt
COPY . .
CMD ["sh", "-c", "PY=python sh scripts/v2/reproduce_small.sh"]
