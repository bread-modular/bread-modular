#!/usr/bin/env bash
# Wrapper for the tscircuit CLI (tsci) that works without a global install.
# Usage: ./tsci.sh <tsci args...>   e.g. ./tsci.sh export blank.circuit.tsx -f pcb-svg
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$DIR/node_modules/.bin:$PATH"
exec tsci "$@"
