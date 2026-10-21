# blink2video

Web UI: `http://<ha-ip>:8765`. Sign in with your Blink account on first open
(session token only is kept; password is not stored). Data lives in the
add-on's `/data` volume and is included in Home Assistant backups.

**Security:** the UI has no login of its own. `trusted_host` decides which
clients are accepted (comma separated host names, IPs or CIDR subnets). The
default trusts the whole `192.168.1.0/24` LAN. Narrow it to specific IPs if
you prefer. A name typed in the address bar must be listed too.

Webhooks (`/webhook/status`, `/webhook/arm`, `/webhook/snapshot`) use the
secret shown under Settings in the UI.

## Live stream for Home Assistant (port 8766)

A small restreamer runs next to blink2video and exposes the live view as plain MJPEG,
with no token and no Host-header rules, so Home Assistant's **MJPEG IP Camera**
integration can use it as an ordinary camera:

- `http://<ha-ip>:8766/stream` - continuous video. Blink is only contacted while someone is
  watching, and the session is reopened automatically when Blink closes it (about every 6 minutes).
- `http://<ha-ip>:8766/still.jpg` - still image (does not start a live session).
- Add `?camera=NAME` to pick a camera if you have several.

Blink allows one live session per sync module at a time, so while the stream is running the
blink2video web UI's own live view will be refused. Port 8766 has no authentication; keep it on your LAN.
