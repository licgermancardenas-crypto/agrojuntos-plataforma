# -*- coding: utf-8 -*-
"""Agrega la exportación agrícola por empresa y por mercado, con cobertura.

El gemelo de `build_import_agregados.py` del otro lado de la aduana, y hereda
su disciplina: un mes sin operaciones puede significar que nadie embarcó o que
ese archivo todavía no se bajó, así que cada año y cada mes viajan con las
semanas de origen que los respaldan.

La exportación agrega una trampa que la importación no tiene, y es la que
manda sobre casi todo lo demás:

  **El rezago de regularización.** La serie se ancla en la fecha de embarque,
  pero el archivo semanal se arma cuando la declaración se regulariza, y entre
  una cosa y otra pasan 11 días en la mediana. El último mes de la serie está
  incompleto *aunque su semana esté descargada*: faltan los embarques que aún
  no regularizan.

  El percentil de días no sirve para decidir cuándo un mes está completo, y
  conviene decir por qué: se calcula sobre las líneas que ya se vieron, y las
  que faltan son justamente las lentas. Que el p99 dé 30 días no significa que
  un mes de 30 días de antigüedad esté completo; significa que el 99% de lo
  que ya llegó llegó en menos de 30. Es censura por la derecha, y leída al
  revés inventa caídas del último trimestre.

  Lo que sí decide es la curva de maduración: sobre meses de embarque ya
  cerrados —más de 120 días de antigüedad, cuando el mes ya no crece— qué
  fracción del FOB se había visto a los N días del embarque. Esa curva,
  aplicada día por día, dice cuánto de cada mes reciente debería estar a la
  vista hoy. Un mes entra en la variación interanual solo si su completitud
  esperada llega al 99.5% en los dos años, y el tramo comparado se declara.

Dos aclaraciones más que viajan dentro del archivo:

  El ubigeo del manifiesto **no es el domicilio fiscal**, y eso lo vuelve el
  campo más valioso del archivo. Cruzado contra el padrón de SUNAT sobre 2024
  —529 exportadores, 120,815 líneas— coincide en el distrito solo el 26.6% de
  las veces y en el departamento el 48.8%. Las diferencias no son ruido: donde
  el manifiesto dice Ica, La Libertad, Lambayeque o Piura, el padrón dice Lima.
  El manifiesto apunta al fundo y el padrón a la oficina.

  Pero se está apagando. El campo viene lleno en el 100% del FOB hasta 2024,
  en el 60% en 2025 y en el 2.3% en 2026. El corte por departamento se calcula
  entonces solo sobre los años que lo traen, y el año se declara: extender un
  mapa de producción con años en los que SUNAT dejó de llenar el campo lo
  convertiría en un mapa de la caída del campo.

  Una declaración trae varias líneas —una por partida y serie—, así que la
  declaración repetida no es una anomalía como en importación: es la forma del
  documento. Se cuentan las declaraciones únicas aparte de las líneas.

Uso:
    python scripts/build_export_agregados.py
"""
import datetime as dt
import io
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tandas import leer_en_tandas                      # noqa: E402
from universo import CAPITULO, CAP_ORIGEN, ampliada    # noqa: E402

PROC = "data/exportaciones/processed"
# El archivo depurado, no el crudo: el crudo trae la misma serie
# repetida y precios que el producto no aguanta. Ver
# `build_export_depurar.py`, que deja constancia de lo apartado.
ENTRADA = os.path.join(PROC, "operaciones_limpias.csv")
SALIDA = os.path.join(PROC, "exportadores.json")
MERCADO = os.path.join(PROC, "mercado.json")
ANOMALIAS = os.path.join(PROC, "anomalias.json")
ANIOS = 5
REZAGO_PANEL = 28    # el que trae hardcodeado build_export_panel.py
CIERRE = 120         # dias tras los cuales un mes de embarque ya no crece
UMBRAL = 99.5        # % de maduracion esperada para llamar completo a un mes
UBIGEO_MIN = 95.0    # % del FOB con ubigeo para que el ano sirva de mapa

