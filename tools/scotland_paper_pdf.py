"""Print a briefing paper to PDF from its rendered page (needs playwright).

    uv run --with playwright python tools/scotland_paper_pdf.py 2026
"""
import functools, http.server, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ed = sys.argv[1]
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(
    http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "site")))
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}/papers/scotland-{ed}/index.html"
out = ROOT / f"site/papers/scotland-{ed}/scotland-claims-{ed}.pdf"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 900, "height": 1200})
    pg.goto(url, wait_until="networkidle")
    pg.add_style_tag(content=".masthead nav,.footer,.paper-actions{display:none!important} body{background:#fff}")
    pg.pdf(path=str(out), format="A4", print_background=False,
           margin={"top": "16mm", "bottom": "16mm", "left": "16mm", "right": "16mm"})
    b.close()
srv.shutdown()
print("wrote", out)
