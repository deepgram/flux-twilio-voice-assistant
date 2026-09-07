#!/bin/bash
set -euo pipefail

# --- Local dev helper for Docker + ngrok ---
# Runtime-agnostic: works with any Docker-compatible daemon (Colima, Rancher
# Desktop, a Podman docker-compatible socket, a remote engine). It never tries
# to launch a GUI app — if no daemon is reachable it tells you how to start one.
#
# - Verifies a Docker daemon is reachable
# - Removes any existing 'dg-drinks' container
# - Builds the image from Containerfile
# - Runs the container on port 8000 with your .env

if ! command -v docker >/dev/null 2>&1; then
  echo "❌ No 'docker' CLI found. Install the free CLI with:  brew install docker"
  exit 1
fi

if [[ -n "${DOCKER_HOST:-}" ]]; then
  echo "⚠️  DOCKER_HOST is set to: ${DOCKER_HOST}"
  echo "    It overrides your docker context, so commands go there regardless of"
  echo "    which runtime you think is active. Unset it if that's not intended."
  echo ""
fi

echo "▶️ Checking for a Docker-compatible daemon..."
if ! docker info >/dev/null 2>&1; then
  echo "❌ No reachable Docker daemon."
  echo ""
  echo "   Start whichever runtime you use:"
  echo "     • Colima ......... colima start          (brew install colima)"
  echo "     • Rancher Desktop  open the app"
  echo "     • Podman socket .. podman machine start  (then use ./podman-start.sh instead)"
  echo ""
  echo "   Current docker context: $(docker context show 2>/dev/null || echo unknown)"
  exit 1
fi

echo "   ✅ Daemon reachable — context '$(docker context show 2>/dev/null || echo default)', server $(docker info --format '{{.ServerVersion}}' 2>/dev/null || echo '?')"

if [[ ! -f .env ]]; then
  echo "❌ No .env file found. Copy sample.env.txt to .env and fill it in first."
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -q '^dg-drinks$'; then
  echo "🗑️  Removing old 'dg-drinks' container..."
  docker stop dg-drinks >/dev/null 2>&1 || true
  docker rm dg-drinks   >/dev/null 2>&1 || true
fi

echo "🧱 Building image dg-drinks:local ..."
docker build -t dg-drinks:local -f Containerfile .

# Per-call logs are written inside the container to /app/logs; bind-mount the
# host ./logs over it so one file per call shows up in this directory.
# 777 because the container runs as uid 10001, which won't match your host user.
mkdir -p logs
chmod 777 logs 2>/dev/null || true

echo "🚀 Starting container on :8000 ..."
docker run -d --name dg-drinks \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/logs:/app/logs" \
  dg-drinks:local

echo ""
echo "✅ Up! Dashboards:"
echo "   • Orders:  http://localhost:8000/orders"
echo "   • Staff:   http://localhost:8000/staff"
echo ""
echo "📞 Expose to Twilio with ngrok:"
echo "   ngrok http 8000"
echo "   (Then set VOICE_HOST in .env and Twilio Voice webhook to https://<VOICE_HOST>/voice)"
echo ""
echo "🔎 Logs (follow):"
echo "   docker logs -f dg-drinks"
echo ""
echo "📝 Per-call log files (one per call):"
echo "   ./logs/<caller-digits>_<timestamp>_<callsid>.log"
echo ""
echo "🛑 To stop and remove container manually:"
echo "   docker stop dg-drinks && docker rm dg-drinks"
echo ""
echo "🛑 Or simply run the helper script:"
echo "   ./docker-stop.sh"
echo ""
echo "ℹ️  Note: this publishes host port 8000, the same port as ./podman-start.sh."
echo "    Don't run both at once — stop one before starting the other."
echo ""
