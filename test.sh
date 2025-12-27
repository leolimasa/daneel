#!/usr/bin/env bash

# test.sh - Run all tests for the daneel project

set -e  # Exit on any error

echo "Running daneel project tests..."
echo "================================"

# Check if pytest is available, if not, enter Nix environment
if ! command -v pytest &> /dev/null; then
    echo "Entering Nix development environment..."
    exec nix develop --command "$0" "$@"
fi

# Set PYTHONPATH to include current directory
export PYTHONPATH=.

echo "Python version: $(python --version)"
echo "pytest version: $(pytest --version)"
echo ""

# Run all tests with verbose output
echo "Running all tests..."
pytest tests/ -v

echo ""
echo "✅ All tests completed successfully!"
