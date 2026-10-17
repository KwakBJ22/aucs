#!/usr/bin/env bash
# 형식·타입·시험을 한 번에 돌립니다.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/rules/src apps/api/src
uv run pytest -q
pnpm --filter web check
echo "검사 통과"
