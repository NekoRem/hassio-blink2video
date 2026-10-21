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
echo "blink2video: trusted host = '${TRUSTED:-<none>}'"
if [ -n "$TRUSTED" ]; then
    exec python blink2video.py start --trusted-host "$TRUSTED"
fi
exec python blink2video.py start
