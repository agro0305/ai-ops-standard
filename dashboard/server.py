#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    data_dir=Path('.')
    def do_GET(self):
        if self.path=="/api/reports":
            items=[]
            for p in sorted(self.data_dir.glob("*.json")):
                try: items.append({"name":p.name,"data":json.loads(p.read_text(encoding="utf-8"))})
                except Exception as e: items.append({"name":p.name,"error":str(e)})
            body=json.dumps(items).encode()
            self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(body); return
        rows=[]
        for p in sorted(self.data_dir.glob("*.json")):
            rows.append(f"<tr><td>{html.escape(p.name)}</td><td>{p.stat().st_size}</td></tr>")
        page=f"""<!doctype html><html><head><meta charset='utf-8'><title>AI-OPS Dashboard</title>
<style>body{{font-family:system-ui;margin:2rem;background:#111;color:#eee}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #555;padding:.6rem;text-align:left}}code{{color:#9fe}}</style></head>
<body><h1>AI-OPS Dashboard</h1><p>Read-only local report index.</p><table><tr><th>Report</th><th>Bytes</th></tr>{''.join(rows)}</table><p>JSON API: <code>/api/reports</code></p></body></html>""".encode()
        self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.end_headers(); self.wfile.write(page)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",default="."); ap.add_argument("--host",default="127.0.0.1"); ap.add_argument("--port",type=int,default=8787); a=ap.parse_args()
    Handler.data_dir=Path(a.data_dir); print(f"http://{a.host}:{a.port}"); ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=="__main__": main()
