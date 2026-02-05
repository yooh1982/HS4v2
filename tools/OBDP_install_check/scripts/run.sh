#!/bin/bash
# OBDP Install Check - 실행 진입점
# 설치된 호스트에서 실행 (로컬 또는 해당 서버에서)
# 요구: Python3, PyYAML (pip install pyyaml)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 run_check.py "$@"
