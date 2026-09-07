#!/bin/bash
set -euo pipefail

# --- Local dev helper for Podman + ngrok ---
# - Ensures Podman VM is running (macOS/Windows)
# - Removes any existing 'dg-drinks' container
# - Builds the image from Containerfile
# - Runs the container on port 8000 with your .env

echo "▶️ Ensuring Podman machine is running..."
podman machine start >/dev/null 2>&1 || true

if podman ps -a --format '{{.Names}}' | grep -q '^dg-drinks$'; then
  echo "🗑️  Removing old 'dg-drinks' container..."
  podman stop dg-drinks >/dev/null 2>&1 || true
  podman rm dg-drinks   >/dev/null 2>&1 || true
fi

echo "🧱 Building image dg-drinks:local ..."
podman build -t dg-drinks:local -f Containerfile .

# Per-call logs are written inside the container to /app/logs; bind-mount the
# host ./logs over it so one file per call shows up in this directory.
mkdir -p logs
chmod 777 logs 2>/dev/null || true

echo "🚀 Starting container on :8000 ..."
podman run -d --name dg-drinks \
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
echo "   (Then set NGROK_HOST in .env and Twilio Voice webhook to https://<NGROK_HOST>/voice)"
echo ""
echo "🔎 Logs (follow):"
echo "   podman logs -f dg-drinks"
echo ""
echo "📝 Per-call log files (one per call):"
echo "   ./logs/<caller-digits>_<timestamp>_<callsid>.log"
echo ""
echo "🛑 To stop and remove container manually:"
echo "   podman stop dg-drinks && podman rm dg-drinks"
echo ""
echo "🛑 Or simply run the helper script:"
echo "   ./podman-stop.sh"
echo ""
echo "🛑 To stop Podman VM entirely:"
echo "   podman machine stop"