# Las dieciseis columnas que el agregado necesita. El archivo tiene treinta y
# leerlas todas cuesta gigabytes que la maquina no tiene. Las que se repiten
# mucho van como categoria.
COLS = {
    "ruc": "category", "razon_social": "category", "fecha": "category",
    "anio": "category", "mes": "category", "semana_archivo": "category",
    "dias_regularizacion": "float32", "familia": "category",
    "partida": "category", "pais_destino": "category", "via": "category",
    "aduana": "category", "ubigeo": "str", "declaracion": "category",
    "fob_usd": "float64", "peso_neto_kg": "float64",
}

# Codigos INEI de departamento. El ubigeo del domicilio fiscal empieza por
# ellos y es el unico puente entre la aduana y el territorio del proyecto.
DEP = {
    "01": "AMAZONAS", "02": "ANCASH", "03": "APURIMAC", "04": "AREQUIPA",
    "05": "AYACUCHO", "06": "CAJAMARCA", "07": "CALLAO", "08": "CUSCO",
    "09": "HUANCAVELICA", "10": "HUANUCO", "11": "ICA", "12": "JUNIN",
    "13": "LA LIBERTAD", "14": "LAMBAYEQUE", "15": "LIMA", "16": "LORETO",
    "17": "MADRE DE DIOS", "18": "MOQUEGUA", "19": "PASCO", "20": "PIURA",
    "21": "PUNO", "22": "SAN MARTIN", "23": "TACNA", "24": "TUMBES",
    "25": "UCAYALI",
}

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)


def bloque(sub):
    return {
        "fob": round(float(sub.fob_usd.sum()), 2),
        "kg": round(float(sub.peso_neto_kg.sum()), 1),
        "ops": int(len(sub)),
        "duas": int(sub.declaracion.nunique()),
        "empresas": int(sub.ruc[sub.pub].nunique()),
        "semanas": int(sub.semana_archivo.nunique()),
    }


def bloque_emp(sub):
    """El mismo bloque sin el conteo de empresas, que dentro de la ficha de una
    empresa siempre vale uno y solo ocupa lugar."""
    b = bloque(sub)
    b.pop("empresas")
    return b


def top(sub, col, n=8):
    return [{"n": str(k), "fob": round(float(v), 2)} for k, v in
            sub.groupby(col, observed=True).fob_usd.sum().nlargest(n).items()]


