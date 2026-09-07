#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# PAL Subagent - Install Script
#
# 1. Clone PAL MCP Server into the skill directory
# 2. Create / reuse a conda environment (default: pal-mcp-server)
# 3. Install Python dependencies
# 4. Register the MCP server for Claude Code and Codex CLI
#
# Usage:
#   pal-subagent-install.sh [--env-name NAME]
# ============================================================


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

REPO_URL="https://github.com/BeehiveInnovations/pal-mcp-server.git"
REPO_DIR_NAME="pal-mcp-server"

DEFAULT_ENV_NAME="pal-mcp-server"
PYTHON_VERSION="3.12"
CLAUDE_MCP_NAME="pal"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "${SCRIPT_DIR}")"
REPO_DIR="${SKILL_DIR}/${REPO_DIR_NAME}"

CODEX_CONFIG="${HOME}/.codex/config.toml"

# Keep common CLI locations available to PAL.
PAL_PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:${HOME}/.local/bin:${HOME}/.cargo/bin:${HOME}/bin"

ENV_NAME=""


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

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

usage() {
    cat <<EOF
Usage: $(basename "$0") [--env-name NAME]

Options:
  --env-name NAME   Conda environment to create/reuse (skips interactive prompt)
  -h, --help        Show this help message
EOF
}


# ------------------------------------------------------------
# Parse arguments
# ------------------------------------------------------------

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
# 0. Environment name (interactive if not provided)
# ------------------------------------------------------------

if [[ -z "${ENV_NAME}" ]]; then
    if [[ ! -t 0 ]]; then
        ENV_NAME="${DEFAULT_ENV_NAME}"
        info "No TTY detected, using default environment: ${ENV_NAME}"
    else
        read -r -p "Conda environment name [${DEFAULT_ENV_NAME}]: " input_env || input_env=""
        ENV_NAME="${input_env:-${DEFAULT_ENV_NAME}}"
    fi
fi

info "Using conda environment: ${ENV_NAME}"


# ------------------------------------------------------------
# 1. Check conda
# ------------------------------------------------------------

info "Checking conda"

if ! command_exists conda; then
    error "conda was not found."
    echo
    echo "Please install Miniconda/Anaconda first:"
    echo "    https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

success "conda found: $(command -v conda)"


# ------------------------------------------------------------
# 2. Clone / update PAL MCP Server repository
# ------------------------------------------------------------

info "Fetching PAL MCP Server"

if [[ -d "${REPO_DIR}/.git" ]]; then
    success "Repository already exists: ${REPO_DIR}"
    info "Pulling latest changes"
    git -C "${REPO_DIR}" pull --ff-only || {
        error "git pull failed, continuing with existing code."
    }
else
    info "Cloning ${REPO_URL}"
    git clone --depth 1 "${REPO_URL}" "${REPO_DIR}"
    success "Cloned to: ${REPO_DIR}"
fi


# ------------------------------------------------------------
# 3. Check repository contents
# ------------------------------------------------------------

info "Checking PAL MCP Server contents"

SERVER_PY="${REPO_DIR}/server.py"
REQUIREMENTS="${REPO_DIR}/requirements.txt"

if [[ ! -f "${SERVER_PY}" ]]; then
    error "server.py not found: ${SERVER_PY}"
    exit 1
fi

if [[ ! -f "${REQUIREMENTS}" ]]; then
    error "requirements.txt not found: ${REQUIREMENTS}"
    exit 1
fi

success "PAL MCP Server ready: ${REPO_DIR}"


# ------------------------------------------------------------
# 4. Create .env (custom API endpoint for local models)
# ------------------------------------------------------------

info "Configuring .env"

ENV_FILE="${REPO_DIR}/.env"

if [[ -f "${ENV_FILE}" ]]; then
    success ".env already exists, keeping current configuration:"
    echo "    ${ENV_FILE}"
else
    cat > "${ENV_FILE}" <<'ENVEOF'
# Option 3: Use custom API endpoints for local models (Ollama, vLLM, LM Studio, etc.)
CUSTOM_API_URL=http://localhost:11434/v1                # Ollama example
CUSTOM_API_KEY=safe-code                                # Empty for Ollama (no auth needed)
CUSTOM_MODEL_NAME=llama3.2                              # Default model name
ENVEOF
    success "Created .env:"
    echo "    ${ENV_FILE}"
fi


# ------------------------------------------------------------
# 5. Check / create conda environment
# ------------------------------------------------------------

info "Checking conda environment: ${ENV_NAME}"

if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
    success "Conda environment already exists: ${ENV_NAME}"
else
    echo "Creating conda environment..."
    conda create -n "${ENV_NAME}" "python=${PYTHON_VERSION}" -y
    success "Created conda environment: ${ENV_NAME}"
fi


# ------------------------------------------------------------
# 6. Detect Python executable
# ------------------------------------------------------------

info "Detecting Python executable"

