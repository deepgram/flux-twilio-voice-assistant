#!/bin/bash
set -euo pipefail

# --- Stop helper for Docker ---
# Runtime-agnostic: stops and removes the 'dg-drinks' container, then offers to
# stop the backing VM only if it can identify one it knows how to stop.

if ! command -v docker >/dev/null 2>&1; then
  echo "❌ No 'docker' CLI found. Nothing to do."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ℹ️ No reachable Docker daemon — container is already not running."
  exit 0
fi

echo "🛑 Stopping 'dg-drinks' container..."
docker stop dg-drinks >/dev/null 2>&1 || true
docker rm dg-drinks   >/dev/null 2>&1 || true

echo "✅ Container stopped and removed."

# Offer to stop the backing VM, but only for runtimes we can drive from the CLI.
if command -v colima >/dev/null 2>&1 && colima status >/dev/null 2>&1; then
  read -p "Do you also want to stop the Colima VM? (y/N): " yn
  case $yn in
      [Yy]* )
          echo "🛑 Stopping Colima VM..."
          colima stop
          echo "✅ Colima VM stopped."
          ;;
      * )
          echo "ℹ️ Colima VM left running."
          ;;
  esac
else
  echo "ℹ️ Docker daemon left running."
  echo "    To stop the backing VM, use whatever your runtime provides:"
  echo "      • Colima ......... colima stop"
  echo "      • Rancher Desktop  quit the app"
fi
