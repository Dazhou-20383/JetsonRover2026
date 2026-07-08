"""Serve an image annotation page for receiving an image from action_node and returning point coordinates as percentages.

Run this module as a small local HTTP server. Upload a base64-encoded image through POST /image,
open the returned page in a browser, click points on the image, and submit the annotation list as
percentages of the original image width and height.
"""

from __future__ import annotations

import base64
import json
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


@dataclass
class ImageState:
  image_b64: str | None = None
  content_type: str = "image/jpeg"
  annotations: list[dict[str, float]] = field(default_factory=list)
  image_version: int = 0
  annotation_version: int = 0


STATE = ImageState()
STATE_LOCK = threading.Lock()


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Pragma", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Pragma", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def _render_page() -> str:
    with STATE_LOCK:
        image_b64 = STATE.image_b64 or ""
        content_type = STATE.content_type
        annotations = json.dumps(STATE.annotations)
        image_version = STATE.image_version

    image_src = f"data:{content_type};base64,{image_b64}" if image_b64 else ""

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Homography Annotation</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f1218;
      --panel: #151b23;
      --panel-2: #1b2330;
      --text: #e8edf2;
      --muted: #9aa7b6;
      --accent: #69d2ff;
      --accent-2: #7cffc8;
      --danger: #ff7a90;
      --border: rgba(255, 255, 255, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(105, 210, 255, 0.15), transparent 30%),
        radial-gradient(circle at bottom right, rgba(124, 255, 200, 0.12), transparent 28%),
        var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 24px 28px 8px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, rgba(255,255,255,0.04), transparent);
    }}
    h1 {{ margin: 0 0 8px; font-size: 22px; letter-spacing: 0.2px; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.9fr);
      gap: 18px;
      padding: 18px;
      align-items: start;
    }}
    .panel {{
      background: rgba(21, 27, 35, 0.92);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.28);
      overflow: hidden;
    }}
    .viewer {{ padding: 16px; }}
    .canvas-wrap {{ position: relative; width: 100%; }}
    img {{ width: 100%; display: block; border-radius: 12px; user-select: none; -webkit-user-drag: none; }}
    canvas {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      cursor: crosshair;
    }}
    .sidebar {{ padding: 18px; display: grid; gap: 14px; }}
    .card {{ background: var(--panel-2); border: 1px solid var(--border); border-radius: 14px; padding: 14px; }}
    .card h2 {{ margin: 0 0 8px; font-size: 15px; }}
    .coords {{
      min-height: 120px;
      max-height: 280px;
      overflow: auto;
      display: grid;
      gap: 8px;
      font-variant-numeric: tabular-nums;
    }}
    .coord {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 8px 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: rgba(255,255,255,0.03);
    }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    button {{
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      transition: transform 120ms ease, opacity 120ms ease, background 120ms ease;
    }}
    button:hover {{ transform: translateY(-1px); }}
    .primary {{ background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #071018; }}
    .secondary {{ background: rgba(255,255,255,0.07); color: var(--text); border: 1px solid var(--border); }}
    .danger {{ background: rgba(255, 122, 144, 0.15); color: #ffdce3; border: 1px solid rgba(255, 122, 144, 0.35); }}
    .empty {{ color: var(--muted); font-style: italic; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      color: #d6e1eb;
      font-size: 13px;
      line-height: 1.45;
    }}
    @media (max-width: 980px) {{
      main {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Homography Annotation</h1>
    <p>Click points on the image. The page stores them as percentages of the source image width and height.</p>
  </header>
  <main>
    <section class=\"panel viewer\">
      <div class=\"canvas-wrap\" id=\"wrap\">
        <img id=\"image\" alt=\"Uploaded frame\" src=\"{image_src}\" />
        <canvas id=\"overlay\"></canvas>
      </div>
    </section>
    <aside class=\"panel sidebar\">
      <div class=\"card\">
        <h2>Annotations</h2>
        <div id=\"coords\" class=\"coords\"></div>
      </div>
      <div class=\"card\">
        <h2>Actions</h2>
        <div class=\"actions\">
          <button class=\"primary\" id=\"submit\">Submit annotations</button>
          <button class=\"secondary\" id=\"clear\">Clear</button>
          <button class=\"danger\" id=\"remove\">Undo last</button>
        </div>
      </div>
      <div class=\"card\">
        <h2>Server state</h2>
        <pre id=\"state\"></pre>
      </div>
    </aside>
  </main>
  <script>
    const image = document.getElementById('image');
    const canvas = document.getElementById('overlay');
    const ctx = canvas.getContext('2d');
    const coordsEl = document.getElementById('coords');
    const stateEl = document.getElementById('state');
    const annotations = {annotations};
    let imageVersion = {image_version};

    function setImageSource(contentType, imageB64) {{
      if (!imageB64) {{
        image.removeAttribute('src');
        return;
      }}
      image.src = `data:${{contentType}};base64,${{imageB64}}`;
    }}

    function resizeCanvas() {{
      const rect = image.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(rect.width * window.devicePixelRatio));
      canvas.height = Math.max(1, Math.round(rect.height * window.devicePixelRatio));
      canvas.style.width = rect.width + 'px';
      canvas.style.height = rect.height + 'px';
      draw();
    }}

    function draw() {{
      const rect = image.getBoundingClientRect();
      ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
      ctx.clearRect(0, 0, rect.width, rect.height);
      annotations.forEach((point, index) => {{
        const x = rect.width * (point.x / 100);
        const y = rect.height * (point.y / 100);
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#69d2ff';
        ctx.strokeStyle = '#071018';
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#e8edf2';
        ctx.font = '12px ui-sans-serif, system-ui, sans-serif';
        ctx.fillText(String(index + 1), x + 10, y - 10);
      }});
      renderList();
      stateEl.textContent = JSON.stringify({{ count: annotations.length, annotations }}, null, 2);
    }}

    function renderList() {{
      coordsEl.innerHTML = '';
      if (!annotations.length) {{
        coordsEl.innerHTML = '<div class="empty">No points selected yet.</div>';
        return;
      }}
      annotations.forEach((point, index) => {{
        const row = document.createElement('div');
        row.className = 'coord';
        row.innerHTML = `<span>Point ${{index + 1}}</span><span>(${{point.x.toFixed(2)}}%, ${{point.y.toFixed(2)}}%)</span>`;
        coordsEl.appendChild(row);
      }});
    }}

    function addPoint(clientX, clientY) {{
      const rect = image.getBoundingClientRect();
      const x = ((clientX - rect.left) / rect.width) * 100;
      const y = ((clientY - rect.top) / rect.height) * 100;
      if (x < 0 || x > 100 || y < 0 || y > 100) {{
        return;
      }}
      annotations.push({{ x, y }});
      draw();
    }}

    canvas.addEventListener('click', (event) => {{
      addPoint(event.clientX, event.clientY);
    }});

    document.getElementById('clear').addEventListener('click', () => {{
      annotations.length = 0;
      draw();
    }});

    document.getElementById('remove').addEventListener('click', () => {{
      annotations.pop();
      draw();
    }});

    document.getElementById('submit').addEventListener('click', async () => {{
      const response = await fetch('/annotations', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ annotations }})
      }});
      const payload = await response.json();
      if (Array.isArray(payload.annotations)) {{
        annotations.length = 0;
        annotations.push(...payload.annotations);
        draw();
      }}
      stateEl.textContent = JSON.stringify(payload, null, 2);
    }});

    async function refreshImage() {{
      try {{
        const response = await fetch('/image', {{ cache: 'no-store' }});
        if (!response.ok) {{
          return;
        }}
        const payload = await response.json();
        if (typeof payload.version !== 'number' || payload.version === imageVersion) {{
          return;
        }}

        imageVersion = payload.version;
        annotations.length = 0;
        if (Array.isArray(payload.annotations)) {{
          annotations.push(...payload.annotations);
        }}
        setImageSource(payload.content_type, payload.image);
        draw();
      }} catch (error) {{
        console.error('Failed to refresh image:', error);
      }}
    }}

    window.addEventListener('resize', resizeCanvas);
    image.addEventListener('load', resizeCanvas);

    setInterval(refreshImage, 1000);
    refreshImage();

    if (image.complete && image.naturalWidth > 0) {{
      resizeCanvas();
    }} else {{
      renderList();
      stateEl.textContent = JSON.stringify({{ count: 0, annotations: [] }}, null, 2);
    }}
  </script>
</body>
</html>"""


class HomographyRequestHandler(BaseHTTPRequestHandler):
    server_version = "HomographyServer/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            _html_response(self, _render_page())
            return

        if parsed.path == "/image":
            with STATE_LOCK:
                if not STATE.image_b64:
                    _json_response(self, {"error": "No image uploaded yet."}, HTTPStatus.NOT_FOUND)
                    return
                payload = {
                  "version": STATE.image_version,
                    "content_type": STATE.content_type,
                    "image": STATE.image_b64,
                    "annotations": STATE.annotations,
                }
            _json_response(self, payload)
            return

        if parsed.path == "/annotations":
            with STATE_LOCK:
                payload = {"annotations": STATE.annotations}
            _json_response(self, payload)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown path")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""

        if parsed.path == "/image":
            self._handle_image_upload(raw_body)
            return

        if parsed.path == "/annotations":
            self._handle_annotations(raw_body)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown path")

    def _handle_image_upload(self, raw_body: bytes) -> None:
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        image_b64 = None
        image_content_type = "image/jpeg"

        if content_type == "application/json":
            try:
                payload = json.loads(raw_body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                _json_response(self, {"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
                return

            image_b64 = payload.get("image") or payload.get("image_b64")
            image_content_type = payload.get("content_type", image_content_type)
        elif content_type in {"text/plain", "application/octet-stream", "image/jpeg", "image/png"}:
            image_b64 = base64.b64encode(raw_body).decode("ascii")
            image_content_type = content_type if content_type.startswith("image/") else image_content_type
        else:
            form = parse_qs(raw_body.decode("utf-8", errors="ignore"))
            image_b64 = form.get("image", [None])[0]
            image_content_type = form.get("content_type", [image_content_type])[0]

        if not image_b64:
            _json_response(self, {"error": "Missing image data."}, HTTPStatus.BAD_REQUEST)
            return

        with STATE_LOCK:
            STATE.image_b64 = image_b64
            STATE.content_type = image_content_type or "image/jpeg"
            STATE.annotations = []
            STATE.image_version += 1
            STATE.annotation_version += 1

        _json_response(
            self,
            {
                "success": True,
            "version": STATE.image_version,
                "message": "Image stored. Open GET / in a browser to annotate it.",
            },
        )

    def _handle_annotations(self, raw_body: bytes) -> None:
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            _json_response(self, {"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
            return

        annotations = payload.get("annotations")
        if not isinstance(annotations, list):
            _json_response(self, {"error": "annotations must be a list."}, HTTPStatus.BAD_REQUEST)
            return

        normalized: list[dict[str, float]] = []
        for index, point in enumerate(annotations):
            if not isinstance(point, dict) or "x" not in point or "y" not in point:
                _json_response(
                    self,
                    {"error": f"Invalid annotation at index {index}. Each point must have x and y."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            try:
                normalized.append({"x": float(point["x"]), "y": float(point["y"])})
            except (TypeError, ValueError):
                _json_response(
                    self,
                    {"error": f"Invalid numeric values at index {index}."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

        with STATE_LOCK:
            STATE.annotations = normalized
            STATE.annotation_version += 1

        _json_response(self, {"success": True, "annotations": normalized, "version": STATE.annotation_version})

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    """Start the annotation server and return the HTTP server instance."""
    server = ThreadingHTTPServer((host, port), HomographyRequestHandler)
    return server


def main(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run the annotation server until interrupted."""
    server = serve(host=host, port=port)
    print(f"Homography server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()