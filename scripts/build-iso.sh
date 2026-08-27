#!/usr/bin/env bash
# Convenience wrapper for iso/build.sh
set -euo pipefail
exec "$(dirname "${BASH_SOURCE[0]}")/../iso/build.sh" "$@"
