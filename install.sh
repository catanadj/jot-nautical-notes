#!/usr/bin/env bash

set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
LIB_DIR="$PREFIX/lib/jot"

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: ./install.sh [--prefix DIR]

Installs jot without pip by copying the launcher and jot_core package into:
  <prefix>/lib/jot

and creating:
  <prefix>/bin/jot -> <prefix>/lib/jot/jot

Default prefix:
  ~/.local
EOF
}

while (($#)); do
  case "$1" in
    --prefix)
      if (($# < 2)); then
        echo "error: --prefix requires a directory" >&2
        exit 2
      fi
      PREFIX="$2"
      BIN_DIR="$PREFIX/bin"
      LIB_DIR="$PREFIX/lib/jot"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$BIN_DIR"
mkdir -p "$LIB_DIR"
rm -rf "$LIB_DIR/jot_core"

install -m 755 "$SCRIPT_DIR/jot" "$LIB_DIR/jot"
cp -R "$SCRIPT_DIR/jot_core" "$LIB_DIR/jot_core"
find "$LIB_DIR/jot_core" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$LIB_DIR/jot_core" -type f -name '*.pyc' -delete
ln -sfn "$LIB_DIR/jot" "$BIN_DIR/jot"

cat <<EOF
Installed jot to:
  $LIB_DIR

Command link:
  $BIN_DIR/jot

If '$BIN_DIR' is not on your PATH, add this to your shell profile:
  export PATH="$BIN_DIR:\$PATH"
EOF
