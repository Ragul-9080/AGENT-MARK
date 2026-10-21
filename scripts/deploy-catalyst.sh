#!/usr/bin/env bash
# =============================================================================
# Agentic Marketing Platform - Zoho Catalyst deployment script
# =============================================================================
# Deploys backend functions + frontend client to Zoho Catalyst.
#
# Prerequisites:
#   - Catalyst CLI installed: https://docs.catalyst.zoho.com/en/cli/v1/
#   - Logged in: catalyst login
#   - Environment variables set (see .env.example)
#
# Usage:
#   ./scripts/deploy-catalyst.sh [environment]
#   environment: development | production (default: development)
# =============================================================================
set -euo pipefail

ENV="${1:-development}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNCTIONS_DIR="$ROOT_DIR/functions"
CLIENT_DIR="$ROOT_DIR/client"
WEB_DIR="$ROOT_DIR/apps/web"

echo "=============================================="
echo "AMA -> Zoho Catalyst deployment ($ENV)"
echo "=============================================="

# --- 1. Check Catalyst CLI --------------------------------------------------
if ! command -v catalyst &> /dev/null; then
  echo "ERROR: Catalyst CLI not found. Install it first."
  echo "  https://docs.catalyst.zoho.com/en/cli/v1/"
  exit 1
fi

if ! catalyst whoami &> /dev/null; then
  echo "ERROR: Not logged in to Catalyst. Run: catalyst login"
  exit 1
fi

# --- 2. Build frontend (Next.js static export) ------------------------------
echo "[1/4] Building Next.js frontend for static export..."
if [ ! -d "$WEB_DIR/node_modules" ]; then
  echo "  Installing frontend dependencies..."
  (cd "$WEB_DIR" && npm install)
fi

(cd "$WEB_DIR" && npx next build --config next.config.catalyst.mjs)

# Copy static export to client/ for Catalyst client hosting
echo "  Copying static export to client/..."
rm -rf "$CLIENT_DIR/_next" "$CLIENT_DIR/*.html" "$CLIENT_DIR/*.js" "$CLIENT_DIR/*.css"
cp -r "$WEB_DIR/out/"* "$CLIENT_DIR/"

# Ensure index.html and 404.html exist (static export may not generate them)
if [ ! -f "$CLIENT_DIR/index.html" ]; then
  cp "$CLIENT_DIR/../index.html" "$CLIENT_DIR/index.html" 2>/dev/null || true
fi

# --- 3. Deploy functions ----------------------------------------------------
echo "[2/4] Deploying Catalyst functions..."
for func in auth contacts campaigns email voice webhooks jobs; do
  echo "  Deploying function: $func"
  (cd "$FUNCTIONS_DIR/$func" && catalyst deploy function "$func") || {
    echo "  WARNING: Failed to deploy $func, continuing..."
  }
done

# --- 4. Deploy client -------------------------------------------------------
echo "[3/4] Deploying Catalyst client..."
(cd "$CLIENT_DIR" && catalyst deploy client) || {
  echo "  WARNING: Client deploy failed."
}

# --- 5. Done ----------------------------------------------------------------
echo "[4/4] Deployment complete."
echo ""
echo "Next steps:"
echo "  - Verify in Catalyst console: https://console.catalyst.zoho.com"
echo "  - Set environment variables in Catalyst console for each function"
echo "  - Configure API Gateway routes if needed"
echo ""
echo "Done."