def main():
    if not os.path.exists(ENTRADA):
        sys.exit("falta " + ENTRADA + ": corre build_export_depurar.py")
    d = leer_en_tandas(ENTRADA, COLS)
    d = d[d.fob_usd >= 0].copy()
    # fecha ordenada para que .max() siga dando el ultimo embarque; una
    # categoria sin orden no se puede comparar.
    d["fecha"] = d.fecha.cat.as_ordered()
    # «No Disponib» no es un RUC: es la reserva del exportador persona natural
    # bajo la Ley 29733. Se queda en los totales del mercado —el embarque
    # ocurrio— y sale de todo corte por empresa, con el monto declarado aparte.
    d["pub"] = d.ruc.str.fullmatch(r"\d{11}", na=False)
    # El departamento del domicilio fiscal; sin ubigeo valido no se imputa.
    u = d.ubigeo.fillna("")
    d["dep"] = u.where(u.str.fullmatch(r"\d{6}"), "").str[:2]

    an = {"generado": dt.datetime.now().isoformat(timespec="seconds")}
    ultimo = str(d.fecha.max())
    anio_actual = ultimo[:4]
    anios_pedidos = [str(int(anio_actual) - i) for i in range(ANIOS - 1, -1, -1)]

    # ------------------------------------------------ recorte de la ventana --
    # Identico al del panel, para que los dos archivos hablen del mismo
    # universo. Lo que cae fuera se cuenta, nunca se repara a mano.
    fuera = d[~d.anio.isin(anios_pedidos)].copy()
    fuera["anio"] = fuera.anio.astype(str)
    previo = str(int(anios_pedidos[0]) - 1)
    d = d[d.anio.isin(anios_pedidos)].copy()
    reservado = d[~d.pub]
    d_emp = d[d.pub]

    # ----------------------------------------------------------- el rezago --
    # Medido, no supuesto. Pero el percentil de dias no alcanza como criterio:
    # se calcula sobre las lineas que ya se vieron, y las que faltan son
    # justamente las lentas. Un p99 de 30 dias no significa que un mes de 30
    # dias de antiguedad este completo, significa que el 99% de lo que ya
    # llego llego en menos de 30 dias. Es censura por la derecha, y leida al
    # reves inventa caidas.
    #
    # El criterio bueno es la curva de maduracion: sobre meses de embarque ya
    # cerrados —los que tuvieron mas de CIERRE dias para regularizar— que
    # fraccion del FOB del mes se habia visto a los N dias del embarque. Esa
    # curva se aplica dia por dia a los meses recientes y da cuanto de cada
    # uno deberia estar a la vista hoy.
    dr = d.dias_regularizacion.dropna()
    p50, p90, p99 = (int(round(x)) for x in dr.quantile([.5, .9, .99]))
    hoy = dt.date.fromisoformat(ultimo)
    mad = d[d.dias_regularizacion.notna()]
    antig = (pd.Timestamp(hoy) - pd.to_datetime(mad.fecha.astype(str))).dt.days
    cerrado = mad[antig.to_numpy() >= CIERRE]
    fob_cerrado = float(cerrado.fob_usd.sum())
    # La curva se consulta un par de miles de veces —cada dia de cada mes—, asi
    # que se acumula una sola vez: FOB por dia de rezago y suma corrida. Filtrar
    # el millon y medio de lineas en cada consulta tardaba diez minutos.
    _dias = cerrado.dias_regularizacion.clip(0, CIERRE).round().astype(int)
    _acum = np.cumsum(np.bincount(_dias.to_numpy(),
                                  weights=cerrado.fob_usd.to_numpy(),
                                  minlength=CIERRE + 1))

    def visto_a(n):
        """Fraccion del FOB de un embarque que ya regularizo a los n dias."""
        if fob_cerrado <= 0:
            return 1.0
        return float(_acum[min(max(int(n), 0), CIERRE)]) / fob_cerrado

    curva = {n: round(100 * visto_a(n), 2)
             for n in (7, 14, 21, 28, 30, 45, 60, 90, CIERRE)}
    # Completitud esperada de cada mes: promedio dia a dia de la curva, con
    # los dias del mes pesando igual. Un mes futuro respecto del corte no
    # existe; uno que empieza despues del corte da cero.
    def completitud(clave):
        a, m = int(clave[:4]), int(clave[5:7])
        fin = (dt.date(a + m // 12, m % 12 + 1, 1) - dt.timedelta(days=1))
        dias = [dt.date(a, m, x + 1) for x in range(fin.day)]
        vis = [visto_a((hoy - x).days) for x in dias if x <= hoy]
        return round(100 * (sum(vis) / len(dias)), 2) if vis else 0.0

    comp_mes = {k: completitud(k) for k in sorted(
        set("%s-%s" % (a, m) for a, m in
            zip(d.anio.astype(str), d.mes.astype(str))))}
    # La frontera es el ultimo dia de embarque cuya maduracion esperada llega
    # al umbral, no el ultimo dia menos un percentil.
    n_umbral = next((n for n in range(1, CIERRE + 1)
                     if visto_a(n) >= UMBRAL / 100), CIERRE)
    frontera = (hoy - dt.timedelta(days=n_umbral)).isoformat()

    # ------------------------------------------------------------ cobertura --
    cob_anio = {str(a): int(v) for a, v in
                d.groupby("anio", observed=True).semana_archivo.nunique().items()}
    cob_mes = {"%s-%s" % (a, m): int(v) for (a, m), v in
               d.groupby(["anio", "mes"], observed=True)
                .semana_archivo.nunique().items()}
    anios = sorted(cob_anio)

    # -------------------------------------------------- el tramo comparable --
    # Un mes entra en la comparacion interanual solo si su completitud
    # esperada llega al umbral en los dos anios. Comparar un mes que todavia
    # esta entrando contra uno cerrado es inventar una caida.
    meses_ytd = [k[5:] for k in sorted(comp_mes)
                 if k[:4] == anio_actual and comp_mes[k] >= UMBRAL]
    yoy = None
    prev = str(int(anio_actual) - 1)
    if prev in cob_anio and meses_ytd:
        a1 = d[(d.anio == anio_actual) & (d.mes.isin(meses_ytd))].fob_usd.sum()
        a0 = d[(d.anio == prev) & (d.mes.isin(meses_ytd))].fob_usd.sum()
        if a0 > 0:
            yoy = {"tramo": "%s-%s" % (meses_ytd[0], meses_ytd[-1]),
                   "meses": meses_ytd,
                   "anios": [prev, anio_actual],
                   "hasta": frontera,
                   "motivo": "solo meses cuya maduracion esperada llega al "
                             "%.1f%%, medida sobre la curva de "
                             "regularizacion" % UMBRAL,
                   "fob_previo": round(float(a0), 2),
                   "fob_actual": round(float(a1), 2),
                   "variacion_pct": round(100 * (a1 - a0) / a0, 1)}

    # -------------------------------------------------------------- mercado --
    por_anio = {str(a): bloque(g) for a, g in d.groupby("anio", observed=True)}
    por_mes = {"%s-%s" % (a, m): bloque(g) for (a, m), g in
               d.groupby(["anio", "mes"], observed=True)}
    tot = d.fob_usd.sum()

    fam = (d.groupby("familia", observed=True)
             .agg(fob=("fob_usd", "sum"), kg=("peso_neto_kg", "sum"),
                  ops=("fob_usd", "size"), empresas=("ruc", "nunique"))
             .sort_values("fob", ascending=False))
    dest = (d.groupby("pais_destino", observed=True)
              .agg(fob=("fob_usd", "sum"), kg=("peso_neto_kg", "sum"),
                   empresas=("ruc", "nunique"))
              .sort_values("fob", ascending=False))
    # Cobertura del ubigeo ano por ano: el campo se apaga y hay que saber
    # cuando dejo de servir antes de dibujar un mapa con el.
    ubi_anio = {}
    for a, g in d.groupby("anio", observed=True):
        f = float(g.fob_usd.sum())
        ubi_anio[str(a)] = round(100 * float(g[g.dep != ""].fob_usd.sum()) / f, 2)             if f > 0 else 0.0
    anios_ubi = [a for a, v in sorted(ubi_anio.items()) if v >= UBIGEO_MIN]
    d_ubi = d[d.anio.isin(anios_ubi) & (d.dep != "")] if anios_ubi else d.iloc[:0]
    dep = (d_ubi.groupby("dep", observed=True)
             .agg(fob=("fob_usd", "sum"), ops=("fob_usd", "size"),
                  empresas=("ruc", "nunique"))
             .sort_values("fob", ascending=False))
    # La serie mensual de cada departamento y, aparte, su perfil de doce meses
    # —el promedio del calendario, en % de su propio ano—. El perfil es lo que
    # dice cuando compra insumo cada region: Ica no siembra cuando siembra La
    # Libertad, y un canal que reparte igual todo el ano les llega tarde a las
    # dos. Va en porcentaje del ano propio para que Ica no aplaste a Amazonas.
    dep_mes, dep_perfil = {}, {}
    for c, g in d_ubi.groupby("dep", observed=True):
        dep_mes[str(c)] = {"%s-%s" % (a, m): round(float(v), 2) for (a, m), v
                           in g.groupby(["anio", "mes"], observed=True)
                                .fob_usd.sum().items()}
        pm = g.groupby("mes", observed=True).fob_usd.sum()
        t = float(pm.sum())
        dep_perfil[str(c)] = [round(100 * float(pm.get("%02d" % k, 0.0)) / t, 2)
                              if t > 0 else 0.0 for k in range(1, 13)]
    # Que exporta cada departamento. Hasta ahora el corte territorial daba el
    # total y el calendario, y para saber QUE sale de cada region habia que
    # mirar la ventana de diez semanas, que es otra medicion y de otro
    # periodo. Cinco familias alcanzan: en el 80% de los departamentos las
    # cinco primeras son mas del 95% del FOB.
    dep_fam = {}
    for c, g in d_ubi.groupby("dep", observed=True):
        ff = (g.groupby("familia", observed=True)
                .agg(v=("fob_usd", "sum"), tn=("peso_neto_kg", "sum"))
                .sort_values("v", ascending=False).head(5))
        dep_fam[str(c)] = [{"n": str(i), "v": round(float(r.v), 2),
                            "tn": int(round(float(r.tn) / 1000))}
                           for i, r in ff.iterrows()]

    # Dos cifras que no son la misma: lo que esos anios exportaron y lo que de
    # eso quedo ubicado. Ni siquiera un ano al 100% lo trae entero.
    fob_anios = float(d[d.anio.isin(anios_ubi)].fob_usd.sum()) if anios_ubi else 0.0
    fob_ubi = float(d_ubi.fob_usd.sum())
    sin_dep = d[d.dep == ""]

    # --------------------------------------------- de donde sale el total --
    # El universo arancelario dejo de ser una eleccion tacita: `universo.py`
    # la escribe y la mide contra MIDAGRI. Aqui se guarda cuanto aporta cada
    # capitulo que entro con la ampliacion, para que la plataforma pueda
    # marcar las familias nuevas en vez de anunciar un salto sin explicacion.
    cap = d.partida.astype(str).str.zfill(10).str[:2]
    amp = d.partida.astype(str).map(ampliada)
    fob_amp = float(d.fob_usd[amp].sum())
    por_cap = (d[amp].assign(cap=cap[amp]).groupby("cap", observed=True)
               .agg(fob=("fob_usd", "sum"), ops=("fob_usd", "size"),
                    empresas=("ruc", "nunique"))
               .sort_values("fob", ascending=False))
    universo = {
        "regla": "capitulos del arancel menos una lista corta de partidas que "
                 "no son agro; escrita y justificada en scripts/universo.py",
        "capitulos_origen": sorted(CAP_ORIGEN),
        "capitulos": {c: CAPITULO[c] for c in sorted(CAPITULO)},
        "excluido": {"1504": "aceite de pescado", "2301": "harina de pescado",
                     "33xx": "perfumeria y cosmetica",
                     "52xx/53xx": "hilados y tejidos"},
        "fob_ampliacion": round(fob_amp, 2),
        "pct_ampliacion": round(100 * fob_amp / tot, 2) if tot else 0.0,
        "por_capitulo": [{"cap": c, "n": CAPITULO[c],
                          "fob": round(float(r.fob), 2), "ops": int(r.ops),
                          "empresas": int(r.empresas)}
                         for c, r in por_cap.iterrows()],
        # Las familias que entraron, por nombre. La pantalla lista familias y
        # no capítulos, así que sin esta lista no puede marcar cuáles son
        # nuevas, que es justo lo que evita que el salto del total parezca un
        # error del sitio.
        "familias_ampliacion": sorted(
            str(x) for x in d.familia[amp].unique()),
        # Lo que la ampliación vale como cartera, que no es lo mismo que lo
        # que vale como FOB: exportadores que no aparecían en ninguno de los
        # siete capítulos originales y ahora sí son prospecto.
        "exportadores_solo_ampliacion": int(
            d_emp.assign(_a=amp.loc[d_emp.index].values)
            .groupby("ruc", observed=True)._a.all().sum()),
        "fob_ampliacion_por_anio": {
            str(a): round(float(g.fob_usd[amp.loc[g.index]].sum()), 2)
            for a, g in d.groupby("anio", observed=True)},
    }

    mercado = {
        "generado": an["generado"],
        "universo": universo,
        "fuente": "SUNAT/Aduanas · microdatos de manifiestos (Ley 27806)",
        "ultimo_registro": ultimo,
        "anio_en_curso": anio_actual,
        "meses_del_anio_en_curso": meses_ytd,
        "anios_con_dato": anios,
        "anios_pedidos": anios_pedidos,
        "cobertura_semanas": cob_anio,
        "cobertura_mes": cob_mes,
        "rezago": {
            "motivo": "dias entre el embarque y la regularizacion de la "
                      "declaracion; el archivo semanal se arma con la segunda "
                      "fecha y la serie se ancla en la primera",
            "mediana": p50, "p90": p90, "p99": p99,
            "advertencia_percentil": "el percentil se mide sobre lo que ya "
                                     "llego, y lo que falta es lo lento; no "
                                     "sirve para declarar un mes completo",
            "curva_maduracion": {
                "motivo": "%% del FOB de un mes de embarque ya regularizado a "
                          "los N dias, medido sobre meses cerrados (mas de "
                          "%d dias de antiguedad)" % CIERRE,
                "base_fob": round(float(fob_cerrado), 2),
                "pct_por_dia": curva,
            },
            "completitud_mes": comp_mes,
            "umbral_completo_pct": UMBRAL,
            "frontera_completitud": frontera,
            "advertencia": "todo embarque posterior a la frontera esta "
                           "incompleto por rezago, no por falta de descarga",
        },
        "empresas_con_dato": int(d_emp.ruc.nunique()),
        "reservado": {
            "motivo": "exportadores persona natural; SUNAT no publica al "
                      "titular (Ley 29733 de protección de datos personales)",
            "fob": round(float(reservado.fob_usd.sum()), 2),
            "ops": int(len(reservado)),
            "por_anio": {str(a): round(float(v), 2) for a, v in
                         reservado.groupby("anio", observed=True)
                                  .fob_usd.sum().items()},
        },
        # Las dos cosas que quedan fuera de la ventana, que no son la misma.
        "fuera_de_rango": {
            "ventana_anterior": {
                "anio": previo,
                "motivo": "embarques de diciembre que regularizan en enero; "
                          "quedan fuera del recorte de cinco años",
                "fob": round(float(fuera[fuera.anio == previo].fob_usd.sum()), 2),
                "ops": int((fuera.anio == previo).sum()),
            },
            "fechas_no_creibles": {
                "motivo": "fecha de embarque anterior a la ventana; no se "
                          "corrigen ni se borran, se declaran",
                "fob": round(float(fuera[fuera.anio < previo].fob_usd.sum()), 2),
                "ops": int((fuera.anio < previo).sum()),
                "anios": sorted(fuera[fuera.anio < previo].anio.unique().tolist()),
            },
        },
        "operaciones": int(len(d)),
        "declaraciones": int(d.declaracion.nunique()),
        "total": bloque(d),
        "por_anio": por_anio,
        "por_mes": por_mes,
        "yoy": yoy,
        "familias": [{"n": str(c), "fob": round(float(r.fob), 2),
                      "kg": round(float(r.kg), 1), "ops": int(r.ops),
                      "empresas": int(r.empresas),
                      "pct": round(100 * r.fob / tot, 2)}
                     for c, r in fam.iterrows()],
        "destinos": [{"n": str(p), "fob": round(float(r.fob), 2),
                      "kg": round(float(r.kg), 1), "empresas": int(r.empresas),
                      "pct": round(100 * r.fob / tot, 2)}
                     for p, r in dest.head(30).iterrows()],
        "vias": top(d, "via", 10),
        # La aduana con su mezcla, y no solo su total. La vista de productos
        # explicaba por que existe cada aduana —Paita es cafe, Pisco es uva—
        # con la ventana de diez semanas, que es otra medicion; con esto la
        # explicacion sale del mismo periodo que la cifra que acompana.
        "aduanas": [{
            "n": str(c),
            "fob": round(float(g.fob_usd.sum()), 2),
            "kg": round(float(g.peso_neto_kg.sum()), 1),
            "empresas": int(g.ruc.nunique()),
            "mezcla": [{"n": str(i), "v": round(float(v), 2)} for i, v in
                       g.groupby("familia", observed=True).fob_usd.sum()
                        .nlargest(6).items()],
        } for c, g in sorted(d.groupby("aduana", observed=True),
                             key=lambda x: -x[1].fob_usd.sum())[:18]],
        "departamentos": {
            "motivo": "ubigeo declarado en el manifiesto, que apunta al lugar "
                      "de produccion y no al domicilio fiscal: contra el "
                      "padron de SUNAT sobre 2024 coincide el 26.6% a nivel "
                      "de distrito y el 48.8% a nivel de departamento, y "
                      "donde el manifiesto dice Ica o La Libertad el padron "
                      "dice Lima",
            "cobertura_fob_por_anio": ubi_anio,
            "umbral_cobertura_pct": UBIGEO_MIN,
            "anios_usados": anios_ubi,
            "advertencia": "SUNAT dejo de llenar el campo: el corte se limita "
                           "a los anios que lo traen y no debe extenderse a "
                           "los demas",
            "fob_de_los_anios_usados": round(fob_anios, 2),
            "fob_ubicado": round(fob_ubi, 2),
            "sin_ubigeo": {"fob": round(float(sin_dep.fob_usd.sum()), 2),
                           "ops": int(len(sin_dep)),
                           "pct": round(100 * len(sin_dep) / len(d), 1)},
            "lista": [{"c": str(c), "n": DEP.get(str(c), str(c)),
                       "fob": round(float(r.fob), 2), "ops": int(r.ops),
                       "empresas": int(r.empresas),
                       "pct": round(100 * float(r.fob) / fob_ubi, 2)
                       if fob_ubi > 0 else 0.0,
                       "perfil": dep_perfil.get(str(c), []),
                       "familias": dep_fam.get(str(c), []),
                       "meses": dep_mes.get(str(c), {})}
                      for c, r in dep.iterrows()],
        },
    }

    # ------------------------------------------------------------- empresas --
    emp = {}
    for ruc, g in d_emp.groupby("ruc", observed=True):
        # Algun RUC llega sin razon social en ninguna de sus lineas; en ese
        # caso el nombre es el propio RUC, que es un dato y no un invento.
        m = g.razon_social.dropna().mode()
        deps = g.dep[g.dep != ""].mode()
        # El mismo corte por producto, destino y partida repetido ano por ano,
        # que es lo que permite filtrar la ficha sin volver a pedir nada.
        cubo = {str(a): {"fam": top(x, "familia"),
                         "pais": top(x, "pais_destino"),
                         "part": top(x, "partida")}
                for a, x in g.groupby("anio", observed=True)}
        emp[str(ruc)] = {
            "ruc": str(ruc),
            "n": str(m.iat[0]) if len(m) else str(ruc),
            "dep": DEP.get(deps.iat[0], "") if len(deps) else "",
            "cubo": cubo,
            "total": bloque_emp(g),
            "por_anio": {str(a): bloque_emp(x)
                         for a, x in g.groupby("anio", observed=True)},
            "por_mes": {"%s-%s" % (a, mm): round(float(v), 2) for (a, mm), v in
                        g.groupby(["anio", "mes"], observed=True)
                         .fob_usd.sum().items()},
            "familias": top(g, "familia", 12),
            "partidas": top(g, "partida", 10),
            "paises": top(g, "pais_destino", 10),
            "n_paises": int(g.pais_destino.nunique()),
            "n_familias": int(g.familia.nunique()),
            "vias": top(g, "via", 5),
            "aduanas": top(g, "aduana", 5),
            "primera": str(g.fecha.min()), "ultima": str(g.fecha.max()),
            "rezago_mediana": (int(round(g.dias_regularizacion.median()))
                               if g.dias_regularizacion.notna().any() else None),
        }

    # ------------------------------------------- cuadraturas que deben dar --
    an["operaciones"] = int(len(d))
    an["declaraciones"] = int(d.declaracion.nunique())
    an["lineas_por_declaracion"] = round(len(d) / max(an["declaraciones"], 1), 2)
    an["operaciones_sin_titular_publicable"] = int(len(reservado))
    an["mes_fuera_de_rango"] = int((~d.mes.isin(
        ["%02d" % m for m in range(1, 13)])).sum())
    an["fob_cero"] = int((d.fob_usd == 0).sum())
    an["sin_razon_social"] = int(d_emp.razon_social.isna().sum())
    an["sin_ubigeo"] = int((d.dep == "").sum())
    an["ubigeo_fuera_de_tabla"] = sorted(
        set(d.dep[d.dep != ""].unique()) - set(DEP))
    an["fecha_min"], an["fecha_max"] = str(d.fecha.min()), str(d.fecha.max())
    an["rezago"] = {"mediana": p50, "p90": p90, "p99": p99,
                    "dias_para_umbral": n_umbral, "umbral_pct": UMBRAL,
                    "frontera": frontera, "rezago_del_panel": REZAGO_PANEL,
                    "coincide_con_el_panel": bool(n_umbral == REZAGO_PANEL)}
    an["meses_parciales"] = {k: v for k, v in comp_mes.items() if v < UMBRAL}
    tot_emp = d_emp.fob_usd.sum()
    an["cuadra_suma_anios"] = bool(abs(
        sum(v["fob"] for v in por_anio.values()) - tot) < 1)
    an["cuadra_suma_meses"] = bool(abs(
        sum(v["fob"] for v in por_mes.values()) - tot) < 1)
    an["cuadra_suma_familias"] = bool(abs(fam.fob.sum() - tot) < 1)
    an["cuadra_suma_destinos"] = bool(abs(dest.fob.sum() - tot) < 1)
    # Los cortes por empresa cuadran contra el total menos lo reservado, que es
    # exactamente lo que no tiene empresa a la cual atribuirse.
    an["cuadra_suma_empresas"] = bool(abs(
        sum(e["total"]["fob"] for e in emp.values()) - tot_emp) < 1)
    an["cuadra_meses_empresa"] = bool(abs(
        sum(sum(e["por_mes"].values()) for e in emp.values()) - tot_emp) < 1)
    # El corte departamental cuadra contra el FOB de los anios que traen
    # ubigeo, no contra el total: los otros anios no tienen donde ubicarse.
    an["cobertura_ubigeo_por_anio"] = ubi_anio
    an["anios_con_ubigeo_util"] = anios_ubi
    an["cuadra_departamentos"] = bool(abs(dep.fob.sum() - fob_ubi) < 1)
    an["cuadra_perfil_dep"] = all(abs(sum(v) - 100) < 0.5
                                  for v in dep_perfil.values() if sum(v) > 0)
    an["cuadra_meses_dep"] = bool(abs(
        sum(sum(v.values()) for v in dep_mes.values()) - fob_ubi) < 1)

    for p, o in ((SALIDA, emp), (MERCADO, mercado), (ANOMALIAS, an)):
        with io.open(p, "w", encoding="utf-8") as fh:
            json.dump(o, fh, ensure_ascii=False, separators=(",", ":"))

    print("exportadores      : %s" % format(len(emp), ","))
    print("operaciones       : %s lineas en %s declaraciones"
          % (format(len(d), ","), format(an["declaraciones"], ",")))
    print("FOB total         : US$ %.1f MM" % (tot / 1e6))
    print("familias          : %d | destinos: %d"
          % (len(fam), len(dest)))
    print("universo ampliado : US$ %.1f MM (%.1f%% del total) en %d capitulos"
          % (fob_amp / 1e6, universo["pct_ampliacion"], len(por_cap)))
    print("ultimo embarque   : %s" % ultimo)
    print("rezago            : p50 %d d, p90 %d d, p99 %d d" % (p50, p90, p99))
    print("maduracion        : %s"
          % " ".join("%dd=%.1f%%" % (n, v) for n, v in curva.items()))
    print("frontera completa : %s (%d d para el %.1f%%)%s" % (
        frontera, n_umbral, UMBRAL, "" if n_umbral == REZAGO_PANEL
        else "  -- el panel usa %d d; conviene alinearlos" % REZAGO_PANEL))
    print("meses parciales   : %s"
          % (", ".join("%s %.1f%%" % (k, v)
                       for k, v in sorted(an["meses_parciales"].items()))
             or "ninguno"))
    print("anios con dato    : %s" % anios)
    print("anios sin dato    : %s"
          % [a for a in anios_pedidos if a not in anios])
    print("semanas por anio  : %s" % cob_anio)
    for p in (SALIDA, MERCADO):
        print("archivo           : %-18s %.2f MB"
              % (os.path.basename(p), os.path.getsize(p) / 1e6))
    print("\ncuadraturas:")
    for k in ("cuadra_suma_anios", "cuadra_suma_meses", "cuadra_suma_familias",
              "cuadra_suma_destinos", "cuadra_suma_empresas",
              "cuadra_meses_empresa", "cuadra_departamentos",
              "cuadra_perfil_dep", "cuadra_meses_dep"):
        print("  %-34s %s" % (k, "OK" if an[k] else "NO CUADRA"))
    print("  ubigeo, %% del FOB por anio         %s"
          % " ".join("%s=%.1f%%" % kv for kv in sorted(ubi_anio.items())))
    print("  anios que sirven de mapa           %s"
          % (", ".join(anios_ubi) or "ninguno"))
    print("  sin ubigeo                         %s lineas (%.1f%% del total)"
          % (format(an["sin_ubigeo"], ","), 100 * an["sin_ubigeo"] / len(d)))
    print("  sin razon social                   %s lineas"
          % format(an["sin_razon_social"], ","))
    print("  lineas por declaracion             %.2f"
          % an["lineas_por_declaracion"])
    print("  FOB cero                           %s"
          % format(an["fob_cero"], ","))
    print("  ubigeo fuera de tabla              %s"
          % (an["ubigeo_fuera_de_tabla"] or "ninguno"))
    print("  reservado Ley 29733                US$ %.1f MM en %s operaciones"
          % (reservado.fob_usd.sum() / 1e6, format(len(reservado), ",")))
    if yoy:
        print("\nvariacion %s %s->%s: %+.1f%%  (hasta %s, solo meses cerrados)"
              % (yoy["tramo"], yoy["anios"][0], yoy["anios"][1],
                 yoy["variacion_pct"], yoy["hasta"]))


if __name__ == "__main__":
    main()
