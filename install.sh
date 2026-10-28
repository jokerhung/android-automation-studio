#!/usr/bin/env bash
# Internet bootstrap. Compatible with the macOS system Bash (3.2).
set -Eeuo pipefail

main() {
    local install_dir="${HOME}/.local/share/artemis" stage='' lock='' code=3
    local os arch arg
    local runtime_args=()
    while [ "$#" -gt 0 ]; do
        arg="$1"; shift
        case "$arg" in
            --install-dir|--port)
                [ "$#" -gt 0 ] && [ -n "$1" ] || { echo "[LOI] Missing value for $arg" >&2; exit 2; }
                if [ "$arg" = --install-dir ]; then install_dir="$1"
                else
                    case "$1" in *[!0-9]*|'') echo '[LOI] Invalid port' >&2; exit 2;; esac
                    [ "${#1}" -le 5 ] && [ "$1" -ge 1 ] && [ "$1" -le 65535 ] || exit 2
                    runtime_args+=(--port "$1")
                fi
                shift ;;
            --local-only|--non-interactive|--open) runtime_args+=("$arg");;
            --help|-h)
                echo 'Usage: bash install.sh [--install-dir PATH] [--port 1..65535] [--local-only] [--non-interactive] [--open]'
                echo 'Default: ~/.local/share/artemis, port 8009, LAN bind, background process.'
                return ;;
            *) echo "[LOI] Unknown argument: $arg (use --help)" >&2; exit 2;;
        esac
    done
    os="$(uname -s)"; arch="$(uname -m)"
    case "$os/$arch" in
        Linux/x86_64)
            # shellcheck disable=SC1091
            . /etc/os-release
            [ "${ID:-}" = ubuntu ] && { [ "${VERSION_ID:-}" = 22.04 ] || [ "${VERSION_ID:-}" = 24.04 ]; } || {
                echo '[LOI] Supported Linux: Ubuntu 22.04/24.04 x86_64 (glibc).' >&2; exit 2;
            } ;;
        Darwin/x86_64|Darwin/arm64)
            case "$(sw_vers -productVersion)" in 14.*|15.*) :;; *) echo '[LOI] Supported macOS: 14/15.' >&2; exit 2;; esac ;;
        *) echo "[LOI] Unsupported environment: $os/$arch" >&2; exit 2;;
    esac
    for arg in curl tar mktemp; do command -v "$arg" >/dev/null || { echo "[LOI] Install prerequisite: $arg" >&2; exit 2; }; done
    case "$install_dir" in /*) :;; *) install_dir="$PWD/$install_dir";; esac
    mkdir -p "$(dirname "$install_dir")"
    # Canonicalize the parent so equivalent paths share the installation lock.
    install_dir="$(cd "$(dirname "$install_dir")" && pwd -P)/$(basename "$install_dir")"
    lock="${install_dir}.install-lock"
    mkdir "$lock" 2>/dev/null || { echo "[LOI] Installation locked: $lock. If interrupted, confirm no installer is running before removing this directory." >&2; exit 3; }
    cleanup() {
        local result=$?
        [ -z "$stage" ] || rm -rf -- "$stage"
        rmdir "$lock" 2>/dev/null || true
        if [ "$result" -ne 0 ]; then
            echo "[LOI] Installation stopped (code $result). Existing servers were not stopped. Retry the same command; see $install_dir/logs/install.log when available." >&2
        fi
    }
    trap cleanup EXIT
    trap 'echo "[HUY] Installation cancelled; retry the same command." >&2; exit 130' INT TERM
    trap 'exit "$code"' ERR
    echo "[OK] 1/6 Environment: $os/$arch"
    echo "Source: jokerhung/android-automation-studio @ nextjs"
    echo "Directory: $install_dir"
    stage="$(mktemp -d "$(dirname "$install_dir")/.artemis-stage.XXXXXXXX")"
    if [ -f "$install_dir/.artemis-install.json" ] && [ -f "$install_dir/scripts/install_runtime.py" ]; then
        echo '[GIU] 2/6 Keeping existing source and configuration'
    else
        if [ -e "$install_dir" ] && { [ ! -d "$install_dir" ] || [ -n "$(ls -A "$install_dir")" ]; }; then
            echo '[LOI] Destination is not a recognized installation. Choose --install-dir PATH.' >&2; exit 3
        fi
        code=4
        echo '[DANG] 2/6 Downloading source snapshot'
        curl -fSL --connect-timeout 15 --max-time 600 --retry 2 --retry-delay 2 \
            https://codeload.github.com/jokerhung/android-automation-studio/tar.gz/refs/heads/nextjs -o "$stage/source.tar.gz"
        mkdir "$stage/source"
        tar -xzf "$stage/source.tar.gz" -C "$stage/source" --strip-components=1
        for arg in pyproject.toml uv.lock artemis apps/showcase_next/package-lock.json packages/artemis-client config/artemis.jsonc scripts/install_runtime.py scripts/bootstrap_common.sh; do
            [ -e "$stage/source/$arg" ] || { echo "[LOI] Incomplete archive: $arg" >&2; exit 4; }
        done
        printf '%s\n' '{"schema":1,"source":"jokerhung/android-automation-studio","ref":"nextjs","stage":"source"}' > "$stage/source/.artemis-install.json"
        [ ! -d "$install_dir" ] || rmdir "$install_dir"
        mv "$stage/source" "$install_dir"
    fi
    code=4
    # shellcheck source=scripts/bootstrap_common.sh
    . "$install_dir/scripts/bootstrap_common.sh"
    bootstrap_uv "$install_dir" "$stage" "$os" "$arch"
    code=5
    cd "$install_dir"
    export PYTHONUTF8=1 ARTEMIS_FRONTEND=next
    "$ARTEMIS_UV" python install 3.12
    # Avoid syncing the project before the installer can inspect the running server.
    if "$ARTEMIS_UV" run --no-project --python 3.12 python scripts/install_runtime.py install --uv "$ARTEMIS_UV" "${runtime_args[@]}"; then
        cleanup
        trap - EXIT INT TERM ERR
    else
        exit "$?"
    fi
}

main "$@"
