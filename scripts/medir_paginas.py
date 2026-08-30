# -*- coding: utf-8 -*-
"""Measure each report page against the printable area of an A4 sheet.

Eyeballing a PDF to find which section overflows is slow and imprecise. This
loads the same HTML in the same engine that prints it and reports, per page,
how much taller than the frame the content runs.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

# A4 is 297mm tall; @page reserves 16mm top and 14mm bottom.
MM_PX = 96 / 25.4
FRAME = round((297 - 18 - 15) * MM_PX)

src = "file:///" + os.path.abspath("out/reporte_agrojuntos.html").replace("\\", "/")

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="chrome")
    page = browser.new_page(viewport={"width": round(180 * MM_PX), "height": 900})
    page.goto(src, wait_until="networkidle")
    page.emulate_media(media="print")
    rows = page.evaluate("""() => [...document.querySelectorAll('.page')].map(p => {
        const h = p.getBoundingClientRect().height;
        const k = p.querySelector('.kicker');
        const t = p.querySelector('h2.title');
        const lbl = (k ? k.textContent.trim() + ' — ' : '') +
                    (t ? t.textContent.replace(/\s+/g, ' ').trim() : '');
        return {t: lbl.slice(0, 62) || 'sin título', h: Math.round(h)};
    })""")
    browser.close()

print(f"marco imprimible: {FRAME} px\n")
bad = 0
for i, r in enumerate(rows, 1):
    over = r["h"] - FRAME
    flag = f"DESBORDA +{over}px" if over > 0 else "ok"
    if over > 0:
        bad += 1
    print(f"{i:>2}. {r['t']:<48} {r['h']:>5}px  {flag}")
print(f"\n{bad} de {len(rows)} paginas desbordan")
sys.exit(1 if bad else 0)