CONDA_PYTHON="$(
    conda run \
        --no-capture-output \
        -n "${ENV_NAME}" \
        python -c 'import sys; print(sys.executable)'
)"

if [[ ! -x "${CONDA_PYTHON}" ]]; then
    error "Unable to locate Python executable: ${CONDA_PYTHON}"
    exit 1
fi

success "Python: ${CONDA_PYTHON}"


# ------------------------------------------------------------
# 6. Install dependencies
# ------------------------------------------------------------

info "Installing MCP"

"${CONDA_PYTHON}" -m pip install "mcp>=1.28,<2"

info "Installing PAL dependencies"

"${CONDA_PYTHON}" -m pip install -r "${REQUIREMENTS}"

success "Python dependencies installed"


# ------------------------------------------------------------
# 7. Configure Claude Code MCP
# ------------------------------------------------------------

CLAUDE_OK=0

if command_exists claude; then
    info "Configuring Claude Code MCP"

    # Remove old PAL configuration if it exists.
    claude mcp remove "${CLAUDE_MCP_NAME}" -s user >/dev/null 2>&1 || true

    claude mcp add "${CLAUDE_MCP_NAME}" -s user \
        -e "PATH=${PAL_PATH}" \
        -- \
        "${CONDA_PYTHON}" \
        "${SERVER_PY}"

    success "Claude Code MCP configured"
    CLAUDE_OK=1
else
    error "Claude Code not found, skipping Claude MCP registration."
fi


# ------------------------------------------------------------
# 8. Configure Codex MCP
# ------------------------------------------------------------

CODEX_OK=0

if command_exists codex; then
    info "Configuring Codex MCP"

    mkdir -p "${HOME}/.codex"

    # Backup existing config.
    if [[ -f "${CODEX_CONFIG}" ]]; then
        BACKUP="${CODEX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "${CODEX_CONFIG}" "${BACKUP}"
        success "Codex config backed up: ${BACKUP}"
    else
        touch "${CODEX_CONFIG}"
        success "Created: ${CODEX_CONFIG}"
    fi

    "${CONDA_PYTHON}" - "${CODEX_CONFIG}" "${CONDA_PYTHON}" "${SERVER_PY}" "${REPO_DIR}" "${PAL_PATH}" <<'PY'
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
python_path = sys.argv[2]
server_path = sys.argv[3]
cwd = sys.argv[4]
pal_path = sys.argv[5]

text = config_path.read_text() if config_path.exists() else ""

section_start = "[mcp_servers.pal]"

# Remove an existing [mcp_servers.pal] section.
if section_start in text:
    start = text.index(section_start)

    remainder = text[start + len(section_start):]

    import re

    match = re.search(r"\n\[[^\]]+\]", remainder)

    if match:
        end = start + len(section_start) + match.start() + 1
    else:
        end = len(text)

    text = text[:start] + text[end:]

    text = text.rstrip() + "\n\n"


pal_config = f'''[mcp_servers.pal]
type = "stdio"
command = {python_path!r}
args = [{server_path!r}]
cwd = {cwd!r}
tool_timeout_sec = 1200

[mcp_servers.pal.env]
PATH = {pal_path!r}

'''

text = text.rstrip() + "\n\n" + pal_config

config_path.write_text(text)

print(f"Updated: {config_path}")
PY

    success "Codex MCP configured"
    CODEX_OK=1
else
    error "Codex CLI not found, skipping Codex MCP registration."
fi


# ------------------------------------------------------------
# 9. Result
# ------------------------------------------------------------

if [[ "${CLAUDE_OK}" -eq 0 && "${CODEX_OK}" -eq 0 ]]; then
    error "Neither Claude Code nor Codex CLI was found. Nothing was registered."
    echo
    echo "Install at least one of them, then run this script again:"
    echo "    Claude Code: https://claude.com/claude-code"
    echo "    Codex CLI:   npm install -g @openai/codex"
    exit 1
fi


# ------------------------------------------------------------
# 11. Show final summary
# ------------------------------------------------------------

echo
echo "============================================================"
echo "PAL Subagent setup completed"
echo "============================================================"
echo
echo "Repository:        ${REPO_DIR}"
echo "Conda environment: ${ENV_NAME}"
echo "Python:            ${CONDA_PYTHON}"
echo "PAL Server:        ${SERVER_PY}"
echo "Claude MCP:        $( [[ ${CLAUDE_OK} -eq 1 ]] && echo "registered (name: ${CLAUDE_MCP_NAME})" || echo "skipped" )"
echo "Codex MCP:         $( [[ ${CODEX_OK} -eq 1 ]] && echo "registered (${CODEX_CONFIG})" || echo "skipped" )"
echo
echo "Next steps:"
echo "  1. Restart your CLI session so the MCP registration takes effect."
echo "  2. Verify with:"
echo "       claude mcp list"
echo "  3. Test subagent delegation via the PAL 'clink' tool (cli_name=codex)."
echo "============================================================"
