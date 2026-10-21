# blink2video for Home Assistant

A Home Assistant app (add-on) that runs [blink2video](https://github.com/nico579/blink2video)
by nico579 on your Home Assistant OS / Supervised install.

blink2video is a web interface for Blink cameras. It gives you:

- live view of your cameras
- arming and disarming (per camera or per system)
- a local, timestamped archive of the clips the Sync Module would otherwise erase (grouped by day, week or month)
- snapshots, plus status, arming and snapshot webhooks that Home Assistant can call

This repository only packages the upstream project for Home Assistant. It is a thin wrapper
around the official `nico579dock/blink2video` Docker image, and it contains none of
the upstream code. All the real work is theirs.

## Install

[![Add repository to my Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FNekoRem%2Fhassio-blink2video)

Or manually:

1. In Home Assistant go to **Settings > Add-ons > Add-on Store > ⋮ > Repositories**.
2. Add `https://github.com/NekoRem/hassio-blink2video`.
3. Install **blink2video**, then start it.
4. Open `http://<your-ha-ip>:8765` and sign in with your Blink account (the
   password is not stored, only a session token).

Works on `amd64` and `aarch64`. Requires Home Assistant OS or a Supervised install
(anything with the Supervisor and add-on support).

## Configuration

| Option | Default | Meaning |
| --- | --- | --- |
| `trusted_host` | `192.168.1.0/24` | Which clients may open the UI. Comma-separated host names, IPs or CIDR subnets. |

**Read this before installing:** blink2video's web UI has **no login of its own**. It
only accepts requests whose `Host` is local or listed in `trusted_host`. The default
trusts the whole `192.168.1.0/24` subnet, so every device on that subnet can view your
cameras and arm or disarm them. If your network isn't `192.168.1.x`, or you want it
tighter, change the option, for example to `192.168.1.10, 192.168.1.20`.
A name typed in the browser (such as `homeassistant.local`) must be listed too, because the
server compares the exact `Host` header. Do not expose port 8765 to the internet.

Clips, settings and the Blink session live in the app's data volume and are included in
Home Assistant backups.

## Using it from Home Assistant

blink2video exposes `GET /webhook/status`, `/webhook/arm` and `/webhook/snapshot`, all
using a secret shown under **Settings** in the UI. These work with Home Assistant
`rest_command` and `rest` sensors. See the
[upstream README](https://github.com/nico579/blink2video#readme) for details.

## Status: as-is, no support

This is a personal project, shared in case it's useful. It is **not actively
maintained**: the upstream version is pinned (`0.25.0`), there is no automation
updating it, and I'll bump it only if and when I feel like it. Issues and pull requests
are not monitored. You're welcome to fork it and change anything.

To run a newer upstream release yourself, change the version in `blink2video/config.yaml`
and the `FROM` line in `blink2video/Dockerfile`, then rebuild the add-on.

## Credits and licence

- [blink2video](https://github.com/nico579/blink2video) by nico579 (GPL-3.0). It is not
  affiliated with this repository, and it is pulled in unmodified through its published Docker image.
- Blink is a trademark of Amazon. Neither this repository nor blink2video is affiliated with Blink or Amazon.
- The packaging files in this repository are released under the MIT licence (see `LICENSE`).
