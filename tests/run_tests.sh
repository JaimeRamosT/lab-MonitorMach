#!/bin/bash
# Run integration tests against running Docker services.
# Must be executed from the project root with docker-compose up already running.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing test dependencies..."
pip install pytest requests --quiet

echo ""
echo "Running integration tests..."
python -m pytest "$ROOT/tests/test_services.py" -v "$@"
