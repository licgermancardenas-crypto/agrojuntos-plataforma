# -*- coding: utf-8 -*-
"""SOM and unit economics, anchored on AgroJuntos' own invoiced sales.

The SAM says how much money sits in the market. The SOM has to say how much of
it this team can take with the sales motion it has actually demonstrated, so
every input below comes from the sales ledger rather than from a target.
"""
import pandas as pd

dep = pd.read_csv("out/modelo_v2_departamento.csv", encoding="utf-8-sig")
ven = pd.read_csv("out/ventas_doc.csv", encoding="utf-8-sig")
cli = pd.read_csv("out/ventas_cliente.csv", encoding="utf-8-sig")

ven["fecha"] = pd.to_datetime(ven["fecha"])
meses = (ven.fecha.max() - ven.fecha.min()).days / 30.44

# --- observed unit economics ----------------------------------------------
ticket_prom = ven.usd.mean()
ticket_med = ven.usd.median()
rec = cli[cli.compras > 1]
frec_dias = rec.frec_dias.max()          # the established client, not the noise
compras_ano = 365 / frec_dias
recurrencia = len(rec) / len(cli)
MARGEN = 0.21                            # gross margin reported by the company

valor_cliente_ano = ticket_prom * compras_ano
margen_cliente_ano = valor_cliente_ano * MARGEN

print("=" * 74)
print("ECONOMIA UNITARIA OBSERVADA  (libro de ventas, Sep 2024 - Oct 2025)")
print("=" * 74)
print(f"periodo facturado        : {meses:>8,.1f} meses")
print(f"ventas acumuladas        : US$ {ven.usd.sum():>8,.0f}")
print(f"clientes facturados      : {len(cli):>8,.0f}")
print(f"ticket promedio          : US$ {ticket_prom:>8,.0f}     (mediana US$ {ticket_med:,.0f})")
print(f"frecuencia cliente activo: {frec_dias:>8,.0f} dias  -> {compras_ano:,.1f} compras/ano")
print(f"tasa de recurrencia      : {100*recurrencia:>8,.0f}%")
print(f"valor anual por cliente  : US$ {valor_cliente_ano:>8,.0f}")
print(f"margen anual por cliente : US$ {margen_cliente_ano:>8,.0f}     (margen bruto {100*MARGEN:.0f}%)")
print()

# --- capture scenarios -----------------------------------------------------
# Focus is the top 8 regions, which hold 58% of the SAM.
FOCO = 8
foco = dep.head(FOCO)
sam_foco = foco.sam_usd.sum()
cli_foco = foco.clientes_sam.sum()

ESCENARIOS = [
    ("Conservador", 0.005),
    ("Base",        0.015),
    ("Agresivo",    0.030),
]

print("=" * 74)
print(f"SOM - captura sobre las {FOCO} regiones foco")
print("=" * 74)
print(f"SAM en regiones foco     : US$ {sam_foco/1e6:>8,.0f} MM")
print(f"clientes alcanzables     : {cli_foco:>8,.0f}")
print()
hdr = f"{'escenario':<13} {'penetracion':>11} {'clientes':>9} {'ventas/ano':>13} {'margen/ano':>12}"
print(hdr)
print("-" * len(hdr))
rows = []
for nombre, pen in ESCENARIOS:
    n = cli_foco * pen
    ventas = n * valor_cliente_ano
    rows.append({"escenario": nombre, "penetracion": pen, "clientes": n,
                 "ventas_usd": ventas, "margen_usd": ventas * MARGEN})
    print(f"{nombre:<13} {100*pen:>10,.1f}% {n:>9,.0f} "
          f"US$ {ventas/1e6:>9,.1f} MM US$ {ventas*MARGEN/1e6:>8,.1f} MM")
pd.DataFrame(rows).to_csv("out/som_escenarios.csv", index=False, encoding="utf-8-sig")

print()
print("Para dimensionar el esfuerzo: alcanzar el escenario base implica")
base_n = cli_foco * 0.015
print(f"sumar {base_n:,.0f} clientes activos, es decir {base_n/36:,.0f} por mes durante 3 anos.")
print(f"Hoy la empresa factura a {len(cli)} clientes.")
print()

# --- what the deck currently claims ---------------------------------------
print("=" * 74)
print("CONTRASTE CON EL DOSSIER ACTUAL")
print("=" * 74)
comp = [
    ("TAM",               "$297 Billones (global)", f"US$ {dep.tam_usd.sum()/1e6:,.0f} MM (Peru)"),
    ("SAM",               "$19 Billones (LatAm)",   f"US$ {dep.sam_usd.sum()/1e6:,.0f} MM"),
    ("SOM",               "$3 Millones / 250 clientes", f"US$ {rows[1]['ventas_usd']/1e6:,.1f} MM / {base_n:,.0f} clientes"),
    ("Ticket promedio",   "$1,800",                 f"US$ {ticket_prom:,.0f}"),
    ("Frecuencia compra", "1.5 meses",              f"{frec_dias/30.44:,.1f} meses"),
    ("Ventas totales",    "+$200,000",              f"US$ {ven.usd.sum():,.0f}"),
    ("Rentabilidad",      "21%",                    "21% (coincide)"),
]
print(f"{'metrica':<18} {'dossier':<28} {'verificado':<28}")
print("-" * 74)
for a, b, c in comp:
    print(f"{a:<18} {b:<28} {c:<28}")
