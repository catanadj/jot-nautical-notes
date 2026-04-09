#!/usr/bin/env bash

set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
LIB_DIR="$PREFIX/lib/jot"

usage() {
  cat <<'EOF'
Usage: ./uninstall.sh [--prefix DIR]

Removes the non-pip jot installation created by install.sh.
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

rm -f "$BIN_DIR/jot"
rm -rf "$LIB_DIR"

cat <<EOF
Removed:
  $BIN_DIR/jot
  $LIB_DIR
EOF
