#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
uv run main.py
