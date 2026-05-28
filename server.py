#!/usr/bin/env python3
"""
Okolica.ai - web server za Render.com deploy
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import http.server
import os
import sys

# Na Renderu port dolazi iz environment varijable, lokalno 8765
PORT = int(os.environ.get("PORT", 8765))

# API ključ čitamo iz environment varijable (postavlja se na Renderu)
# Za lokalno testiranje: set ANTHROPIC_API_KEY=sk-ant-... (Windows)
#                        export ANTHROPIC_API_KEY=sk-ant-... (Mac/Linux)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

HTML_FILE = os.path.join(os.path.dirname(__file__), "index.html")

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {args[0]} {args[1]}")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, content):
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            with open(HTML_FILE, "r", encoding="utf-8") as f:
                self.send_html(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except Exception:
            self.send_json({"error": "Invalid JSON"}, 400)
            return

        if self.path == "/api/geocode":
            self._geocode(payload)
        elif self.path == "/api/reverse":
            self._reverse(payload)
        elif self.path == "/api/autocomplete":
            self._autocomplete(payload)
        elif self.path == "/api/overpass":
            self._overpass(payload)
        elif self.path == "/api/claude":
            self._claude(payload)
        else:
            self.send_json({"error": "Not found"}, 404)

    def _geocode(self, payload):
        address = payload.get("address", "")
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": address, "format": "json", "limit": "1", "addressdetails": "1"
        })
        req = urllib.request.Request(url, headers={
            "User-Agent": "OkolicaAI/1.0 (edukacijska aplikacija)"
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            self.send_json(data)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def _overpass(self, payload):
        query = payload.get("query", "")
        endpoints = [
            "https://overpass-api.de/api/interpreter",
            "https://lz4.overpass-api.de/api/interpreter",
            "https://z.overpass-api.de/api/interpreter",
        ]
        body = ("data=" + urllib.parse.quote(query)).encode()
        last_err = None
        for ep in endpoints:
            try:
                req = urllib.request.Request(ep, data=body, method="POST", headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "OkolicaAI/1.0"
                })
                with urllib.request.urlopen(req, timeout=25) as r:
                    data = json.loads(r.read())
                self.send_json(data)
                return
            except Exception as e:
                last_err = e
                continue
        self.send_json({"error": f"Overpass nedostupan: {last_err}"}, 500)

    def _claude(self, payload):
        if not ANTHROPIC_API_KEY:
            self.send_json({"error": "API ključ nije postavljen! Dodaj ANTHROPIC_API_KEY u Render environment varijable."}, 400)
            return

        body = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "messages": payload.get("messages", [])
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            self.send_json(data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            self.send_json({"error": f"Anthropic greška {e.code}: {err_body}"}, 500)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("UPOZORENJE: ANTHROPIC_API_KEY nije postavljen!")

    print(f"Server pokrenut na portu {PORT}")
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server zaustavljen.")


    def _autocomplete(self, payload):
        q = payload.get("q", "")
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
            "q": q, "format": "json", "limit": "6", "addressdetails": "1",
            "accept-language": "hr"
        })
        req = urllib.request.Request(url, headers={
            "User-Agent": "OkolicaAI/1.0 (edukacijska aplikacija)"
        })
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            results = []
            for item in data:
                addr = item.get("address", {})
                parts = [
                    addr.get("road") or addr.get("pedestrian") or addr.get("footway", ""),
                    addr.get("house_number", ""),
                ]
                main = " ".join(p for p in parts if p).strip() or item.get("display_name", "").split(",")[0]
                sub_parts = [
                    addr.get("suburb") or addr.get("neighbourhood", ""),
                    addr.get("city") or addr.get("town") or addr.get("village", ""),
                    addr.get("country", ""),
                ]
                sub = ", ".join(p for p in sub_parts if p)
                results.append({
                    "display_name": item["display_name"],
                    "display_main": main,
                    "display_sub": sub,
                    "lat": item["lat"],
                    "lon": item["lon"],
                })
            self.send_json({"results": results})
        except Exception as e:
            self.send_json({"results": [], "error": str(e)})

    def _reverse(self, payload):
        lat = payload.get("lat")
        lon = payload.get("lon")
        url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode({
            "lat": lat, "lon": lon, "format": "json",
            "zoom": "18", "addressdetails": "1", "accept-language": "hr"
        })
        req = urllib.request.Request(url, headers={
            "User-Agent": "OkolicaAI/1.0 (edukacijska aplikacija)"
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            self.send_json(data)
        except Exception as e:
            self.send_json({"error": str(e), "display_name": f"{lat}, {lon}"}, 200)
