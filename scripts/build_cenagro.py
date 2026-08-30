# -*- coding: utf-8 -*-
"""Extract the departmental annex tables from the IV CENAGRO 2012 PDF.

The PDF's text layer emits one value per line in reading order, so each table
is recovered by walking the department names in census order and taking the
next N numeric tokens.
"""
import re
import fitz
import pandas as pd

PDF = "data/cenagro2012.pdf"

DEPS = ["Amazonas", "Áncash", "Apurímac", "Arequipa", "Ayacucho", "Cajamarca",
        "Callao", "Cusco", "Huancavelica", "Huánuco", "Ica", "Junín",
        "La Libertad", "Lambayeque", "Lima", "Loreto", "Madre de Dios",
        "Moquegua", "Pasco", "Piura", "Puno", "San Martín", "Tacna", "Tumbes",
        "Ucayali"]

# page index (0-based) -> (output name, column labels)
TABLES = {
    43: ("productores", ["productores", "pct"]),
    52: ("ua_por_tamano", ["ua_total", "ha_0_5", "ha_5_10", "ha_10_20",
                           "ha_20_50", "ha_50_100", "ha_100_mas"]),
}


def num(tok):
    t = tok.strip().replace("\xa0", "").replace(" ", "")
    t = t.replace(".", "").replace(",", ".")
    if t.startswith("."):
        t = "0" + t
    return float(t)


def norm(s):
    s = s.replace("\ufffd", "?")
    return re.sub(r"[^a-z]", "", s.lower()
                  .replace("á", "a").replace("é", "e").replace("í", "i")
                  .replace("ó", "o").replace("ú", "u").replace("?", ""))


def parse_page(page, cols):
    lines = [l.strip() for l in page.get_text().split("\n") if l.strip()]
    idx = {norm(d): i for i, d in enumerate(DEPS)}
    rows, i = {}, 0
    while i < len(lines):
        key = norm(lines[i])
        if key in idx and key not in rows:
            vals = []
            j = i + 1
            while j < len(lines) and len(vals) < len(cols):
                try:
                    vals.append(num(lines[j]))
                except ValueError:
                    break
                j += 1
            if len(vals) == len(cols):
                rows[key] = (DEPS[idx[key]], vals)
                i = j
                continue
        i += 1
    out = pd.DataFrame([[n] + v for n, v in rows.values()], columns=["dep"] + cols)
    return out


doc = fitz.open(PDF)
frames = {}
for pg, (name, cols) in TABLES.items():
    df = parse_page(doc[pg], cols)
    frames[name] = df
    print(f"{name}: {len(df)} departamentos")

prod = frames["productores"][["dep", "productores"]]
tam = frames["ua_por_tamano"]
m = prod.merge(tam, on="dep", how="outer")

# Segments that matter for a B2B agri-input marketplace.
m["ua_micro_0_5"] = m["ha_0_5"]
m["ua_pequeno_5_20"] = m["ha_5_10"] + m["ha_10_20"]
m["ua_mediano_20_100"] = m["ha_20_50"] + m["ha_50_100"]
m["ua_grande_100_mas"] = m["ha_100_mas"]
m["ua_objetivo_5_mas"] = m["ua_pequeno_5_20"] + m["ua_mediano_20_100"] + m["ua_grande_100_mas"]
m["pct_objetivo"] = 100 * m["ua_objetivo_5_mas"] / m["ua_total"]

m = m.sort_values("ua_objetivo_5_mas", ascending=False)
m.to_csv("out/cenagro_departamento.csv", index=False, encoding="utf-8-sig")

print(f"\nTOTAL productores = {prod['productores'].sum():,.0f}")
print(f"TOTAL UA          = {tam['ua_total'].sum():,.0f}")
print(f"TOTAL UA >5 ha    = {m['ua_objetivo_5_mas'].sum():,.0f}\n")
cols = ["dep", "productores", "ua_total", "ua_micro_0_5", "ua_pequeno_5_20",
        "ua_mediano_20_100", "ua_grande_100_mas", "ua_objetivo_5_mas", "pct_objetivo"]
print(m[cols].to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
