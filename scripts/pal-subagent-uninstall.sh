#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# PAL Subagent - Uninstall Script
#
# Interactively removes, item by item:
#   1. Claude Code MCP registration (pal)
#   2. Codex CLI [mcp_servers.pal] config section
#   3. Conda environment
#   4. Cloned PAL MCP Server repository
#
# Each item is confirmed before removal. Answering "no" (default)
# skips that item.
#
# Usage:
#   pal-subagent-uninstall.sh [--env-name NAME]
# ============================================================


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

DEFAULT_ENV_NAME="pal-mcp-server"
CLAUDE_MCP_NAME="pal"
REPO_DIR_NAME="pal-mcp-server"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "${SCRIPT_DIR}")"
REPO_DIR="${SKILL_DIR}/${REPO_DIR_NAME}"

CODEX_CONFIG="${HOME}/.codex/config.toml"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

info() {
    echo
    echo "==> $1"
}

success() {
    echo "✓ $1"
}

error() {
    echo "✗ $1" >&2
}

skip() {
    echo "- $1 (skipped)"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ask "question" -> returns 0 on yes, 1 on no/EOF
ask() {
    local answer
    read -r -p "$1 [y/N]: " answer || answer=""
    answer="${answer,,}"
    [[ "${answer}" == "y" || "${answer}" == "yes" ]]
}

usage() {
    cat <<EOF
Usage: $(basename "$0") [--env-name NAME]

Options:
  --env-name NAME   Conda environment to consider removing (default: ${DEFAULT_ENV_NAME})
  -h, --help        Show this help message

Note: this script is interactive. Run it in a terminal.
EOF
}


# ------------------------------------------------------------
# Parse arguments
# ------------------------------------------------------------

ENV_NAME="${DEFAULT_ENV_NAME}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-name)
            if [[ $# -lt 2 ]]; then
                error "--env-name requires a value."
                usage
                exit 1
            fi
            ENV_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done


# ------------------------------------------------------------
# Precheck
# ------------------------------------------------------------

if [[ ! -t 0 ]]; then
    error "This uninstall script is interactive and requires a terminal (TTY)."
    echo
    echo "Alternatively remove items manually, see references/uninstall-guide.md"
    exit 1
fi

echo
echo "PAL Subagent uninstall"
echo "======================"
echo "The following items will be confirmed one by one:"
echo "  1. Claude Code MCP registration (${CLAUDE_MCP_NAME})"
echo "  2. Codex MCP section in ${CODEX_CONFIG}"
echo "  3. Conda environment (${ENV_NAME})"
echo "  4. Cloned repository (${REPO_DIR})"
echo


# ------------------------------------------------------------
# 1. Claude Code MCP
# ------------------------------------------------------------

info "Item 1/4: Claude Code MCP"

if ! command_exists claude; then
    skip "Claude Code not installed"
else
    if claude mcp get "${CLAUDE_MCP_NAME}" -s user >/dev/null 2>&1; then
        if ask "Remove Claude MCP '${CLAUDE_MCP_NAME}'?"; then
            claude mcp remove "${CLAUDE_MCP_NAME}" -s user
            success "Claude MCP '${CLAUDE_MCP_NAME}' removed"
        else
            skip "Claude MCP registration kept"
        fi
    else
        skip "Claude MCP '${CLAUDE_MCP_NAME}' not registered"
    fi
fi


# ------------------------------------------------------------
# 2. Codex MCP section
# ------------------------------------------------------------

info "Item 2/4: Codex MCP configuration"

if [[ ! -f "${CODEX_CONFIG}" ]]; then
    skip "Codex config not found: ${CODEX_CONFIG}"
elif grep -q '^\[mcp_servers\.pal\]' "${CODEX_CONFIG}"; then
    if ask "Remove [mcp_servers.pal] section from ${CODEX_CONFIG}?"; then

        BACKUP="${CODEX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "${CODEX_CONFIG}" "${BACKUP}"
        success "Codex config backed up: ${BACKUP}"

        python3 - "${CODEX_CONFIG}" <<'PY'
import sys
from pathlib import Path

import re

config_path = Path(sys.argv[1])
text = config_path.read_text()

section_start = "[mcp_servers.pal]"

if section_start in text:
    start = text.index(section_start)

    remainder = text[start + len(section_start):]

    match = re.search(r"\n\[[^\]]+\]", remainder)

    if match:
        end = start + len(section_start) + match.start() + 1
    else:
        end = len(text)

    text = (text[:start] + text[end:]).rstrip() + "\n"

    config_path.write_text(text)
    print(f"Removed section, updated: {config_path}")
else:
    print("Section not found, nothing changed.")
PY

        success "Codex MCP section removed"
    else
        skip "Codex config kept"
    fi
else
    skip "No [mcp_servers.pal] section in ${CODEX_CONFIG}"
fi


# ------------------------------------------------------------
# 3. Conda environment
# ------------------------------------------------------------

info "Item 3/4: Conda environment"

if ! command_exists conda; then
    skip "conda not installed"
else
    read -r -p "Conda environment to remove [${ENV_NAME}]: " input_env || input_env=""
    ENV_NAME="${input_env:-${ENV_NAME}}"

    if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
        if ask "Remove conda environment '${ENV_NAME}'? This cannot be undone."; then
            conda env remove -n "${ENV_NAME}" -y
            success "Conda environment '${ENV_NAME}' removed"
        else
            skip "Conda environment kept"
        fi
    else
        skip "Conda environment '${ENV_NAME}' does not exist"
    fi
fi


# ------------------------------------------------------------
# 4. Cloned repository
# ------------------------------------------------------------

info "Item 4/4: Cloned repository"

if [[ -d "${REPO_DIR}" ]]; then
    if ask "Remove cloned repository '${REPO_DIR}'?"; then
        rm -rf "${REPO_DIR}"
        success "Repository removed"
    else
        skip "Repository kept"
    fi
else
    skip "Repository not found: ${REPO_DIR}"
fi


# ------------------------------------------------------------
# Done
# ------------------------------------------------------------

echo
echo "============================================================"
echo "PAL Subagent uninstall finished"
echo "============================================================"
echo
echo "Restart your CLI session if any MCP registration was removed."
echo "Codex config backups (if any) remain in ${HOME}/.codex/."
echo "============================================================"
