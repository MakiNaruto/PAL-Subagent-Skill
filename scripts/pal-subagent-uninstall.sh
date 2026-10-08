#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v conda >/dev/null 2>&1; then
    PAL_SETUP_PYTHON="$(conda info --base)/bin/python"
else
    PAL_SETUP_PYTHON="$(command -v python3 || true)"
fi
if [[ -z "${PAL_SETUP_PYTHON}" ]] || ! "${PAL_SETUP_PYTHON}" -c 'import tomllib' >/dev/null 2>&1; then
    echo 'A bootstrap Python 3.11+ is required (normally supplied by conda base).' >&2
    exit 1
fi
exec "${PAL_SETUP_PYTHON}" "${SCRIPT_DIR}/pal_subagent_setup.py" uninstall "$@"
