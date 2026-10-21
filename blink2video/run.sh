#!/bin/sh
# Reads the add-on options and starts blink2video with them.
set -eu
TRUSTED="$(python - <<'PY'
import json
try:
    print(json.load(open("/data/options.json")).get("trusted_host", "").strip())
except Exception:
    print("")
PY
)"
# MJPEG restreamer on :8766 (restarted if it ever exits).
( while true; do python /stream_proxy.py; sleep 3; done ) &

echo "blink2video: trusted host = '${TRUSTED:-<none>}'"
if [ -n "$TRUSTED" ]; then
    exec python blink2video.py start --trusted-host "$TRUSTED"
fi
exec python blink2video.py start
