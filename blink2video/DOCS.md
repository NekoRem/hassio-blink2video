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
