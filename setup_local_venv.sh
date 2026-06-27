#!/usr/bin/env bash
# =============================================================================
# setup_local_venv.sh
#
# Creates a local Python virtual environment inside backend/.venv so that
# PyCharm can find all project packages and stop showing import errors.
#
# This venv is for IDE intelligence ONLY — the actual running app still uses
# Docker.  Run this once after cloning, and whenever requirements.txt changes.
#
# Usage:
#   cd DocuTrust-Rag-main
#   bash setup_local_venv.sh
# =============================================================================

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/backend" && pwd)"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON="${PYTHON:-python3.11}"   # override with: PYTHON=python3.10 bash setup_local_venv.sh

echo "▶ Creating virtual environment at $VENV_DIR …"
"$PYTHON" -m venv "$VENV_DIR"

echo "▶ Upgrading pip …"
"$VENV_DIR/bin/pip" install --upgrade pip

echo "▶ Installing CPU-only PyTorch (avoids pulling CUDA build) …"
"$VENV_DIR/bin/pip" install \
    torch==2.3.0 \
    --index-url https://download.pytorch.org/whl/cpu

echo "▶ Installing project dependencies …"
"$VENV_DIR/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

echo ""
echo "✅  Done!  Virtual environment is ready at: $VENV_DIR"
echo ""
echo "Next steps in PyCharm:"
echo "  1. File → Settings → Project → Python Interpreter"
echo "  2. Click ⚙️  → Add Interpreter → Add Local Interpreter"
echo "  3. Choose 'Existing' and browse to:"
echo "     $VENV_DIR/bin/python"
echo "  4. Click OK — PyCharm will index the packages and import errors will disappear."
echo ""
echo "Re-run this script any time you update requirements.txt."