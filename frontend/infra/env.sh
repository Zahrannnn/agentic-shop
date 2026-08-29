#!/bin/sh
set -e

# Runtime browser env substitution.
# Writes /app/public/runtime-env.js from the container environment so that
# changing infra/.env and restarting the container picks up new values
# without rebuilding the image. Node is available in the runner image.

node -e '
const fs = require("node:fs");
const cfg = {
  NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME ?? "",
  NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL ?? "",
  NEXT_PUBLIC_SHOW_HEALTH_URLS: process.env.NEXT_PUBLIC_SHOW_HEALTH_URLS ?? "false",
  NEXT_PUBLIC_CORE_API_BASE_URL: process.env.NEXT_PUBLIC_CORE_API_BASE_URL ?? "",
  NEXT_PUBLIC_BILLING_API_BASE_URL: process.env.NEXT_PUBLIC_BILLING_API_BASE_URL ?? "",
  NEXT_PUBLIC_REPORTING_API_BASE_URL: process.env.NEXT_PUBLIC_REPORTING_API_BASE_URL ?? "",
};
fs.writeFileSync(
  "/app/public/runtime-env.js",
  "window.__RUNTIME_CONFIG__ = " + JSON.stringify(cfg) + ";"
);
' || echo "[env.sh] warning: could not write runtime-env.js (server will use build-time env)"

exec "$@"
