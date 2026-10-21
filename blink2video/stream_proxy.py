#!/usr/bin/env python3
"""MJPEG restreamer for blink2video's live view (stdlib only, needs ffmpeg).

blink2video's live view needs a per-process token, needs the Host header to be
trusted, and Blink ends every live session after about 6 minutes. This small
server hides all of that behind stable, token-less URLs so Home Assistant's
"MJPEG IP Camera" integration can use it as an ordinary camera:

  /stream[?camera=NAME]  multipart MJPEG; connects to Blink only while at least
                         one client is watching, and reconnects by itself when
                         Blink closes the session. Repeats the last frame during
                         the reconnect gap so clients do not time out.
  /still.jpg[?camera=NAME]  newest live frame if one is fresh, else Blink's
                         cached thumbnail. Never starts a live session.
  /health

Only one live session can run at a time on a Blink sync module, so opening the
blink2video web UI's live view while this is streaming will be refused (409).
"""
import http.server
import json
import os
import queue
import re
import socketserver
import subprocess
import threading
import time
import urllib.parse
import urllib.request

BASE = os.environ.get("B2V_URL", "http://127.0.0.1:8765")
PORT = int(os.environ.get("STREAM_PORT", "8766"))
FPS = int(os.environ.get("STREAM_FPS", "10"))
WIDTH = int(os.environ.get("STREAM_WIDTH", "1280"))
QUALITY = os.environ.get("STREAM_QUALITY", "6")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
IDLE_GRACE = 8          # seconds with no viewer before the Blink session is closed
KEEPALIVE = 2.0         # repeat the last frame this often when nothing new arrives
FRESH = 10              # a live frame younger than this is served as the still
BOUNDARY = "b2vframe"


def log(*args):
    print("[stream]", *args, flush=True)


def fetch(path, token=None, timeout=20):
    request = urllib.request.Request(BASE + path)
    if token:
        request.add_header("X-Blink-Token", token)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def get_token():
    match = re.search(rb'BLINK_TOKEN = "([0-9a-f]{32})"', fetch("/"))
    if not match:
        raise RuntimeError("blink2video token not found (not signed in yet?)")
    return match.group(1).decode()


def find_camera(token, wanted):
    data = json.loads(fetch("/api/system", token))
    cameras = [c for s in data.get("systems", []) for c in s.get("cameras", [])]
    if not cameras:
        raise RuntimeError("blink2video reports no cameras")
    if wanted:
        for camera in cameras:
            if wanted.lower() in camera["name"].lower():
                return camera
        raise RuntimeError(f"no camera matching {wanted!r}")
    return cameras[0]


