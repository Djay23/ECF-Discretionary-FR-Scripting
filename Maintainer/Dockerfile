# ECF Discretionary FR — classification engine
#
# This is now the PRIMARY way to run the tool: "RUN (Docker).bat" /
# run-docker.sh drop someone straight into the same numbered menu RUN.bat
# gives, with no Python install required. RUN.bat (needs a system Python +
# venv) remains as the alternative for people who already have that set up.
# See "HOW TO RUN.md".
#
# The image contains only the code, at /app. The Excel workbooks live outside
# the image entirely and are bind-mounted at /data, so nothing in Taxonomy/,
# Data Sheets/ or Final Review/ is ever baked into the image.

FROM python:3.13-slim

# Engines print unicode arrows and em-dashes in their summaries.
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencies first so code edits don't invalidate the pip layer.
# Core only — the ML extras (requirements-ml.txt) are deliberately excluded:
# they add ~650 MB of packages plus ~1.1 GB of model weights.
COPY Maintainer/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY Engine_1_and_2/ ./Engine_1_and_2/
COPY Maintainer/Tools/ ./Tools/

# The workspace (Data Sheets/, Taxonomy/, Final Review/) is bind-mounted here
# by the host launcher / compose file. Setting ECF_WORKSPACE means paths.py
# resolves straight to the mount instead of inventing a folder inside the
# container that would vanish when it exits.
RUN mkdir /data
ENV ECF_WORKSPACE=/data

# Which dataset to work on: "2025" or "2023_24". Override per run with
#   docker compose run --rm -e ECF_DATASET=2023_24 ecf classify
ENV ECF_DATASET=2025

ENTRYPOINT ["python", "Tools/docker_entrypoint.py"]
# No default command: run with no arguments and docker_entrypoint.py decides
# between the interactive menu (a real terminal is attached) and the help
# text (it isn't). A maintainer overrides this per run, e.g. `... classify`.
CMD []
