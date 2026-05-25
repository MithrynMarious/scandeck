"""Branch-aware reverse proxy for local service routing."""

import http.server
import json
import socketserver
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


def load_topology(repo_path: Optional[str] = None) -> dict:
    """Load service topology from .scandeck.json in the repo."""
    root = Path(repo_path) if repo_path else Path.cwd()
    cfg_path = root / ".scandeck.json"
    if not cfg_path.exists():
        return {}
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data.get("services", {})
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_target(host: str, services: dict) -> Optional[int]:
    """Resolve a Host header to a backend port.

    Patterns:
      service.branch.project.localhost -> services[service][branch] or services[service][default]
      service.localhost -> services[service][default]
    """
    parts = host.split(".")
    if not parts:
        return None

    parts = [p for p in parts if p not in ("localhost", "127", "0", "1")]
    if not parts:
        return None

    service_name = parts[0]
    branch = parts[1] if len(parts) > 1 else None

    svc = services.get(service_name)
    if not svc:
        return None

    if isinstance(svc, int):
        return svc

    if isinstance(svc, dict):
        if branch and branch in svc:
            return svc[branch]
        return svc.get("default")

    return None


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    services: dict = {}

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def do_PATCH(self):
        self._proxy()

    def do_HEAD(self):
        self._proxy()

    def do_OPTIONS(self):
        self._proxy()

    def _proxy(self):
        host = self.headers.get("Host", "").split(":")[0]
        port = resolve_target(host, self.services)
        if port is None:
            self.send_error(502, f"No service mapped for host: {host}")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        target_url = f"http://127.0.0.1:{port}{self.path}"

        headers = {}
        for key, val in self.headers.items():
            if key.lower() not in ("host", "connection"):
                headers[key] = val

        req = urllib.request.Request(
            target_url,
            data=body,
            headers=headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.end_headers()
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for key, val in e.headers.items():
                if key.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(key, val)
            self.end_headers()
            self.wfile.write(e.read())
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            self.send_error(502, f"Backend unavailable: {e}")

    def log_message(self, format, *args):
        host = self.headers.get("Host", "?") if hasattr(self, "headers") and self.headers else "?"
        port = resolve_target(host.split(":")[0], self.services) if self.services else "?"
        print(f"  {host} -> :{port}  {format % args}")


def run_proxy(port: int = 8400, repo_path: Optional[str] = None):
    """Start the reverse proxy server."""
    services = load_topology(repo_path)
    if not services:
        print("No services found in .scandeck.json")
        print("Create a .scandeck.json with a 'services' map:")
        print('  {"services": {"web": {"default": 3000}, "api": {"default": 8080}}}')
        return

    ProxyHandler.services = services

    print(f"ScanDeck proxy on :{port}")
    print(f"Services: {len(services)}")
    for name, cfg in services.items():
        if isinstance(cfg, int):
            print(f"  {name}.localhost:{port} -> :{cfg}")
        elif isinstance(cfg, dict):
            for branch, bport in cfg.items():
                label = f"{name}.localhost" if branch == "default" else f"{name}.{branch}.localhost"
                print(f"  {label}:{port} -> :{bport}")
    print()

    with socketserver.TCPServer(("", port), ProxyHandler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nProxy stopped.")
