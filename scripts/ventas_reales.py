# -*- coding: utf-8 -*-
"""Read AgroJuntos' own sales ledger and derive the real commercial metrics.

These are the numbers a term sheet gets argued over, so every figure here comes
from the invoice lines rather than from the deck: ticket size, purchase
frequency, repeat rate, product mix and delivery geography.

Columns are positionally stable; blanks are simply empty cells. Header is row 2.
"""
import datetime as dt
import pandas as pd

SRC = "../17-10-25 COMPRA Y VENTA DE MERCADERÍA.xlsx"
COLS = {0: "fecha", 1: "ruc", 2: "cliente", 3: "doc", 4: "producto",
        5: "cantidad", 6: "unidad", 7: "pu", 8: "total_linea", 9: "moneda",
        10: "tc", 14: "facturado", 15: "facturado_soles", 17: "forma_pago",
        22: "estado_pago", 28: "zona", 29: "distrito", 30: "provincia",
        31: "departamento"}

raw = pd.read_excel(SRC, sheet_name="VENTAS", header=None)
df = raw.iloc[3:, list(COLS)].copy()
df.columns = list(COLS.values())
df = df[df["fecha"].apply(lambda v: isinstance(v, (dt.datetime, pd.Timestamp)))]
df["fecha"] = pd.to_datetime(df["fecha"])

# A sale spans several product lines; identifying fields appear only on the first.
for c in ("ruc", "cliente", "doc", "moneda", "tc", "forma_pago",
          "zona", "distrito", "provincia", "departamento"):
    df[c] = df[c].ffill()
df["doc"] = df["doc"].astype(str).str.strip()
df["ruc"] = df["ruc"].astype(str).str.split(".").str[0].str.strip()
for c in ("cliente", "moneda", "forma_pago", "producto", "departamento",
          "provincia", "distrito"):
    df[c] = df[c].astype(str).str.strip().str.upper().replace({"NAN": ""})
for c in ("cantidad", "pu", "total_linea", "tc"):
    df[c] = pd.to_numeric(df[c], errors="coerce")

# Normalise every line to USD. The sheet books most sales in soles.
TC_DEF = 3.75
df["tc"] = df["tc"].where(df["tc"].between(2, 5), TC_DEF)
df["linea_usd"] = df.apply(
    lambda r: r["total_linea"] / (r["tc"] if r["moneda"] == "SOLES" else 1), axis=1)
df = df.dropna(subset=["linea_usd"])

df.to_csv("out/ventas_lineas.csv", index=False, encoding="utf-8-sig")

# ---- per sale -------------------------------------------------------------
ventas = (df.groupby("doc")
          .agg(fecha=("fecha", "min"), ruc=("ruc", "first"),
               cliente=("cliente", "first"), usd=("linea_usd", "sum"),
               lineas=("producto", "size"), pago=("forma_pago", "first"),
               dep=("departamento", "first"))
          .sort_values("fecha"))
ventas.to_csv("out/ventas_doc.csv", encoding="utf-8-sig")

# ---- per client -----------------------------------------------------------
cli = (ventas.groupby("ruc")
       .agg(cliente=("cliente", "first"), compras=("usd", "size"),
            usd=("usd", "sum"), ticket=("usd", "mean"),
            primera=("fecha", "min"), ultima=("fecha", "max"))
       .sort_values("usd", ascending=False))
cli["dias"] = (cli["ultima"] - cli["primera"]).dt.days
cli["frec_dias"] = (cli["dias"] / (cli["compras"] - 1)).where(cli["compras"] > 1)
cli.to_csv("out/ventas_cliente.csv", encoding="utf-8-sig")

meses = (ventas.fecha.max() - ventas.fecha.min()).days / 30.44
rec = cli[cli.compras > 1]

print("=" * 66)
print("VENTAS REALES AGROJUNTOS")
print("=" * 66)
print(f"periodo               : {ventas.fecha.min():%b %Y} - {ventas.fecha.max():%b %Y}  ({meses:.1f} meses)")
print(f"ventas totales        : US$ {ventas.usd.sum():,.0f}")
print(f"documentos            : {len(ventas)}")
print(f"clientes unicos       : {len(cli)}")
print(f"ticket promedio       : US$ {ventas.usd.mean():,.0f}")
print(f"ticket mediano        : US$ {ventas.usd.median():,.0f}")
print(f"ticket max            : US$ {ventas.usd.max():,.0f}")
print(f"clientes recurrentes  : {len(rec)} de {len(cli)}  ({100*len(rec)/len(cli):.0f}%)")
if len(rec):
    print(f"frecuencia recompra   : {rec.frec_dias.median():.0f} dias  ({rec.frec_dias.median()/30.44:.1f} meses)")
    print(f"valor cliente recurr. : US$ {rec.usd.mean():,.0f}")
print(f"% credito (docs)      : {100*(ventas.pago=='CRÉDITO').mean():.0f}%")
print()
print("--- CLIENTES ---")
show = cli.copy()
show["cliente"] = show["cliente"].str.slice(0, 34)
print(show[["cliente", "compras", "usd", "ticket", "frec_dias"]]
      .to_string(float_format=lambda v: f"{v:,.0f}"))
print()
print("--- GEOGRAFIA DE ENTREGA ---")
geo = df[df.departamento != ""].groupby(["departamento", "provincia"]).agg(
    docs=("doc", "nunique"), usd=("linea_usd", "sum"))
print(geo.to_string(float_format=lambda v: f"{v:,.0f}") if len(geo) else "  (sin datos)")
print()
print("--- TOP PRODUCTOS ---")
top = (df.groupby("producto").agg(usd=("linea_usd", "sum"), docs=("doc", "nunique"))
       .sort_values("usd", ascending=False).head(12))
print(top.to_string(float_format=lambda v: f"{v:,.0f}"))
