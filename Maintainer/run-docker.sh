#!/usr/bin/env bash
# run-docker.sh
# --------------
# The macOS/Linux twin of "RUN (Docker).bat": double-click isn't a thing on a
# terminal, so open a Terminal window in this folder and run
#     bash run-docker.sh
# It gets you the exact same numbered menu as RUN.bat, with no Python install
# needed -- only Docker Desktop.

IMAGE="ecf-discretionary-fr:latest"
BAR="============================================================"

# This script lives in Maintainer/ now, but the build context, the
# "Data Sheets" populated-check and the workspace resolution all need to see
# the REPO ROOT (one level up), not this folder.
cd "$(dirname "$0")/.." || exit 1

# --------------------------------------------------------------------
# Step 1: is Docker installed at all?
# --------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    echo
    echo "$BAR"
    echo "  DOCKER IS NOT INSTALLED"
    echo "$BAR"
    echo
    echo "  This tool needs Docker Desktop, which is free."
    echo
    echo "    1. Go to   https://www.docker.com/products/docker-desktop/"
    echo "    2. Download Docker Desktop for Mac (or your Linux distro's"
    echo "       Docker Engine) and run the installer."
    echo "    3. Start Docker Desktop and wait for the whale icon in the"
    echo "       menu bar to stop animating -- that means it is ready."
    echo "    4. When it finishes, run this script again:"
    echo "           bash run-docker.sh"
    echo
    exit 1
fi

# --------------------------------------------------------------------
# Step 2: is the Docker engine actually running?
# --------------------------------------------------------------------
if ! docker info >/dev/null 2>&1; then
    echo
    echo "$BAR"
    echo "  DOCKER IS NOT RUNNING"
    echo "$BAR"
    echo
    echo "  Docker is installed but does not appear to be running, which"
    echo "  is the most common reason this tool won't start."
    echo
    echo "    1. Open Docker Desktop."
    echo "    2. Wait for the whale icon in the menu bar to stop"
    echo "       animating -- that means it is ready."
    echo "    3. Run this script again:  bash run-docker.sh"
    echo
    exit 1
fi

# --------------------------------------------------------------------
# Step 3: find the workspace -- same rule the rest of the tool uses.
#   1. ECF_WORKSPACE_HOST, if already set.
#   2. This folder itself, if it already has a "Data Sheets" folder with
#      workbooks in it -- an existing install must keep working exactly
#      where it is.
#   3. Otherwise, "ECF Classification" on the Desktop, created if needed.
# --------------------------------------------------------------------
if [ -n "$ECF_WORKSPACE_HOST" ]; then
    WORKSPACE="$ECF_WORKSPACE_HOST"
elif [ -d "Data Sheets" ] && ls "Data Sheets"/*.xlsx >/dev/null 2>&1; then
    WORKSPACE="$(pwd)"
else
    WORKSPACE="$HOME/Desktop/ECF Classification"
    if ! mkdir -p "$WORKSPACE" 2>/dev/null; then
        echo
        echo "$BAR"
        echo "  COULD NOT CREATE THE WORKING FOLDER"
        echo "$BAR"
        echo
        echo "  Tried to create it here:"
        echo "      $WORKSPACE"
        echo
        echo "  This is usually a permissions problem. Check you can write"
        echo "  to your Desktop, then run this script again."
        echo
        exit 1
    fi
fi

# --------------------------------------------------------------------
# Step 4: build the image if this is the first run.
# --------------------------------------------------------------------
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo
    echo "$BAR"
    echo "  FIRST-TIME SETUP"
    echo "$BAR"
    echo
    echo "  Building the tool's Docker image. This happens once and can"
    echo "  take a few minutes depending on your internet connection."
    echo
    if ! docker build -t "$IMAGE" -f Maintainer/Dockerfile .; then
        echo
        echo "$BAR"
        echo "  COULD NOT BUILD THE DOCKER IMAGE"
        echo "$BAR"
        echo
        echo "  This is almost always the internet connection or a"
        echo "  firewall blocking the download."
        echo
        echo "  Check you are online and try again. If you are on a"
        echo "  company network or VPN, it may need to be allowed by IT."
        echo
        exit 1
    fi
    echo
    echo "  Setup complete."
    echo
fi

# --------------------------------------------------------------------
# Step 5: run it. Same numbered menu as RUN.bat.
# --------------------------------------------------------------------
echo
echo "$BAR"
echo "  STARTING THE TOOL"
echo "$BAR"
echo
echo "  Your workbooks folder:"
echo "      $WORKSPACE"
echo

# --user matches files the container writes back to your own account
# instead of root, since the image otherwise runs as root by default.
docker run -it --rm \
    --user "$(id -u):$(id -g)" \
    -v "$WORKSPACE:/data" \
    "$IMAGE"
