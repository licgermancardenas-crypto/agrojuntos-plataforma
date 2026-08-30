# -*- coding: utf-8 -*-
"""Build the addressable-customer funnel from CENAGRO's departmental annexes.

"Producers >5 ha" is too blunt a definition of a customer. AgroJuntos sells
crop-protection and nutrition products, on invoice, with delivery and credit.
So the census is asked four narrower questions, each of which is a real
purchasing behaviour rather than a proxy:

  Anexo 15  applies chemical fertiliser        -> already buys nutrition
  Anexo 10  applies pesticides                 -> already buys crop protection
  Anexo 18  used credit to buy inputs          -> already buys the way we sell
  Anexo 04  is a legal entity (not natural person) -> can be invoiced, can be
                                                     underwritten for credit

The intersection of scale and purchasing behaviour is the real SOM base.
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


def num(t):
    t = t.strip().replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", ".")
    return float("0" + t if t.startswith(".") else t)


def norm(s):
    s = (s.lower().replace("á", "a").replace("é", "e").replace("í", "i")
         .replace("ó", "o").replace("ú", "u").replace("�", ""))
    return re.sub(r"[^a-z]", "", s)


def parse(pg, ncols):
    """Read a departmental annex: department name followed by ncols numbers."""
    lines = [l.strip() for l in fitz.open(PDF)[pg].get_text().split("\n") if l.strip()]
    # Some rows pack several numbers into one line; split them out first.
    flat = []
    for l in lines:
        if re.fullmatch(r"[\d \.,]+", l) and len(re.findall(r"\d[\d ]*[,.]?\d*", l)) > 1:
            flat.extend(re.findall(r"\d[\d ]*(?:[,.]\d+)?", l))
        else:
            flat.append(l)
    idx = {norm(d): i for i, d in enumerate(DEPS)}
    got = {}
    i = 0
    while i < len(flat):
        k = norm(flat[i])
        if k in idx and k not in got:
            vals, j = [], i + 1
            while j < len(flat) and len(vals) < ncols:
                try:
                    vals.append(num(flat[j]))
                except ValueError:
                    break
                j += 1
            if len(vals) == ncols:
                got[k] = (DEPS[idx[k]], vals)
                i = j
                continue
        i += 1
    return got


# --- Anexo 15 (p56): fertiliser -> total, suficiente, poca, no aplica -------
fert = parse(55, 4)
# --- Anexo 10 (p51): pesticides, 4 blocks of (total, si, no) ---------------
pest = parse(50, 12)
# --- Anexo 18 (p59): credit destination -> total, insumos, maq, herr, com, otro
cred = parse(58, 6)
# --- Anexo 04 (p45): legal form -> total, persona natural, then entity types
jur = parse(44, 3)

rows = []
for k, (name, f) in fert.items():
    p = pest.get(k, (None, [0] * 12))[1]
    c = cred.get(k, (None, [0] * 6))[1]
    j = jur.get(k, (None, [0, 0, 0]))[1]
    rows.append({
        "dep": name,
        "ua_total": f[0],
        "fert_suficiente": f[1],
        "fert_poca": f[2],
        "fert_si": f[1] + f[2],
        "pest_si": p[1],                 # first block: insecticidas
        "cred_total": c[0],
        "cred_insumos": c[1],
        "prod_total": j[0],
        "persona_natural": j[1],
    })

df = pd.DataFrame(rows)
df["juridica"] = df["prod_total"] - df["persona_natural"]

cen = pd.read_csv("out/cenagro_departamento.csv", encoding="utf-8-sig")


def key(s):
    s = norm(str(s))
    return {"ncash": "ancash", "apurmac": "apurimac", "hunuco": "huanuco",
            "junn": "junin", "sanmartn": "sanmartin"}.get(s, s)


df["k"] = df["dep"].map(key)
cen["k"] = cen["dep"].map(key)
m = cen[["k", "ua_total", "ua_objetivo_5_mas"]].rename(
    columns={"ua_total": "ua_tot_c"}).merge(df.drop(columns="ua_total"), on="k")

# --- funnel ---------------------------------------------------------------
# Rate of each behaviour within the department, applied to the >5 ha segment.
# Commercial farms adopt inputs more than average, but we do NOT inflate for
# that here: the un-adjusted rate keeps the estimate conservative.
m["tasa_fert"] = m["fert_si"] / m["ua_tot_c"]
m["tasa_pest"] = m["pest_si"] / m["ua_tot_c"]
m["tasa_credito"] = m["cred_insumos"] / m["ua_tot_c"]
m["tasa_juridica"] = m["juridica"] / m["prod_total"]

m["compradores_insumos"] = m["ua_objetivo_5_mas"] * m[["tasa_fert", "tasa_pest"]].max(axis=1)
m["compran_a_credito"] = m["ua_objetivo_5_mas"] * m["tasa_credito"]
m["formales"] = m["ua_objetivo_5_mas"] * m["tasa_juridica"]

m = m.sort_values("compradores_insumos", ascending=False)
m.to_csv("out/embudo_departamento.csv", index=False, encoding="utf-8-sig")

T = m.sum(numeric_only=True)
print("=" * 72)
print("EMBUDO DE CLIENTES  (base: IV CENAGRO 2012)")
print("=" * 72)
steps = [
    ("Productores agropecuarios", T.prod_total, ""),
    ("Unidades agropecuarias", T.ua_tot_c, ""),
    ("  con mas de 5 ha", T.ua_objetivo_5_mas, "escala minima para compra recurrente"),
    ("  que compran insumos", T.compradores_insumos, "aplican fertilizante o pesticida"),
    ("  que compran a credito", T.compran_a_credito, "usan credito para insumos"),
]
base = T.prod_total
for lab, v, note in steps:
    print(f"{lab:<28} {v:>12,.0f}   {100*v/base:>5.1f}%   {note}")
print()
print(f"{'Personas juridicas (todas)':<28} {T.juridica:>12,.0f}   "
      f"{100*T.juridica/base:>5.1f}%   facturables y sujetas a credito")
print()
print("--- POR DEPARTAMENTO ---")
show = m[["dep", "ua_objetivo_5_mas", "compradores_insumos", "compran_a_credito",
          "tasa_fert", "tasa_pest", "tasa_credito"]].copy()
for c in ("tasa_fert", "tasa_pest", "tasa_credito"):
    show[c] = (100 * show[c]).round(1)
print(show.to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
