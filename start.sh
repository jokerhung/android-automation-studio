#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# Internet installations already own a prepared environment and static export.
if [ -f "$SCRIPT_DIR/.artemis-install.json" ]; then
    action=start
    installed_args=()
    for arg in "$@"; do
        case "$arg" in
            --stop) action=stop;;
            --status) action=status;;
            --restart) action=restart;;
            --daemon|--no-open) :;;
            *) installed_args+=("$arg");;
        esac
    done
    exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scripts/install_runtime.py" "$action" "${installed_args[@]}"
fi

ARTEMIS_FRONTEND="${ARTEMIS_FRONTEND:-next}"
START_ARGS=("$@")
for ((i = 0; i < ${#START_ARGS[@]}; i++)); do
    case "${START_ARGS[$i]}" in
        --frontend)
            if ((i + 1 >= ${#START_ARGS[@]})); then echo "--frontend requires next" >&2; exit 2; fi
            ARTEMIS_FRONTEND="${START_ARGS[$((i + 1))]}"
            unset 'START_ARGS[i]' 'START_ARGS[i+1]'
            START_ARGS=("${START_ARGS[@]}")
            break
            ;;
        --frontend=*) ARTEMIS_FRONTEND="${START_ARGS[$i]#*=}"; unset 'START_ARGS[i]'; START_ARGS=("${START_ARGS[@]}"); break ;;
    esac
done
ARTEMIS_FRONTEND="$(printf '%s' "${ARTEMIS_FRONTEND}" | tr '[:upper:]' '[:lower:]')"
case "${ARTEMIS_FRONTEND}" in
    next) FRONTEND_APP="showcase_next"; FRONTEND_LABEL="Next.js" ;;
    *) echo "ARTEMIS_FRONTEND must be 'next' (Angular has been removed) (got: ${ARTEMIS_FRONTEND})." >&2; exit 2 ;;
esac
export ARTEMIS_FRONTEND

# Use the project UI port by default while preserving an explicit CLI override.
UI_PORT="${ARTEMIS_DAEMON_PORT:-8009}"
HAS_PORT_ARG=false
for ((i = 0; i < ${#START_ARGS[@]}; i++)); do
    case "${START_ARGS[$i]}" in
        --port|-p)
            HAS_PORT_ARG=true
            if ((i + 1 < ${#START_ARGS[@]})); then UI_PORT="${START_ARGS[$((i + 1))]}"; fi
            ;;
        --port=*|-p=*)
            HAS_PORT_ARG=true
            UI_PORT="${START_ARGS[$i]#*=}"
            ;;
    esac
done
if ! [[ "${UI_PORT}" =~ ^[0-9]+$ ]] || ((UI_PORT < 1 || UI_PORT > 65535)); then
    echo "Invalid Artemis UI port: ${UI_PORT}" >&2
    exit 2
fi

echo -e "${BOLD}${CYAN}======================================================${NC}"
echo -e "${BOLD}${CYAN}      ✨ Artemis Autonomous Mobile Agent UI          ${NC}"
echo -e "${BOLD}${CYAN}======================================================${NC}"
echo ""

# 1. Normalize PATH with standard toolchain and package manager paths
STANDARD_PATHS=(
    "/opt/homebrew/bin"
    "/opt/homebrew/sbin"
    "/usr/local/bin"
    "/usr/local/sbin"
    "${HOME}/.local/bin"
    "${HOME}/.local/share/node/bin"
    "${HOME}/.local/share/platform-tools"
    "${HOME}/.local/share/scrcpy"
    "${HOME}/.cargo/bin"
    "${HOME}/Library/Android/sdk/platform-tools"
    "${HOME}/Android/Sdk/platform-tools"
)
for p in "${STANDARD_PATHS[@]}"; do
    if [ -d "${p}" ] && [[ ":${PATH}:" != *":${p}:"* ]]; then
        export PATH="${p}:${PATH}"
    fi
done

# Sudo credential and choice state tracking
SUDO_AUTHENTICATED=false
SUDO_DECLINED=false

# Helper to check, prompt for, or skip administrator (sudo) privileges gracefully
request_sudo() {
    [ "$(id -u)" -eq 0 ] && return 0
    if ! command -v sudo >/dev/null 2>&1; then
        return 1
    fi
    # If already authenticated or passwordless sudo works
    if [ "${SUDO_AUTHENTICATED}" = true ] || sudo -n true >/dev/null 2>&1; then
        SUDO_AUTHENTICATED=true
        return 0
    fi
    # If previously declined or failed in this session, don't nag again
    if [ "${SUDO_DECLINED}" = true ]; then
        return 1
    fi
    # If interactive terminal, ask user whether to enter sudo password
    if [ -t 0 ]; then
        local action="${1:-install system packages}"
        echo -e "   ${CYAN}🔐 Administrator (sudo) privileges can be used to ${action}.${NC}"
        local reply=""
        read -r -p "      Enter sudo password now? [Y/n]: " reply
        reply=${reply:-Y}
        if [[ "${reply}" =~ ^[Yy]$ ]]; then
            if sudo -v; then
                SUDO_AUTHENTICATED=true
                echo -e "   ${GREEN}✔ Sudo authenticated successfully.${NC}"
                return 0
            else
                echo -e "   ${YELLOW}⚠ Sudo authentication failed or cancelled. Using user-space fallback.${NC}"
                SUDO_DECLINED=true
                return 1
            fi
        else
            echo -e "   ${YELLOW}⏭️  Skipped sudo. Using user-space fallback.${NC}"
            SUDO_DECLINED=true
            return 1
        fi
    fi
    return 1
}

# Check Node.js/npm against the selected frontend's package requirements.
is_node_compatible() {
    if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then return 1; fi
    local node_ver major minor
    node_ver="$(node -v 2>/dev/null | tr -d 'v')"
    [ -z "${node_ver}" ] && return 1
    major="${node_ver%%.*}"
    minor="$(printf '%s' "${node_ver}" | cut -d. -f2)"
    [ "${major}" -gt 20 ] 2>/dev/null || { [ "${major}" -eq 20 ] 2>/dev/null && [ "${minor}" -ge 9 ] 2>/dev/null; }
}

node_requirement() {
    printf '%s' '>= 20.9.0'
}

# 2. Check or install uv (Fast Python package manager)
if ! command -v uv >/dev/null 2>&1; then
    echo -e "${YELLOW}⚡ uv not found. Installing Astral uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
fi

# 3. Check and auto-install missing system toolchains (ADB, FFmpeg, scrcpy)
# Discover standard Android SDK / user-space locations if adb not in PATH
if ! command -v adb >/dev/null 2>&1; then
    for candidate in \
        "${ANDROID_HOME:-}/platform-tools" \
        "${ANDROID_SDK_ROOT:-}/platform-tools" \
        "${HOME}/Library/Android/sdk/platform-tools" \
        "${HOME}/Android/Sdk/platform-tools" \
        "${HOME}/.local/share/platform-tools" \
        "/opt/homebrew/bin" \
        "/usr/local/bin"; do
        if [ -n "${candidate}" ] && [ -x "${candidate}/adb" ]; then
            export PATH="${candidate}:${PATH}"
            break
        fi
    done
fi

MISSING_CORE=()
if ! command -v adb >/dev/null 2>&1; then MISSING_CORE+=("adb"); fi
if ! command -v ffmpeg >/dev/null 2>&1; then MISSING_CORE+=("ffmpeg"); fi
if ! command -v scrcpy >/dev/null 2>&1; then MISSING_CORE+=("scrcpy"); fi

if [ ${#MISSING_CORE[@]} -gt 0 ]; then
    OS_NAME="$(uname -s)"
    if [ "${OS_NAME}" = "Darwin" ]; then
        export HOMEBREW_NO_AUTO_UPDATE=1
        export HOMEBREW_NO_INSTALL_CLEANUP=1
        export HOMEBREW_NO_ENV_HINTS=1

        if ! command -v brew >/dev/null 2>&1; then
            if [ -x "/opt/homebrew/bin/brew" ]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [ -x "/usr/local/bin/brew" ]; then
                eval "$(/usr/local/bin/brew shellenv)"
            fi
        fi

        if command -v brew >/dev/null 2>&1; then
            echo -e "   ${YELLOW}⚡ Auto-installing missing components (${MISSING_CORE[*]})...${NC}"
            if ! command -v adb >/dev/null 2>&1; then
                brew install --cask android-platform-tools >/dev/null 2>&1 || brew install android-platform-tools >/dev/null 2>&1 || true
            fi
            if ! command -v ffmpeg >/dev/null 2>&1; then
                brew install ffmpeg >/dev/null 2>&1 || true
            fi
            if ! command -v scrcpy >/dev/null 2>&1; then
                brew install scrcpy >/dev/null 2>&1 || true
            fi
        fi
    elif [ "${OS_NAME}" = "Linux" ]; then
        if request_sudo "install missing system components (${MISSING_CORE[*]})"; then
            SUDO_PREFIX=""
            if [ "$(id -u)" -ne 0 ]; then SUDO_PREFIX="sudo"; fi
            if command -v apt-get >/dev/null 2>&1; then
                echo -e "   ${CYAN}📦 Installing missing packages (${MISSING_CORE[*]}) via apt-get...${NC}"
                DEBIAN_FRONTEND=noninteractive ${SUDO_PREFIX} apt-get -o DPkg::Lock::Timeout=3 -o Acquire::http::Timeout=3 -o Acquire::https::Timeout=3 install -y -qq "${MISSING_CORE[@]}" 2>/dev/null || true
            elif command -v dnf >/dev/null 2>&1; then
                ${SUDO_PREFIX} dnf install -y "${MISSING_CORE[@]}" 2>/dev/null || true
            elif command -v pacman >/dev/null 2>&1; then
                ${SUDO_PREFIX} pacman -S --noconfirm "${MISSING_CORE[@]}" 2>/dev/null || true
            fi
        fi

        # Fallback: if scrcpy is still missing, install official precompiled portable scrcpy in user space
        if ! command -v scrcpy >/dev/null 2>&1; then
            ARCH="$(uname -m)"
            SCRCPY_ARCH=""
            case "${ARCH}" in
                x86_64|amd64) SCRCPY_ARCH="x86_64" ;;
                aarch64|arm64) SCRCPY_ARCH="aarch64" ;;
            esac
            if [ -n "${SCRCPY_ARCH}" ]; then
                SCRCPY_DIR="${HOME}/.local/share/scrcpy"
                if [ ! -x "${SCRCPY_DIR}/scrcpy" ]; then
                    echo -e "   ${CYAN}📦 Installing portable scrcpy in user space (~/.local)...${NC}"
                    mkdir -p "${SCRCPY_DIR}" "${HOME}/.local/bin"
                    SCRCPY_URL="https://github.com/Genymobile/scrcpy/releases/download/v4.1/scrcpy-linux-${SCRCPY_ARCH}-v4.1.tar.gz"
                    if curl -fsSL --connect-timeout 5 --max-time 30 "${SCRCPY_URL}" | tar -xz -C "${SCRCPY_DIR}" --strip-components=1 2>/dev/null; then
                        ln -sf "${SCRCPY_DIR}/scrcpy" "${HOME}/.local/bin/scrcpy"
                        export PATH="${SCRCPY_DIR}:${PATH}"
                        echo -e "   ${GREEN}✓ scrcpy installed in user space.${NC}"
                    fi
                else
                    ln -sf "${SCRCPY_DIR}/scrcpy" "${HOME}/.local/bin/scrcpy"
                    export PATH="${SCRCPY_DIR}:${PATH}"
                fi
            fi
        fi

        # Fallback: if adb is missing on Linux without root/sudo, install platform-tools in user space
        if ! command -v adb >/dev/null 2>&1; then
            ARCH="$(uname -m)"
            if [[ "${ARCH}" = "x86_64" || "${ARCH}" = "amd64" ]]; then
                PT_DIR="${HOME}/.local/share/platform-tools"
                if [ ! -x "${PT_DIR}/adb" ]; then
                    echo -e "   ${CYAN}📦 Installing Android platform-tools (adb) in user space...${NC}"
                    TEMP_ZIP="/tmp/platform-tools-$$.zip"
                    if curl -fsSL --connect-timeout 5 --max-time 30 "https://dl.google.com/android/repository/platform-tools-latest-linux.zip" -o "${TEMP_ZIP}" 2>/dev/null; then
                        mkdir -p "${HOME}/.local/share" "${HOME}/.local/bin"
                        if command -v unzip >/dev/null 2>&1; then
                            unzip -q -o "${TEMP_ZIP}" -d "${HOME}/.local/share" 2>/dev/null || true
                        else
                            python3 -m zipfile -e "${TEMP_ZIP}" "${HOME}/.local/share" 2>/dev/null || true
                        fi
                        rm -f "${TEMP_ZIP}"
                    fi
                fi
                if [ -x "${PT_DIR}/adb" ]; then
                    ln -sf "${PT_DIR}/adb" "${HOME}/.local/bin/adb"
                    export PATH="${PT_DIR}:${PATH}"
                    echo -e "   ${GREEN}✓ adb installed in user space.${NC}"
                fi
            fi
        fi
    fi
fi

# Ensure local ADB daemon is warm & listening so probes do not hit 'Connection refused'
if command -v adb >/dev/null 2>&1; then
    (unset ADB_SERVER_SOCKET; adb start-server >/dev/null 2>&1 || true)
fi

# 4. Check or initialize .env configuration file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "   ${GREEN}✓ Initialized .env configuration file.${NC}"
    else
        touch .env
    fi
fi

# 5. Synchronize Python runtime & dependencies
echo -e "   ${BLUE}📦 Synchronizing Python runtime and project dependencies...${NC}"
uv sync --locked --quiet

# 6. Build the selected frontend when missing or older than its source/configuration
FRONTEND_DIR="${SCRIPT_DIR}/apps/${FRONTEND_APP}"
FRONTEND_CANDIDATES=("${FRONTEND_DIR}/out/index.html")
FRONTEND_INPUTS=("${FRONTEND_DIR}/src" "${FRONTEND_DIR}/public" "${FRONTEND_DIR}/package.json" "${FRONTEND_DIR}/package-lock.json" "${FRONTEND_DIR}/next.config.ts" "${FRONTEND_DIR}/postcss.config.mjs" "${FRONTEND_DIR}/tsconfig.json")
EXISTING_SHOWCASE_INDEX=""
for candidate in "${FRONTEND_CANDIDATES[@]}"; do
    if [ -f "${candidate}" ]; then EXISTING_SHOWCASE_INDEX="${candidate}"; break; fi
done
FRONTEND_BUILD_REQUIRED=false
if [ -z "${EXISTING_SHOWCASE_INDEX}" ]; then
    FRONTEND_BUILD_REQUIRED=true
else
    for input in "${FRONTEND_INPUTS[@]}"; do
        if [ -e "${input}" ] && find "${input}" -type f -newer "${EXISTING_SHOWCASE_INDEX}" -print -quit 2>/dev/null | grep -q .; then FRONTEND_BUILD_REQUIRED=true; break; fi
    done
fi
if [ "${FRONTEND_BUILD_REQUIRED}" = true ]; then
    # First: Try loading existing nvm or user-installed node in environment
    export NVM_DIR="${HOME}/.nvm"
    if [ -s "${NVM_DIR}/nvm.sh" ]; then
        # shellcheck disable=SC1090,SC1091
        . "${NVM_DIR}/nvm.sh" 2>/dev/null || true
    fi
    if [ -d "${HOME}/.local/share/node/bin" ] && [[ ":${PATH}:" != *":${HOME}/.local/share/node/bin:"* ]]; then
        export PATH="${HOME}/.local/share/node/bin:${PATH}"
    fi

    # Check if nvm already has a compatible Node version installed
    if ! is_node_compatible && (command -v nvm >/dev/null 2>&1 || type nvm >/dev/null 2>&1); then
        nvm use 22 >/dev/null 2>&1 || true
    fi

    if ! is_node_compatible; then
        OS_NAME="$(uname -s)"
        if command -v node >/dev/null 2>&1; then
            echo -e "   ${YELLOW}⚡ Detected Node.js $(node -v 2>/dev/null), but ${FRONTEND_LABEL} requires Node.js $(node_requirement). Upgrading Node.js...${NC}"
        else
            echo -e "   ${YELLOW}⚡ Node.js/npm not found. Auto-installing Node.js 22 LTS for ${FRONTEND_LABEL} compilation...${NC}"
        fi

        # 1. Try installing Node 22 via nvm if available
        if command -v nvm >/dev/null 2>&1 || type nvm >/dev/null 2>&1; then
            echo -e "   ${CYAN}📦 Installing Node.js 22 LTS via nvm...${NC}"
            nvm install 22 >/dev/null 2>&1 || true
            nvm use 22 >/dev/null 2>&1 || true
        fi

        # 2. Try brew on macOS
        if ! is_node_compatible && [ "${OS_NAME}" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
            brew install node >/dev/null 2>&1 || brew upgrade node >/dev/null 2>&1 || true
        fi

        # 3. Try Linux package managers with sudo / root
        if ! is_node_compatible && [ "${OS_NAME}" = "Linux" ]; then
            if request_sudo "install or upgrade Node.js 22 LTS"; then
                SUDO_PREFIX=""
                if [ "$(id -u)" -ne 0 ]; then SUDO_PREFIX="sudo"; fi
                if command -v apt-get >/dev/null 2>&1; then
                    echo -e "   ${CYAN}📦 Configuring NodeSource Node.js 22 LTS repository...${NC}"
                    curl -fsSL https://deb.nodesource.com/setup_22.x | ${SUDO_PREFIX} bash - >/dev/null 2>&1 || true
                    ${SUDO_PREFIX} apt-get -o DPkg::Lock::Timeout=5 install -y -qq nodejs 2>/dev/null || true
                elif command -v dnf >/dev/null 2>&1; then
                    curl -fsSL https://rpm.nodesource.com/setup_22.x | ${SUDO_PREFIX} bash - >/dev/null 2>&1 || true
                    ${SUDO_PREFIX} dnf install -y nodejs || true
                elif command -v pacman >/dev/null 2>&1; then
                    ${SUDO_PREFIX} pacman -S --noconfirm nodejs npm || true
                fi
            fi
        fi

        # 4. Standalone portable Node.js LTS (zero-admin user space fallback, guaranteed compatible)
        if ! is_node_compatible; then
            ARCH="$(uname -m)"
            NODE_ARCH=""
            case "${ARCH}" in
                x86_64|amd64) NODE_ARCH="x64" ;;
                aarch64|arm64) NODE_ARCH="arm64" ;;
            esac
            OS_SYS="$(uname -s | tr '[:upper:]' '[:lower:]')"
            if [ -n "${NODE_ARCH}" ] && { [ "${OS_SYS}" = "linux" ] || [ "${OS_SYS}" = "darwin" ]; }; then
                NODE_VER="v22.23.2"
                NODE_DIR="${HOME}/.local/share/node"
                echo -e "   ${CYAN}📦 Installing portable Node.js ${NODE_VER} in user space (~/.local)...${NC}"
                rm -rf "${NODE_DIR}"
                mkdir -p "${NODE_DIR}" "${HOME}/.local/bin"
                if curl -fsSL --connect-timeout 5 --max-time 60 "https://nodejs.org/dist/${NODE_VER}/node-${NODE_VER}-${OS_SYS}-${NODE_ARCH}.tar.gz" | tar -xz -C "${NODE_DIR}" --strip-components=1 2>/dev/null; then
                    ln -sf "${NODE_DIR}/bin/node" "${HOME}/.local/bin/node"
                    ln -sf "${NODE_DIR}/bin/npm" "${HOME}/.local/bin/npm"
                    ln -sf "${NODE_DIR}/bin/npx" "${HOME}/.local/bin/npx"
                    export PATH="${NODE_DIR}/bin:${HOME}/.local/bin:${PATH}"
                    hash -r 2>/dev/null || true
                    echo -e "   ${GREEN}✓ Portable Node.js ${NODE_VER} installed in user space.${NC}"
                fi
            fi
        fi
    fi

    if ! is_node_compatible; then
        echo "Cannot build ${FRONTEND_LABEL}: Node.js $(node_requirement) and npm are required." >&2
        exit 1
    fi
    echo -e "   ${GREEN}✓ Node.js $(node -v) and npm $(npm -v) ready for ${FRONTEND_LABEL}.${NC}"
    echo -e "   ${YELLOW}🎨 ${FRONTEND_LABEL} build is missing or stale. Building selected frontend...${NC}"
    if ! (
        cd "${FRONTEND_DIR}"
        if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
        npm run build
    ); then
        echo "${FRONTEND_LABEL} frontend build failed; the previous artifact, if any, was not removed." >&2
        exit 1
    fi
    BUILT_FRONTEND_INDEX=""
    for candidate in "${FRONTEND_CANDIDATES[@]}"; do if [ -f "${candidate}" ]; then BUILT_FRONTEND_INDEX="${candidate}"; break; fi; done
    if [ -z "${BUILT_FRONTEND_INDEX}" ]; then echo "${FRONTEND_LABEL} build completed but expected artifact was not found: ${FRONTEND_CANDIDATES[*]}" >&2; exit 1; fi
    echo -e "   ${GREEN}✓ ${FRONTEND_LABEL} frontend compiled successfully.${NC}"
fi

# 7. Optionally configure MCP for detected AI IDEs
echo ""
echo -e "   ${CYAN}🔌 Would you like to configure ARTEMIS MCP & testing rules for your AI IDEs?${NC}"
echo -e "      (Supported: Antigravity, Cursor, Claude Code/Desktop, Codex, OpenClaw, Windsurf)"
if [ -t 0 ]; then
    read -r -p "      Install MCP configuration & rules now? [Y/n]: " INSTALL_MCP
    INSTALL_MCP=${INSTALL_MCP:-Y}
else
    INSTALL_MCP="n"
fi

if [[ "${INSTALL_MCP}" =~ ^[Yy]$ ]]; then
    echo -e "   ${CYAN}Installing MCP server configuration & testing rules...${NC}"
    if uv run artemis mcp --install all; then
        echo -e "   ${GREEN}✔ MCP configuration and rules installed successfully.${NC}"
        echo -e "   ${CYAN}💡 Tip: You can update or re-install anytime with: ${BOLD}uv run artemis mcp --install all${NC}"
    else
        echo -e "   ${YELLOW}⚠ MCP installation failed. Review the error above and retry with: ${BOLD}uv run artemis mcp --install all${NC}"
    fi
else
    echo -e "   ${YELLOW}⏭️  Skipped. You can install MCP anytime later with: ${BOLD}uv run artemis mcp --install all${NC}"
fi
echo ""

# 8. Detect environment & launch unified Showcase UI
IS_REMOTE=false
if [ -n "${SSH_CONNECTION:-}" ] || [ -n "${SSH_CLIENT:-}" ] || [ -n "${SSH_TTY:-}" ] || [ -z "${DISPLAY:-}" ]; then
    IS_REMOTE=true
fi

echo -e "   ${GREEN}🚀 Launching Artemis Showcase UI & Admin Console...${NC}"

OPEN_FLAG="--open"
if [ "${IS_REMOTE}" = true ]; then
    HOSTNAME_STR="$(hostname 2>/dev/null || echo 'cloud-host')"
    USER_STR="$(whoami 2>/dev/null || echo 'user')"
    echo -e "   ${CYAN}☁️  Cloud / Remote environment detected:${NC}"
    echo -e "      • Access locally via SSH tunnel: ${BOLD}ssh -L ${UI_PORT}:localhost:${UI_PORT} ${USER_STR}@${HOSTNAME_STR}${NC}"
    echo -e "      • Or access via Cloudtop / VS Code / Cursor Port Forwarding (Port ${UI_PORT})"
    if [ -z "${DISPLAY:-}" ]; then
        echo -e "      • Headless session detected (browser auto-open disabled)."
        OPEN_FLAG="--no-open"
    fi
    echo ""
fi

# Ensure local ADB daemon is active and listening before launching UI
if command -v adb >/dev/null 2>&1; then
    (unset ADB_SERVER_SOCKET; adb start-server >/dev/null 2>&1 || true)
fi

# Launch via `python -m artemis` (not the `artemis` console-script shim) so the
# long-running server never pins .venv/Scripts/artemis[.exe] against reinstalls.
if [ "${HAS_PORT_ARG}" = false ]; then
    START_ARGS+=(--port "${UI_PORT}")
fi
exec uv run python -m artemis ui "${OPEN_FLAG}" "${START_ARGS[@]}"
