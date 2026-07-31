# ECF Discretionary FR — classification engine
#
# This is the reproducible/server-side path. Day-to-day use by non-technical
# staff goes through RUN.bat instead; see "HOW TO RUN.md".
#
# The image contains only the code and its dependencies. The Excel workbooks
# stay on the host and are bind-mounted at /work, so nothing in Taxonomy/,
# Data Sheets/ or Post Review/ is ever baked into the image.

FROM python:3.13-slim

# Engines print unicode arrows and em-dashes in their summaries.
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /work

# Dependencies first so code edits don't invalidate the pip layer.
# Core only — the ML extras (requirements-ml.txt) are deliberately excluded:
# they add ~650 MB of packages plus ~1.1 GB of model weights.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY Engine_1_and_2/ ./Engine_1_and_2/
COPY Tools/ ./Tools/

# Which dataset to work on: "2025" or "2023_24". Override per run with
#   docker compose run --rm -e ECF_DATASET=2023_24 ecf classify
ENV ECF_DATASET=2025

ENTRYPOINT ["python", "Tools/docker_entrypoint.py"]
CMD ["help"]
