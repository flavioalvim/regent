#!/usr/bin/env bash
# Fail-closed packaging gate (PLAN-001 STEP-04): full test suite, sdist+wheel
# build and twine metadata check, with exit codes preserved. Creates/reuses a
# dedicated .venv-dev with the build tooling.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHONPATH=src python3 -m unittest discover -s tests

if [ ! -x .venv-dev/bin/python ]; then
    python3 -m venv .venv-dev
fi
.venv-dev/bin/python -m pip show build twine >/dev/null 2>&1 \
    || .venv-dev/bin/python -m pip install --quiet build twine

rm -rf dist build
.venv-dev/bin/python -m build
.venv-dev/bin/python -m twine check --strict dist/*
rm -rf build
echo "gate-package: OK"
