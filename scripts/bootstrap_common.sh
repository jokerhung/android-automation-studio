#!/usr/bin/env bash
# Private, pinned uv binary. No shell profile changes or administrator access.
bootstrap_uv() {
    local root="$1" temporary="$2" os="$3" arch="$4" target file expected actual
    local version=0.12.13
    ARTEMIS_UV="$root/.tools/uv/uv"
    if [ -x "$ARTEMIS_UV" ]; then
        case "$("$ARTEMIS_UV" --version 2>/dev/null)" in "uv $version"|"uv $version "*) return;; esac
    fi
    case "$os/$arch" in
        Linux/x86_64) target=x86_64-unknown-linux-gnu;;
        Darwin/x86_64) target=x86_64-apple-darwin;;
        Darwin/arm64) target=aarch64-apple-darwin;;
        *) return 2;;
    esac
    file="uv-$target.tar.gz"
    echo "[DANG] 3/6 Preparing uv $version and managed Python 3.12"
    curl -fSL --connect-timeout 15 --max-time 600 --retry 2 --retry-delay 2 "https://github.com/astral-sh/uv/releases/download/$version/$file" -o "$temporary/$file"
    curl -fsSL --connect-timeout 15 --max-time 600 --retry 2 "https://github.com/astral-sh/uv/releases/download/$version/$file.sha256" -o "$temporary/uv.sha256"
    read -r expected _ < "$temporary/uv.sha256"
    if command -v sha256sum >/dev/null; then actual="$(sha256sum "$temporary/$file")"
    else actual="$(shasum -a 256 "$temporary/$file")"; fi
    actual="${actual%% *}"
    [ "$actual" = "$expected" ] || { echo '[LOI] uv checksum mismatch' >&2; return 4; }
    mkdir -p "$temporary/uv" "$root/.tools/uv"
    tar -xzf "$temporary/$file" -C "$temporary/uv" --strip-components=1
    cp "$temporary/uv/uv" "$ARTEMIS_UV"
    chmod +x "$ARTEMIS_UV"
}