class Broadcaster:
    """One ffmpeg per camera, shared by every connected viewer."""

    def __init__(self, wanted):
        self.wanted = wanted
        self.lock = threading.Lock()
        self.clients = set()
        self.running = False
        self.last = None
        self.last_time = 0.0

    def subscribe(self):
        client = queue.Queue(maxsize=20)
        with self.lock:
            self.clients.add(client)
            if not self.running:
                self.running = True
                threading.Thread(target=self.loop, daemon=True).start()
        return client

    def unsubscribe(self, client):
        with self.lock:
            self.clients.discard(client)

    def publish(self, frame):
        self.last, self.last_time = frame, time.time()
        for client in list(self.clients):
            try:
                client.put_nowait(frame)
            except queue.Full:
                try:
                    client.get_nowait()
                    client.put_nowait(frame)
                except (queue.Empty, queue.Full):
                    pass

    def idle_since(self):
        return None if self.clients else time.time()

    def loop(self):
        log("watcher started for", self.wanted or "first camera")
        delay = 2
        idle = None
        try:
            while True:
                if not self.clients:
                    idle = idle or time.time()
                    if time.time() - idle > IDLE_GRACE:
                        return
                    time.sleep(1)
                    continue
                idle = None
                started = time.time()
                frames = self.session()
                # A session that delivered frames resets the back-off; failures grow it.
                delay = 2 if frames else min(delay * 2, 30)
                if time.time() - started < 1:
                    delay = max(delay, 3)
                time.sleep(delay)
        finally:
            with self.lock:
                if self.clients:      # someone subscribed as we were exiting
                    threading.Thread(target=self.loop, daemon=True).start()
                else:
                    self.running = False
            log("watcher stopped")

    def session(self):
        frames = 0
        try:
            token = get_token()
            camera = find_camera(token, self.wanted)
            url = f"{BASE}/live-mse/{urllib.parse.quote(camera['key'])}?token={token}"
            log("opening live session for", camera["name"])
            process = subprocess.Popen(
                [FFMPEG, "-hide_banner", "-loglevel", "error", "-fflags", "nobuffer",
                 "-i", url, "-an", "-vf", f"fps={FPS},scale={WIDTH}:-2",
                 "-c:v", "mjpeg", "-q:v", QUALITY, "-f", "image2pipe", "-"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as error:  # noqa: BLE001 - keep the watcher alive
            log("cannot start session:", error)
            return 0

        def watchdog():
            gone = None
            while process.poll() is None:
                time.sleep(1)
                if self.clients:
                    gone = None
                else:
                    gone = gone or time.time()
                    if time.time() - gone > IDLE_GRACE:
                        process.terminate()
        threading.Thread(target=watchdog, daemon=True).start()
        threading.Thread(
            target=lambda: [log("ffmpeg:", line.decode(errors="replace").strip())
                            for line in iter(process.stderr.readline, b"")],
            daemon=True).start()

        buffer = b""
        try:
            while True:
                chunk = process.stdout.read1(65536)
                if not chunk:
                    break
                buffer += chunk
                while True:
                    start = buffer.find(b"\xff\xd8")
                    if start < 0:
                        buffer = b""
                        break
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        buffer = buffer[start:]
                        break
                    self.publish(buffer[start:end + 2])
                    buffer = buffer[end + 2:]
                    frames += 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            log(f"session ended after {frames} frames")
        return frames


BROADCASTERS = {}
BROADCASTERS_LOCK = threading.Lock()


def broadcaster(wanted):
    with BROADCASTERS_LOCK:
        if wanted not in BROADCASTERS:
            BROADCASTERS[wanted] = Broadcaster(wanted)
        return BROADCASTERS[wanted]


def cached_thumb(wanted):
    token = get_token()
    camera = find_camera(token, wanted)
    return fetch(f"/camthumb/{urllib.parse.quote(camera['key'])}?token={token}", timeout=30)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def reply(self, status, body, content_type="text/plain"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        wanted = urllib.parse.parse_qs(parsed.query).get("camera", [""])[0]
        if parsed.path == "/health":
            return self.reply(200, b"ok")
        if parsed.path == "/still.jpg":
            try:
                live = broadcaster(wanted)
                frame = live.last if live.last and time.time() - live.last_time < FRESH else None
                return self.reply(200, frame or cached_thumb(wanted), "image/jpeg")
            except Exception as error:  # noqa: BLE001
                return self.reply(502, str(error).encode())
        if parsed.path == "/stream":
            return self.stream(wanted)
        self.reply(404, b"not found")

    def stream(self, wanted):
        live = broadcaster(wanted)
        client = live.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            # Headers are out; send something quickly so clients with short
            # read timeouts do not give up while the camera wakes up.
            last = live.last
            if last is None:
                try:
                    last = cached_thumb(wanted)
                except Exception:  # noqa: BLE001
                    last = None
            while True:
                try:
                    last = client.get(timeout=KEEPALIVE)
                except queue.Empty:
                    pass
                if last is None:
                    continue
                self.wfile.write(
                    f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                    f"Content-Length: {len(last)}\r\n\r\n".encode() + last + b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            live.unsubscribe(client)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    log(f"listening on :{PORT}, upstream {BASE}, {WIDTH}px @ {FPS} fps")
    Server(("0.0.0.0", PORT), Handler).serve_forever()
