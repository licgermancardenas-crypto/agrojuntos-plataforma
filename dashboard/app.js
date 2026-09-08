/* Dashboard AgroJuntos.
   Cada vista carga su propio JSON la primera vez que se abre: el directorio de
   empresas pesa más que todo el resto junto y no debe frenar la portada. */
(function () {
"use strict";

var cache = {};
function cargar(nombre) {
  if (cache[nombre]) return cache[nombre];
  cache[nombre] = fetch("/data/" + nombre + ".json").then(function (r) {
    if (!r.ok) throw new Error(nombre + ": HTTP " + r.status);
    return r.json();
  });
  return cache[nombre];
}

/* ------------------------------------------------------------- formato -- */
function nf(v, d) {
  return (+v).toLocaleString("es-PE",
    { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 });
}
function usd(v) {
  if (v >= 1e9) return "US$ " + nf(v / 1e9, 2) + " mil MM";
  if (v >= 1e6) return "US$ " + nf(v / 1e6, 1) + " MM";
  if (v >= 1e3) return "US$ " + nf(v / 1e3) + " mil";
  return "US$ " + nf(v);
}
function pct(v, d) { return nf(v, d === undefined ? 1 : d) + "%"; }
function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}
function css(n) {
  return getComputedStyle(document.documentElement).getPropertyValue(n).trim();
}

/* --------------------------------------------------------------- tabla -- */
/* Ordena por la columna que se pulse y recuerda el sentido. Las columnas se
   declaran con su extractor, de modo que ordenar usa el valor crudo y no el
   texto ya formateado —ordenar "US$ 1.2 MM" como cadena da resultados
   absurdos—. */
function tabla(el, cols, filas, opts) {
  opts = opts || {};
  var estado = { k: opts.sort || cols[0].k, asc: !!opts.asc };

  function pintar() {
    var d = filas.slice().sort(function (a, b) {
      var col = cols.filter(function (c) { return c.k === estado.k; })[0];
      var va = col.v ? col.v(a) : a[col.k], vb = col.v ? col.v(b) : b[col.k];
      var r = typeof va === "string" ? va.localeCompare(vb, "es") : (va - vb);
      return estado.asc ? r : -r;
    });
    if (opts.limite) d = d.slice(0, opts.limite);

    el.innerHTML =
      "<thead><tr>" + cols.map(function (c) {
        var a = c.k === estado.k
          ? ' aria-sort="' + (estado.asc ? "asc" : "desc") + '"' : "";
        return "<th" + (c.l ? ' class="l"' : "") + a + ' data-k="' + c.k + '">' +
               c.t + "</th>";
      }).join("") + "</tr></thead><tbody>" +
      d.map(function (row) {
        return "<tr>" + cols.map(function (c) {
          var cls = (c.l ? "l" : "n") + (c.cls ? " " + c.cls : "");
          return '<td class="' + cls + '">' + c.f(row) + "</td>";
        }).join("") + "</tr>";
      }).join("") + "</tbody>";

    el.querySelectorAll("th").forEach(function (th) {
      th.onclick = function () {
        var k = th.dataset.k;
        if (k === estado.k) estado.asc = !estado.asc;
        else { estado.k = k; estado.asc = !!cols.filter(function (c) {
          return c.k === k; })[0].l; }
        pintar();
      };
    });
  }
  pintar();
}

/* -------------------------------------------------------------- resumen -- */
function vistaResumen() {
  cargar("resumen").then(function (D) {
    var k = D.kpi;
    document.getElementById("upd").textContent =
      nf(k.clientes) + " clientes · " + nf(k.territorios) + " territorios";

    document.getElementById("kpis").innerHTML = [
      { v: usd(k.tam), l: "TAM", s: "mercado nacional de insumos" },
      { v: usd(k.sam), l: "SAM", s: Math.round(100 * k.sam / k.tam) + "% del TAM" },
      { v: nf(k.clientes), l: "Clientes", s: "ya compran insumos" },
      { v: "US$ " + nf(k.ticket), l: "Gasto anual", s: "por cliente" },
      { v: nf(k.ha_cosechada / 1e6, 2) + " M", l: "Hectáreas", s: "cosechadas en 2023" },
      { v: nf(k.territorios), l: "Territorios", s: k.territorios_dia + " de un día" }
    ].map(function (x) {
      return '<div><span class="v">' + x.v + '</span><span class="l">' + x.l +
             '</span><span class="s">' + x.s + "</span></div>";
    }).join("");

    /* embudo */
    var base = D.embudo[0].v;
    document.getElementById("funnel").innerHTML = D.embudo.map(function (s) {
      var w = 100 * s.v / base;
      return '<div class="fstep"><span class="n">' + s.n + '</span>' +
        '<span class="v">' + nf(s.v) + '</span>' +
        '<span class="ftrack"><i style="width:' + w.toFixed(2) + '%"></i></span>' +
        '<span class="fpct">' + pct(w) + " del total</span></div>";
    }).join("");

    dibujarCurva(D.curva);
    var pico = D.curva.reduce(function (a, b) { return b.pct > a.pct ? b : a; });
    var top4 = D.curva.slice().sort(function (a, b) { return b.pct - a.pct; })
                 .slice(0, 4);
    document.getElementById("curvaNota").textContent =
      "El pico es " + pico.m + " con " + pct(pico.pct) + " de la demanda anual. " +
      "Cuatro meses concentran " +
      pct(top4.reduce(function (s, x) { return s + x.pct; }, 0), 0) + ".";

    tabla(document.getElementById("tRegiones"), [
      { k: "rank", t: "#", f: function (r) { return r.rank; } },
      { k: "n", t: "Región", l: true, f: function (r) { return esc(r.n); } },
      { k: "sam", t: "SAM anual", f: function (r) { return usd(r.sam); } },
      { k: "cli", t: "Clientes", f: function (r) { return nf(r.cli); } },
      { k: "gasto", t: "US$/ha", f: function (r) { return nf(r.gasto); } },
      { k: "ticket", t: "US$/cliente", f: function (r) { return nf(r.ticket); } },
      { k: "acc", t: "% a <2 h", f: function (r) { return pct(r.acc, 0); } },
      { k: "credito", t: "% crédito", f: function (r) { return pct(r.credito, 0); } },
      { k: "pico", t: "Mes pico", f: function (r) { return r.pico; } },
      { k: "top4", t: "% en 4 meses", f: function (r) { return pct(r.top4, 0); } },
      { k: "arq", t: "Arquetipo", l: true, f: function (r) { return esc(r.arq); } },
      { k: "score", t: "Score", f: function (r) {
          return nf(r.score, 0) + '<span class="mini"><i style="width:' +
                 r.score.toFixed(0) + '%"></i></span>'; } }
    ], D.regiones, { sort: "rank", asc: true });

    /* expansión usa los mismos datos */
    vistaExpansion(D);
  }).catch(fallo);
}

function dibujarCurva(curva) {
  var cv = document.getElementById("curva");
  var w = cv.parentNode.clientWidth - 30, h = 150;
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = w * dpr; cv.height = h * dpr;
  cv.style.width = w + "px"; cv.style.height = h + "px";
  var c = cv.getContext("2d");
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, w, h);

  var mx = Math.max.apply(null, curva.map(function (x) { return x.v; }));
  var pad = 22, bw = (w - pad) / curva.length;
  var orden = curva.slice().sort(function (a, b) { return b.v - a.v; })
                .slice(0, 4).map(function (x) { return x.m; });

  curva.forEach(function (x, i) {
    var bh = (h - pad - 6) * x.v / mx;
    c.fillStyle = orden.indexOf(x.m) >= 0 ? css("--forest") : css("--line");
    c.fillRect(pad / 2 + i * bw + 2, h - pad - bh, bw - 4, bh);
    c.fillStyle = css("--muted");
    c.font = "9px 'IBM Plex Sans',sans-serif";
    c.textAlign = "center";
    c.fillText(x.m, pad / 2 + i * bw + bw / 2, h - 7);
  });
}

/* Cada unidad del mapa tiene su propia direccion: el mapa de un departamento,
   de un territorio o de una provincia se comparte como cualquier pagina. El
   slug se calcula igual que en el mapa, que es quien lo lee. */
function slugU(s) {
  return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "");
}
function enlaceMapa(txt, hash) {
  return '<a class="vermapa" href="/mapa#' + hash + '">' + txt + "</a>";
}

/* --------------------------------------------------------------- periodo -- */
/* Los manifiestos de aduanas son una ventana móvil de diez semanas. Todo el
   comercio exterior del sitio viaja MEDIDO sobre esa ventana y aquí se lleva
   al periodo que el lector elija, en un solo lugar: si cada vista anualizara
   por su cuenta, la misma empresa mostraría dos cifras distintas según por
   dónde se llegara a ella.

   «Medido» es el único dato duro. Mensual y anual son extrapolaciones de diez
   semanas sin corregir estacionalidad, y por eso el rótulo lo dice en cada
   columna en vez de esconderlo en una nota al pie. */
var PERIODO = "anual";
try { PERIODO = localStorage.getItem("periodo") || "anual"; } catch (e) {}

function pFactor(sem) {
  sem = sem || 10;
  if (PERIODO === "medido") return 1;
  if (PERIODO === "mensual") return (52 / sem) / 12;
  return 52 / sem;
}
function pSuf(sem) {
  if (PERIODO === "medido") return (sem || 10) + " sem";
  return PERIODO === "mensual" ? "al mes" : "anual";
}
function pFob(v, sem) { return usd((v || 0) * pFactor(sem)); }
function pNum(v, sem, d) { return nf((v || 0) * pFactor(sem), d); }

/* Cambiar de periodo repinta la vista abierta. No se recargan los datos: son
   los mismos, medidos, y lo único que cambia es por cuánto se multiplican. */
var REPINTAR = {};
function aplicarPeriodo(p) {
  PERIODO = p;
  try { localStorage.setItem("periodo", p); } catch (e) {}
  document.querySelectorAll("#fPeriodo button").forEach(function (b) {
    b.setAttribute("aria-pressed", String(b.dataset.p === p)); });
  var id = (location.hash || "#resumen").replace("#", "");
  var mE = /^empresa=(\d+)$/.exec(id);
  if (mE) { vistaEmpresa(mE[1]); return; }
  if (REPINTAR[id]) REPINTAR[id]();
}

(function initPeriodo() {
  document.querySelectorAll("#fPeriodo button").forEach(function (b) {
    b.setAttribute("aria-pressed", String(b.dataset.p === PERIODO));
    b.onclick = function () { aplicarPeriodo(b.dataset.p); };
  });
})();

/* --------------------------------------------------------- mapa incrustado */
/* El atlas completo dentro de cada modulo. Es la misma pagina de /mapa en un
   iframe, no una version recortada: asi hay un solo motor de mapa y lo que se
   arregla ahi vale en los once lugares donde aparece.

   Se monta al pulsar y no al abrir la vista. Entre pagina, capas de sectores y
   relieve son unos 4 MB, y quien entra a leer una tabla no tiene por que
   pagarlos; despues quedan en cache y los demas modulos los reusan.

   Una vez montado se reenfoca cambiando su hash, que es una navegacion dentro
   del mismo documento: el mapa la atiende con su propio hashchange y no se
   recarga. Por eso «#peru» existe como enlace explicito — vaciar el hash no
   dispara el evento. */
var MAPAS = {};
function mapaEn(cid, hash) {
  var cont = document.getElementById(cid);
  if (!cont) return;
  hash = hash || "#peru";
  cont.dataset.hash = hash;
  var f = MAPAS[cid];
  if (!f) {
    var btn = cont.querySelector(".mapabtn");
    if (btn && !btn.dataset.listo) {
      btn.dataset.listo = "1";
      btn.onclick = function () { montarMapa(cid); };
    }
    return;
  }
  try {
    var w = f.contentWindow;
    if (w && w.location.hash !== hash) w.location.hash = hash;
  } catch (e) {
    f.src = "/mapa?e=1" + hash;
  }
}

function montarMapa(cid) {
  var cont = document.getElementById(cid);
  if (!cont || MAPAS[cid]) return;
  var f = document.createElement("iframe");
  f.title = "Atlas geoespacial";
  f.src = "/mapa?e=1" + (cont.dataset.hash || "#peru");
  cont.innerHTML = "";
  cont.appendChild(f);
  MAPAS[cid] = f;
}

/* --------------------------------------------------------- territorios -- */
function vistaTerritorios() {
  cargar("territorios").then(function (T) {
    document.getElementById("terMeta").textContent =
      T.length + " núcleos · " +
      T.filter(function (x) { return x.dia; }).length + " de un día";
    tabla(document.getElementById("tTerritorios"), [
      { k: "rank", t: "#", f: function (r) { return r.rank; } },
      { k: "prov", t: "Provincias", l: true, f: function (r) { return esc(r.prov); } },
      { k: "dep", t: "Región", l: true, f: function (r) { return esc(r.dep); } },
      { k: "sam", t: "Mercado anual", f: function (r) { return usd(r.sam); } },
      { k: "cli", t: "Clientes", f: function (r) { return nf(r.cli); } },
      { k: "ha", t: "Hectáreas", f: function (r) { return nf(r.ha); } },
      { k: "emp", t: "Empresas", f: function (r) { return nf(r.emp); } },
      { k: "exp", t: "Agroexport.", f: function (r) { return nf(r.exp); } },
      { k: "hub", t: "Centro", l: true, f: function (r) {
          return r.hub ? esc(r.hub) : "—"; } },
      /* Dos columnas y no una. La promesa vigente es de cuatro horas, pero
         las cifras anteriores de este proyecto se publicaron con vara de dos
         y sin las dos al lado el cambio no se puede leer. */
      { k: "dpr", t: "Cartera en promesa", f: function (r) {
          return r.emp ? nf(r.dpr) + " · " +
                 Math.round(100 * r.dpr / r.emp) + "%" : "—"; } },
      { k: "d2h", t: "Cartera a <2 h", cls: "faint", f: function (r) {
          return r.emp ? nf(r.d2h) + " · " +
                 Math.round(100 * r.d2h / r.emp) + "%" : "—"; } },
      { k: "horas", t: "Horas capital", f: function (r) { return nf(r.horas, 1); } },
      { k: "ext", t: "Extensión km", f: function (r) { return nf(r.ext); } },
      { k: "dia", t: "Ruta", l: true, f: function (r) {
          return r.dia ? '<span class="tag P">un día</span>'
                       : '<span class="tag">pernocte</span>'; } },
      { k: "mapa", t: "Mapa", l: true, f: function (r) {
          return enlaceMapa("ver", "ter=" + r.rank); } }
    ], T, { sort: "rank", asc: true });

    /* Pulsar una fila enfoca su territorio en el mapa de abajo. El enlace
       «ver» de la ultima columna sigue abriendo el atlas completo aparte. */
    var tT = document.getElementById("tTerritorios");
    tT.onclick = function (ev) {
      if (ev.target.closest("a")) return;
      var tr = ev.target.closest("tbody tr");
      if (!tr) return;
      var n = tr.querySelector("td:first-child");
      if (n) mapaEn("mapTer", "#ter=" + n.textContent.trim());
    };
  }).catch(fallo);
}

/* ------------------------------------------------------------- empresas -- */
var EMP = null;
function vistaEmpresas() {
  if (EMP) return;
  var tbl = document.getElementById("tEmpresas");
  tbl.innerHTML = '<tbody><tr><td class="load">Cargando 22 mil empresas…</td></tr></tbody>';

  cargar("empresas").then(function (D) {
    /* El índice de búsqueda se arma aquí y no en el servidor: duplicar el
       nombre normalizado en el JSON agregaba medio megabyte a la descarga
       para ahorrar un recorrido que el navegador hace en milisegundos. */
    var filas = D.filas.map(function (f) {
      var dep = f[3] >= 0 ? D.deps[f[3]] : "";
      var prov = f[4] >= 0 ? D.provs[f[4]] : "";
      return {
        ruc: f[0], n: f[1], c: f[2], dep: dep, prov: prov,
        dist: f[5] >= 0 ? D.dists[f[5]] : "",
        x: f[6] * 1000, i: f[7] * 1000,
        z: f[8] >= 0 ? D.ters[f[8]] : "",
        h: f[9] >= 0 ? D.hubs[f[9]] : "",
        s: (f[1] + " " + f[0] + " " + dep + " " + prov)
             .normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      };
    });
    EMP = { d: D, filas: filas, clase: -1, reg: "", ter: "", q: "",
            sem: D.semanas || 10 };
    /* Importador de insumos es la clase 6, pero una empresa del padron agro
       que importa queda clasificada por su clase del padron: se cuenta a
       cualquiera con FOB de importacion registrado. */
    EMP_IMPORTADORES = filas.filter(function (f) {
      return f.c === 6 || f.i > 0; }).length;

    var sel = document.getElementById("fReg");
    sel.innerHTML = '<option value="">Todas las regiones</option>' +
      D.deps.map(function (r) {
        return '<option value="' + esc(r) + '">' + esc(r) + "</option>"; }).join("");

    /* "Fuera de territorio" va al final y no en orden alfabético: es la
       respuesta que más empresas tiene y encabezando la lista tapa a los
       territorios, que es lo que se viene a buscar aquí. */
    var FUERA = "Fuera de territorio";
    var selT = document.getElementById("fTer");
    selT.innerHTML = '<option value="">Todos los territorios</option>' +
      D.ters.filter(function (t) { return t !== FUERA; })
        .map(function (t) {
          return '<option value="' + esc(t) + '">' + esc(t) + "</option>"; }).join("") +
      (D.ters.indexOf(FUERA) >= 0
        ? '<option value="' + esc(FUERA) + '">' + esc(FUERA) + "</option>" : "");
    selT.onchange = function (e) {
      EMP.ter = e.target.value;
      pintarEmpresas();
      /* El rango viaja en el propio catalogo: deducirlo cruzando el texto
         del territorio seria la misma trampa que ya rompio la ubicacion de
         las empresas. */
      var i = D.ters.indexOf(EMP.ter);
      var rk = i >= 0 && D.ters_rank ? D.ters_rank[i] : -1;
      mapaEn("mapEmp", rk > 0 ? "#ter=" + rk : "#peru");
    };

    var CL = ["P", "A", "C", "V", "O", "E", "I"];
    document.getElementById("fClase").innerHTML =
      '<button class="chip" data-c="-1" aria-pressed="true">Todas</button>' +
      D.clases.map(function (n, i) {
        return '<button class="chip" data-c="' + i + '" aria-pressed="false">' +
               esc(n) + "</button>";
      }).join("");

    document.querySelectorAll("#fClase .chip").forEach(function (b) {
      b.onclick = function () {
        EMP.clase = +b.dataset.c;
        document.querySelectorAll("#fClase .chip").forEach(function (o) {
          o.setAttribute("aria-pressed", String(o === b)); });
        pintarEmpresas();
        panelImportadores(EMP.clase === 6);
      };
    });
    var t = null;
    document.getElementById("q").oninput = function (e) {
      clearTimeout(t);
      var v = e.target.value;
      t = setTimeout(function () {
        EMP.q = v.normalize("NFD").replace(/[̀-ͯ]/g, "")
                 .toLowerCase().trim();
        pintarEmpresas();
      }, 140);
    };
    sel.onchange = function (e) { EMP.reg = e.target.value; pintarEmpresas(); };

    pintarEmpresas();
  }).catch(fallo);
}

function pintarEmpresas() {
  var CL = ["P", "A", "C", "V", "O", "E", "I"];
  var f = EMP.filas.filter(function (r) {
    if (EMP.clase >= 0 && r.c !== EMP.clase) return false;
    if (EMP.reg && r.dep !== EMP.reg) return false;
    if (EMP.ter && r.z !== EMP.ter) return false;
    if (EMP.q && r.s.indexOf(EMP.q) < 0) return false;
    return true;
  });
  document.getElementById("cCount").textContent =
    nf(f.length) + " de " + nf(EMP.filas.length) +
    (f.length > 400 ? " · se muestran 400" : "");

  tabla(document.getElementById("tEmpresas"), [
    { k: "n", t: "Razón social", l: true, cls: "name",
      f: function (r) {
        return '<a class="vermapa" href="#empresa=' + r.ruc + '">' +
               esc(r.n) + "</a>"; } },
    { k: "ruc", t: "RUC", l: true, f: function (r) {
        return '<span class="mono">' + r.ruc + "</span>"; } },
    { k: "c", t: "Clase", l: true, f: function (r) {
        return '<span class="tag ' + CL[r.c] + '">' +
               esc(EMP.d.clases[r.c]) + "</span>"; } },
    { k: "dep", t: "Región", l: true, f: function (r) { return esc(r.dep); } },
    { k: "prov", t: "Provincia", l: true, f: function (r) { return esc(r.prov); } },
    { k: "z", t: "Territorio de venta", l: true, f: function (r) {
        return r.z && r.z !== "Fuera de territorio" ? esc(r.z) : "—"; } },
    { k: "h", t: "Centro", l: true, f: function (r) {
        return r.h ? esc(r.h) : "—"; } },
    { k: "x", t: "Exporta · " + pSuf(EMP.sem), f: function (r) {
        return r.x ? pFob(r.x, EMP.sem) : "—"; } },
    { k: "i", t: "Importa · " + pSuf(EMP.sem), f: function (r) {
        return r.i ? pFob(r.i, EMP.sem) : "—"; } }
  ], f, { sort: "x", limite: 400 });
}
REPINTAR.empresas = function () { if (EMP) pintarEmpresas(); };

/* El panel de la subcategoria se arma una sola vez y despues solo se muestra
   u oculta: su cubo pesa 0.45 MB y no hay razon para repedirlo. El estado del
   recorrido —ano, categoria, partida— sobrevive a ocultarlo, de modo que
   volver al chip devuelve al usuario donde estaba. */
var IMP_PANEL = false;
function panelImportadores(mostrar) {
  var caja = document.getElementById("impPanel");
  if (!caja) return;
  caja.hidden = !mostrar;
  if (!mostrar || IMP_PANEL) return;
  IMP_PANEL = true;
  Promise.all([cargar("importaciones/panel"),
               cargar("importaciones/precios")])
    .then(function (r) { IMPPR = r[1]; iniPanelImp(r[0]); })
    .catch(function () { IMP_PANEL = false; });
}

/* ------------------------------------------------------------ importacion */
function vistaImportacion() {
  cargar("importacion").then(function (D) {
    REPINTAR.importacion = function () { pintarImportacion(D); };
    pintarImportacion(D);
  }).catch(fallo);
}

function pintarImportacion(D) {
    var m = D.meta, SEM = m.semanas;
    var conM = D.cats.filter(function (c) { return c.lineas > 0; });
    var mayor = conM.slice().sort(function (a, b) { return b.fob - a.fob; })[0];

    document.getElementById("impKpis").innerHTML = [
      [pFob(m.fob, SEM), "importación agrícola " + pSuf(SEM),
       conM.length + " categorías con mercancía"],
      [nf(m.empresas), "empresas importadoras",
       "con RUC, en " + m.semanas + " semanas"],
      [mayor.n.split(" y ")[0], "la categoría mayor",
       pct(100 * mayor.fob / m.fob, 0) + " del total"],
      [pFob(m.fob_insumos, SEM), "fertilizante y fitosanitario",
       "lo que la plataforma ya medía"],
    ].map(function (k) {
      return "<div><span class='v'>" + esc(k[0]) + "</span><span class='l'>" +
        k[1] + "</span><span class='s'>" + esc(k[2]) + "</span></div>";
    }).join("");

    /* La fila en cero no se oculta: que servicios y tierra no aparezcan en un
       registro aduanero es parte de la respuesta, y borrarlas de la tabla
       dejaria al lector creyendo que nadie las miro. */
    tabla(document.getElementById("tImpCat"), [
      { k: "n", t: "Categoría", l: 1, f: function (r) {
          return r.lineas
            ? "<b>" + esc(r.n) + "</b><span class='sub2'>" + r.part +
              " partidas · pulsa para ver el detalle</span>"
            : "<b>" + esc(r.n) + "</b><span class='sub2'>no es mercancía: " +
              "no cruza una aduana</span>"; } },
      { k: "fob", t: "FOB " + pSuf(SEM), f: function (r) {
          return r.lineas ? pFob(r.fob, SEM) : "—"; } },
      { k: "fob10", t: "FOB medido · " + SEM + " sem", f: function (r) {
          return r.lineas ? usd(r.fob) : "—"; } },
      { k: "tn", t: "Toneladas " + pSuf(SEM), f: function (r) {
          return r.lineas ? pNum(r.tn, SEM) : "—"; } },
      { k: "emp", t: "Empresas", f: function (r) {
          return r.lineas ? nf(r.emp) : "—"; } },
      { k: "peso", t: "% del total", f: function (r) {
          return r.lineas ? pct(100 * r.fob / m.fob, 1) : "—"; } },
    ], D.cats, { sort: "fob" });

    function detalle(c) {
      if (!c || !c.lineas) {
        document.getElementById("impDet").innerHTML =
          "<p class='sub'>" + esc(c ? c.n : "") + " no deja rastro en aduanas: " +
          "para dimensionarla hay que ir al padrón de SUNAT por CIIU, en el " +
          "caso de los servicios, o a registros públicos en el de la tierra.</p>";
        return;
      }
      document.getElementById("impDet").innerHTML =
        "<div class='grid2'>" +
        "<div class='sub-card'><div class='eyebrow'>Composición · " +
          esc(c.n) + "</div><div class='barras compact' id='impGlosa'></div></div>" +
        "<div class='sub-card'><div class='eyebrow'>Mayores importadores</div>" +
          "<div class='barras compact' id='impTop'></div></div></div>";
      barras(document.getElementById("impGlosa"), c.glosas.map(function (g) {
        return { n: g.g, v: g.fob, t: pFob(g.fob, SEM) }; }));
      barras(document.getElementById("impTop"), c.top.map(function (t) {
        return { n: t.n, v: t.fob, t: pFob(t.fob, SEM) }; }));
    }

    var tC = document.getElementById("tImpCat");
    tC.onclick = function (ev) {
      var tr = ev.target.closest("tbody tr");
      if (!tr) return;
      var nombre = (tr.querySelector("td.l b") || {}).textContent;
      detalle(D.cats.filter(function (x) { return x.n === nombre; })[0]);
    };
    detalle(mayor);

    barras(document.getElementById("impRef"), D.ref.map(function (r) {
      return { n: r.g, v: r.fob, t: pFob(r.fob, SEM) }; }));

    tabla(document.getElementById("tImpFuera"), [
      { k: "p", t: "Partida", l: 1, f: function (r) {
          return "<span class='mono'>" + esc(r.p) + "</span>"; } },
      { k: "n", t: "Qué es", l: 1, f: function (r) { return esc(r.n); } },
      { k: "fob", t: "FOB " + pSuf(SEM), f: function (r) {
          return pFob(r.fob, SEM); } },
      { k: "m", t: "Por qué no entra", l: 1, f: function (r) {
          return "<span class='sub2'>" + esc(r.m) + "</span>"; } },
    ], D.fuera, { sort: "fob" });

    document.getElementById("impNota").innerHTML =
      "Microdatos de manifiestos de importación de SUNAT bajo la Ley 27806, " +
      m.semanas + " semanas de junio a agosto de 2026: " + nf(m.lineas_pais) +
      " líneas por " + usd(m.fob_pais) + ", que es toda la importación del " +
      "país. La clasificación se escribe a la longitud de partida que cada " +
      "caso necesita, porque a cuatro dígitos varias mezclan usos " +
      "incompatibles: <span class='mono'>8701</span> junta el tractor agrícola " +
      "con el tractocamión de carretera, y <span class='mono'>3002</span> la " +
      "vacuna humana con la veterinaria. El anualizado extrapola las " +
      m.semanas + " semanas sin corregir estacionalidad. Las " + usd(m.fob_fuera) +
      " de la tabla de exclusiones no son gasto agrícola no contado: son el " +
      "tamaño de la zona ambigua, donde el arancel no permite saber si el uso " +
      "es agrícola o industrial.";
}

/* ------------------------------------------------ importadores de insumos --
   La capa histórica de la subcategoría. Se apoya en dos archivos que arma el
   pipeline desde los manifiestos de aduanas: `mercado` con los totales y
   `importadores` con una entrada por RUC.

   La regla que gobierna todo lo que sigue: **un mes sin operaciones no es un
   cero**. Puede ser que la empresa no importó o que esa semana todavía no se
   bajó, y son cosas opuestas. Por eso cada año trae las semanas de origen que
   lo respaldan y, sin semanas, la respuesta es «sin datos» y no US$ 0.

   Y lo que se muestra es valor importado, nunca facturación: el FOB de una
   importación no dice nada sobre las ventas de la empresa. */
var MESES_IMP = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
/* Los importadores del directorio. El chip de clase muestra solo los que no
   estan en el padron agro; el universo real incluye a los que si estan y
   ademas importan, y ese es el numero que corresponde declarar. */
var EMP_IMPORTADORES = 0;

function impDatos() {
  return Promise.all([cargar("importaciones/mercado"),
                      cargar("importaciones/importadores")]);
}

/* ---------------------------------------- «Qué importa este mercado» ------
   El bloque deja recorrer mercado → año → categoría → partida → empresa sin
   salir del módulo de empresas. Todo sale de `importaciones/panel`, un cubo de
   0.45 MB que ya trae cada corte sumado, de modo que moverse entre niveles no
   pide nada a la red.

   Dos reglas gobiernan lo que se puede afirmar:

   1. Un año sin semanas descargadas no vale cero. Vale «pendiente de carga»,
      y así se dice. Un año medido en el que nadie importó sí es un cero.
   2. No se compara contra un año que no da para comparar. La variación
      interanual exige dos años completos —45 de 52 semanas archivadas—; si
      alguno no llega, la respuesta es N/D con el motivo a la vista. */
var IMPP = null;
var IMPQ = { vista: "anio", anio: "", cat: "", part: "", tope: 10, q: "",
             serie: "" };

function impCompleto(a) {
  return (IMPP.cobertura_semanas[a] || 0) >= IMPP.semanas_completo;
}
function impMedido(a) { return (IMPP.cobertura_semanas[a] || 0) > 0; }
function impEnCurso(a) { return a === IMPP.anio_en_curso; }

/* Cómo se nombra un año en la interfaz. El año en curso nunca aparece a secas:
   arrastra su «YTD» a todas partes para que nadie lo lea como año cerrado. */
function impEt(a) {
  if (impEnCurso(a)) return a + " YTD";
  return a;
}
function impDiasFalta(a) {
  return (IMPP.dias_sin_cubrir_por_anio || {})[a] || 0;
}

function impPie(a) {
  var s = IMPP.cobertura_semanas[a] || 0;
  if (!s) return "pendiente de carga";
  // Las semanas archivadas no siempre cubren el año entero, así que el pie
  // dice los días que ningún archivo respalda. Cuando faltaban, era porque la
  // semana que cruza el año viene partida en dos archivos y el pipeline solo
  // pedía el entero; recuperados, hoy suele no faltar ninguno.
  var f = impDiasFalta(a);
  var cola = f ? " · faltan " + f + (f > 1 ? " días" : " día") : "";
  if (impEnCurso(a)) return s + " semanas al " + IMPP.ultimo_registro + cola;
  return s + " de 52 semanas archivadas" + cola;
}

/* Variación interanual. Solo entre dos años completos: contra un año a medias
   la cifra diría más de lo que la medición aguanta. */
function impVar(a, valAct, valPrev) {
  var prev = String(+a - 1);
  if (!impCompleto(a)) {
    return "N/D · " + (impEnCurso(a) ? "año en curso" : "año incompleto");
  }
  if (!impMedido(prev)) return "N/D · " + prev + " sin descargar";
  if (!impCompleto(prev)) return "N/D · " + prev + " incompleto";
  if (!valPrev) return "N/D · sin base en " + prev;
  var v = 100 * (valAct - valPrev) / valPrev;
  var f = impDiasFalta(a) + impDiasFalta(prev);
  return (v >= 0 ? "+" : "") + nf(v, 1) + "% vs " + prev +
    (f ? " (faltan " + f + " días entre ambos)" : "");
}

function kpi(v, l, s) {
  return "<div><span class='v'>" + v + "</span><span class='l'>" + l +
    "</span><span class='s'>" + esc(s || "") + "</span></div>";
}

/* Serie temporal de FOB por año. Tres estados de barra, que son tres cosas
   distintas: medida, medida a medias —rayada, no comparable— y sin medir
   —hueco punteado—. */
function impSerie(el, filas, titulo) {
  var mx = Math.max.apply(null, filas.map(function (f) {
    return f.hay ? f.v : 0; }));
  if (!isFinite(mx) || mx <= 0) mx = 1;
  el.innerHTML = '<div class="serie">' + filas.map(function (f) {
    var a = f.a;
    if (!f.hay) {
      return '<div class="sb vacio" title="' + esc(titulo + "\n" + a +
        "\n\nSin semanas descargadas: no hay información para este año") +
        '"><i></i><b>' + a + "</b></div>";
    }
    var par = !impCompleto(a);
    var h = Math.max(2, Math.round(100 * f.v / mx));
    return '<div class="sb' + (par ? " parcial" : "") +
      (f.v > 0 ? "" : " cero") + '" title="' + esc(titulo + "\n" + impEt(a) +
      "\n\nFOB: US$ " + nf(f.v) +
      (f.p !== undefined ? "\nParticipación: " + nf(f.p, 1) + "%" : "") +
      (f.ops !== undefined ? "\nOperaciones: " + nf(f.ops) : "") +
      (f.emp !== undefined ? "\nImportadores: " + nf(f.emp) : "") +
      "\n" + impPie(a)) + '"><i style="height:' + (f.v > 0 ? h : 2) +
      '%"></i><b>' + a + (par ? "*" : "") + "</b></div>";
  }).join("") + "</div>";
}

/* Filas de composición que además llevan a algún lado. Se reutiliza la misma
   rejilla de `.bar` del resto del sitio y solo se agrega la columna del
   indicador, para que un bloque que ahora se puede recorrer siga pareciendo
   el mismo bloque. */
function barrasClic(el, filas, alClic) {
  var mx = Math.max.apply(null, filas.map(function (r) { return r.v; })) || 1;
  el.innerHTML = filas.map(function (r) {
    return '<div class="bar clic" role="button" tabindex="0" data-k="' +
      esc(r.k) + '" title="' + esc(r.tt || "") + '">' +
      '<span class="bn">' + esc(r.n) + "</span>" +
      '<span class="bv mono">' + r.t + "</span>" +
      '<span class="bt"><i style="width:' + (100 * r.v / mx).toFixed(1) +
      '%"></i></span>' +
      '<span class="bp mono">' + pct(r.p, 1) + "</span>" +
      '<span class="bx">&rsaquo;</span></div>';
  }).join("");
  function ir(ev) {
    var f = ev.target.closest(".bar.clic");
    if (f) alClic(f.dataset.k);
  }
  el.onclick = ir;
  el.onkeydown = function (ev) {
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); ir(ev); }
  };
}

/* ------------------------------------------------------------ controles -- */
function impControles() {
  var sel = document.getElementById("impAnio");
  var esEvol = IMPQ.vista === "evol";
  document.querySelectorAll("#impVista .chip").forEach(function (b) {
    b.setAttribute("aria-pressed", String(b.dataset.v === IMPQ.vista)); });

  sel.innerHTML = IMPP.anios_pedidos.map(function (a) {
    var hay = impMedido(a);
    return '<option value="' + a + '"' + (hay ? "" : " disabled") +
      (a === IMPQ.anio ? " selected" : "") + ">" + impEt(a) +
      (hay ? "" : " · pendiente de carga") + "</option>";
  }).join("");
  document.getElementById("impAnio").hidden = esEvol;
  document.getElementById("impAnioEt").hidden = esEvol;

  var ser = document.getElementById("impSerie");
  ser.hidden = !esEvol;
  document.getElementById("impSerieEt").hidden = !esEvol;
  if (esEvol) {
    var cats = Object.keys(IMPP.cats).sort();
    ser.innerHTML = '<option value="">Mercado total</option>' +
      cats.map(function (c) {
        return '<option value="' + esc(c) + '"' +
          (c === IMPQ.serie ? " selected" : "") + ">" + esc(c) + "</option>";
      }).join("");
  }
}

/* --------------------------------------------------------------- migas --- */
function impMigas() {
  var m = [["Empresas", ""], ["Importaciones", "raiz"]];
  if (IMPQ.cat) m.push([IMPQ.cat, "cat"]);
  if (IMPQ.part) m.push([impNombreParte(IMPQ.part), "part"]);
  var caja = document.getElementById("impMiga");
  caja.innerHTML = m.map(function (x, i) {
    var ult = i === m.length - 1;
    if (!x[1] || ult) return "<span>" + esc(x[0]) + "</span>";
    return '<a href="#" data-n="' + x[1] + '">' + esc(x[0]) + "</a>";
  }).join(' <span class="sep">&rsaquo;</span> ');
  caja.onclick = function (ev) {
    var a = ev.target.closest("a[data-n]");
    if (!a) return;
    ev.preventDefault();
    if (a.dataset.n === "raiz") { IMPQ.cat = ""; IMPQ.part = ""; }
    if (a.dataset.n === "cat") IMPQ.part = "";
    IMPQ.q = ""; IMPQ.tope = 10;
    pintarPanelImp();
  };
}

function impNombreParte(p) {
  var n = IMPP.nombres_partida[p];
  var cod = p.slice(0, 4) + "." + p.slice(4);
  return n ? n + " (" + cod + ")" : "Partida " + cod;
}

/* ---------------------------------------------------- nivel 0 · mercado -- */
function impNivelMercado() {
  var a = IMPQ.anio, T = IMPP.total[a];
  var caja = document.getElementById("impResumen");
  if (!T) {
    caja.innerHTML =
      kpi(nf(EMP_IMPORTADORES), "importadores identificados",
          "con RUC, cruzados contra el padrón") +
      kpi("N/D", "con operación verificada en " + a, "sin información") +
      kpi("N/D", "FOB importado " + a, "año pendiente de carga") +
      kpi("N/D", "operaciones aduaneras", "no hay manifiestos de " + a);
    document.getElementById("impMercadoCat").innerHTML =
      '<p class="sub">Sin información disponible para ' + a + ". Los " +
      "manifiestos de ese año todavía no se descargan, de modo que no hay " +
      "nada que repartir. No es que se haya importado por US$ 0.</p>";
    return;
  }
  caja.innerHTML =
    kpi(nf(EMP_IMPORTADORES), "importadores identificados",
        "con RUC, cruzados contra el padrón") +
    kpi(nf(T.emp), "con operación verificada en " + impEt(a), impPie(a)) +
    kpi(usd(T.fob), "FOB importado " + impEt(a),
        impCompleto(a) ? "año completo, medido" : "año incompleto: " +
          impPie(a)) +
    kpi(nf(T.ops), "operaciones aduaneras", "una fila por declaración");

  var filas = Object.keys(IMPP.cats).map(function (c) {
    var x = IMPP.cats[c].anios[a];
    return x ? { k: c, n: c, v: x.fob, t: usd(x.fob),
                 p: 100 * x.fob / T.fob,
                 tt: c + "\n" + impEt(a) + "\n\nFOB: US$ " + nf(x.fob) +
                   "\nParticipación: " + nf(100 * x.fob / T.fob, 1) +
                   "%\nOperaciones: " + nf(x.ops) + "\nImportadores: " +
                   nf(x.emp) + "\n\nVer detalle" } : null;
  }).filter(Boolean).sort(function (x, y) { return y.v - x.v; });

  barrasClic(document.getElementById("impMercadoCat"), filas, function (c) {
    IMPQ.cat = c; IMPQ.part = ""; IMPQ.tope = 10; IMPQ.q = "";
    pintarPanelImp();
  });
}

/* -------------------------------------------------- nivel 0 · evolución -- */
function impNivelEvolucion() {
  var c = IMPQ.serie;
  var dat = c ? IMPP.cats[c].anios : IMPP.total;
  var nom = c || "Mercado total de insumos";
  var medidos = IMPP.anios_pedidos.filter(impMedido);
  var acum = medidos.reduce(function (s, a) {
    return s + (dat[a] ? dat[a].fob : 0); }, 0);
  var completos = medidos.filter(impCompleto);
  var ult = completos.length ? completos[completos.length - 1] : null;

  document.getElementById("impResumen").innerHTML =
    kpi(nf(medidos.length), "años con información",
        "de los " + IMPP.anios_pedidos.length + " pedidos") +
    kpi(usd(acum), "FOB acumulado medido", "no anualizado ni estimado") +
    kpi(ult ? usd(dat[ult].fob) : "N/D",
        ult ? "FOB " + ult + ", año completo" : "último año completo",
        ult ? impPie(ult) : "ningún año completo descargado") +
    kpi(dat[IMPP.anio_en_curso] ? usd(dat[IMPP.anio_en_curso].fob) : "N/D",
        "FOB " + IMPP.anio_en_curso + " YTD",
        "acumulado al " + IMPP.ultimo_registro + ", año en curso");

  document.getElementById("impMercadoCat").innerHTML = "";
  var ev = document.getElementById("impEvol");
  ev.hidden = false;
  ev.innerHTML = '<div class="eyebrow">Evolución · ' + esc(nom) +
    " · FOB importado</div><div id='impEvolSerie'></div>" +
    "<p class='sub' id='impEvolNota'></p>";

  var tot = IMPP.total;
  impSerie(document.getElementById("impEvolSerie"),
    IMPP.anios_pedidos.map(function (a) {
      var x = dat[a];
      return { a: a, hay: !!x && impMedido(a), v: x ? x.fob : 0,
               ops: x ? x.ops : undefined, emp: x ? x.emp : undefined,
               p: (c && x && tot[a]) ? 100 * x.fob / tot[a].fob : undefined };
    }), nom);

  var sin = IMPP.anios_pedidos.filter(function (a) { return !impMedido(a); });
  var parc = medidos.filter(function (a) { return !impCompleto(a); });
  document.getElementById("impEvolNota").textContent =
    (parc.length ? "* " + parc.map(function (a) {
        return a + " (" + IMPP.cobertura_semanas[a] + " de 52 semanas" +
          (impEnCurso(a) ? ", año en curso" : "") + ")"; }).join(", ") +
      ": años incompletos, no comparables contra uno entero. " : "") +
    (sin.length ? sin.join(" y ") + " aparecen en hueco: sus manifiestos no " +
      "se han descargado. No son años sin importaciones." : "");
}

/* ------------------------------------------------- nivel 1 · categoría --- */
function impNivelCategoria() {
  var a = IMPQ.anio, c = IMPQ.cat, C = IMPP.cats[c];
  var X = C.anios[a], T = IMPP.total[a];
  var prev = String(+a - 1), P = C.anios[prev];

  var det = document.getElementById("impDetalle");
  document.getElementById("impMercadoCat").innerHTML = "";
  document.getElementById("impEvol").hidden = true;

  if (!X) {
    document.getElementById("impResumen").innerHTML =
      kpi("N/D", "FOB importado " + a,
          impMedido(a) ? "sin operaciones de esta categoría en " + a
                       : "año pendiente de carga");
    det.innerHTML = '<p class="sub">' + esc(c) + " no registra importaciones " +
      "en " + a + (impMedido(a)
        ? ". Ese año sí se midió —" + IMPP.cobertura_semanas[a] +
          " semanas archivadas—, así que la respuesta es que no hubo."
        : ", y ese año todavía no se descarga: no hay información.") + "</p>";
    return;
  }

  document.getElementById("impResumen").innerHTML =
    kpi(usd(X.fob), "FOB importado " + impEt(a),
        impVar(a, X.fob, P ? P.fob : 0)) +
    kpi(pct(100 * X.fob / T.fob, 1), "del mercado en " + impEt(a), impPie(a)) +
    kpi(nf(X.emp), "importadores", impVar(a, X.emp, P ? P.emp : 0)) +
    kpi(nf(X.ops), "operaciones", impVar(a, X.ops, P ? P.ops : 0));

  var tot = IMPP.total;
  det.innerHTML =
    '<div class="eyebrow">Evolución de importaciones · ' + esc(c) + "</div>" +
    "<div id='impCatSerie'></div><p class='sub' id='impCatNota'></p>" +
    "<div class='eyebrow' style='margin-top:14px'>Principales productos y " +
    "partidas · " + esc(impEt(a)) + "</div>" +
    "<div class='barras compact' id='impCatPart'></div>" +
    "<p class='sub'>Nombre oficial de la subpartida NANDINA. La categoría la " +
    "decide el arancel, no la descripción del declarante.</p>" +
    "<div class='eyebrow' style='margin-top:14px'>Principales países de " +
    "origen</div><div class='barras compact' id='impCatPais'></div>" +
    impBloqueEmpresas();

  impSerie(document.getElementById("impCatSerie"),
    IMPP.anios_pedidos.map(function (y) {
      var x = C.anios[y];
      return { a: y, hay: !!x && impMedido(y), v: x ? x.fob : 0,
               ops: x ? x.ops : undefined, emp: x ? x.emp : undefined,
               p: (x && tot[y]) ? 100 * x.fob / tot[y].fob : undefined };
    }), c);
  var sin = IMPP.anios_pedidos.filter(function (y) { return !impMedido(y); });
  document.getElementById("impCatNota").textContent =
    "FOB de " + c + " año por año. " +
    (sin.length ? sin.join(" y ") + " sin descargar: hueco, no cero." : "");

  var parts = C.partidas[a] || [];
  barrasClic(document.getElementById("impCatPart"), parts.map(function (p) {
    return { k: p.p, n: impNombreParte(p.p), v: p.fob, t: usd(p.fob),
             p: 100 * p.fob / X.fob,
             tt: impNombreParte(p.p) + "\n" + impEt(a) + "\n\nFOB: US$ " +
               nf(p.fob) + "\nParticipación en la categoría: " +
               nf(100 * p.fob / X.fob, 1) + "%\nOperaciones: " + nf(p.ops) +
               "\nImportadores: " + nf(p.emp) + "\n\nVer importadores" };
  }), function (p) {
    IMPQ.part = p; IMPQ.tope = 10; IMPQ.q = "";
    pintarPanelImp();
  });

  barras(document.getElementById("impCatPais"),
    (C.paises[a] || []).map(function (p) {
      return { n: pais(p.n), v: p.fob, t: usd(p.fob),
               p: 100 * p.fob / X.fob }; }));

  impPintarEmpresas();
}

/* --------------------------------------------------- nivel 2 · partida --- */
function impNivelPartida() {
  var a = IMPQ.anio, c = IMPQ.cat, p = IMPQ.part;
  var C = IMPP.cats[c], X = C.anios[a];
  var fila = (C.partidas[a] || []).filter(function (x) {
    return x.p === p; })[0];
  document.getElementById("impMercadoCat").innerHTML = "";
  document.getElementById("impEvol").hidden = true;
  var det = document.getElementById("impDetalle");

  if (!fila) {
    document.getElementById("impResumen").innerHTML =
      kpi("N/D", impNombreParte(p) + " en " + a,
          impMedido(a) ? "sin operaciones en este año"
                       : "año pendiente de carga");
    det.innerHTML = '<p class="sub">Sin registros de esta partida en ' + a +
      ".</p>";
    return;
  }
  document.getElementById("impResumen").innerHTML =
    kpi(usd(fila.fob), "FOB importado " + impEt(a), impPie(a)) +
    kpi(pct(100 * fila.fob / X.fob, 1), "de " + esc(c), "dentro de la categoría") +
    kpi(nf(fila.emp), "importadores", "con operación en esta partida") +
    kpi(nf(fila.ops), "operaciones", "una fila por declaración");

  det.innerHTML =
    '<div class="eyebrow">Presencia de la partida año por año</div>' +
    "<div id='impPartSerie'></div>" +
    "<p class='sub'>Subpartida " + esc(p.slice(0, 4) + "." + p.slice(4)) +
    " dentro de " + esc(c) + ".</p>" + bloquePrecio(p, a) +
    impBloqueEmpresas();

  impSerie(document.getElementById("impPartSerie"),
    IMPP.anios_pedidos.map(function (y) {
      var f = (C.partidas[y] || []).filter(function (x) {
        return x.p === p; })[0];
      return { a: y, hay: !!f && impMedido(y), v: f ? f.fob : 0,
               ops: f ? f.ops : undefined, emp: f ? f.emp : undefined };
    }), impNombreParte(p));

  pintarPrecio(p, a);
  impPintarEmpresas();
}

/* ------------------------------------------ precio de importación --------
   US$ por kilo, que ya estaba en los datos —cada operación trae su FOB y su
   peso— y solo hacía falta decidir dónde significa algo.

   No en todas las partidas, y el criterio no es de gusto: se publica precio
   donde el kilo es la unidad en que se comercia y donde la tonelada del mes se
   mueve dentro de una banda estrecha. Los fitosanitarios quedan fuera porque
   se declaran en litros y porque un insecticida de US$ 3/kg y otro de US$ 200
   comparten subpartida. La regla, y el motivo de cada rechazo, viajan en el
   propio archivo. */
var IMPPR = null;

function preciosDe(p) {
  return IMPPR && IMPPR.partidas[p];
}

/* La variación de precio contra el año anterior. A diferencia del FOB, aquí no
   hace falta que el año esté completo para que el promedio signifique algo:
   un valor unitario de once semanas sigue siendo el precio de esas once
   semanas. Lo que sí se declara es sobre cuánta tonelada se calculó. */
function deltaPrecio(x, prev) {
  if (!prev || !prev.uv) return null;
  return 100 * (x.uv - prev.uv) / prev.uv;
}

function upk(v) {
  return "US$ " + nf(v, v < 10 ? 3 : 2) + "/kg";
}
function tons(kg) {
  return kg >= 1e6 ? nf(kg / 1e6, 1) + " M t" : nf(kg / 1000) + " t";
}

function bloquePrecio(p, a) {
  var P = preciosDe(p);
  if (!P) {
    var motivo = IMPPR && IMPPR.rechazadas[p];
    return '<div class="eyebrow" style="margin-top:16px">Precio de ' +
      "importación</div><p class='sub'>Esta subpartida no publica precio por " +
      "kilo" + (motivo ? ": " + esc(motivo) : "") + ". Calcularlo daría un " +
      "número, no un precio.</p>";
  }
  return '<div class="eyebrow" style="margin-top:16px">Precio de importación · ' +
    "US$ por kilo</div>" +
    '<div class="kpis" id="impPrecioKpi" style="margin:6px 0 10px"></div>' +
    "<div id='impPrecioAnual'></div>" +
    "<p class='sub' id='impPrecioNota'></p>" +
    "<div class='eyebrow' style='margin-top:12px'>Precio mes a mes · " +
    esc(impEt(a)) + "</div><div id='impPrecioMes'></div>" +
    "<p class='sub' id='impPrecioMesNota'></p>";
}

function pintarPrecio(p, a) {
  var P = preciosDe(p);
  if (!P) return;
  var x = P.anios[a], prev = P.anios[String(+a - 1)];
  var d = x ? deltaPrecio(x, prev) : null;

  document.getElementById("impPrecioKpi").innerHTML =
    kpi(x ? upk(x.uv) : "N/D", "precio medio " + impEt(a),
        x ? "sobre " + tons(x.kg) + " en " + nf(x.ops) + " operaciones"
          : "sin operaciones con peso en " + a) +
    kpi(d === null ? "N/D" : (d >= 0 ? "+" : "") + nf(d, 1) + "%",
        "vs " + String(+a - 1),
        d === null ? "sin precio del año anterior"
                   : "de " + upk(prev.uv) + " a " + upk(x.uv)) +
    kpi(x ? nf(x.p25, 3) + " – " + nf(x.p75, 3) : "N/D",
        "US$/kg · mitad central del año",
        "la mitad de las operaciones cae en esta banda") +
    kpi(x ? tons(x.kg) : "N/D", "tonelaje importado " + impEt(a),
        "peso neto declarado");

  /* La serie de precio no lleva las marcas de cobertura del FOB. Un año a
     medias importa menos toneladas, pero el precio al que las importó es el
     precio al que las importó: no es una suma incompleta, es un promedio. */
  /* La serie de precio no arranca en cero. Un precio que se movió entre 0.31
     y 0.66 dibujado desde cero da cinco barras casi iguales, que es lo
     contrario de lo que pasó: el fertilizante se abarató a la mitad. Se
     recorta la escala y se dice cuál es, para que nadie lea la altura como si
     fuera proporcional al precio. */
  var anios = IMPP.anios_pedidos;
  var vals = anios.map(function (y) { return P.anios[y]; });
  var us = vals.filter(Boolean).map(function (v) { return v.uv; });
  var hi = Math.max.apply(null, us), lo = Math.min.apply(null, us);
  var piso = lo - (hi - lo) * 0.25;
  if (!(piso > 0)) piso = 0;
  function alto(v) {
    return hi > piso
      ? Math.max(3, Math.round(100 * (v - piso) / (hi - piso))) : 100;
  }
  document.getElementById("impPrecioAnual").innerHTML =
    '<div class="serie">' + anios.map(function (y, i) {
      var v = vals[i];
      if (!v) {
        return '<div class="sb vacio" title="' + y +
          ' · sin operaciones con peso"><i></i><b>' + y + "</b></div>";
      }
      return '<div class="sb" title="' + esc(impNombreParte(p) + "\n" +
        impEt(y) + "\n\nPrecio: " + upk(v.uv) + "\nMitad central: " +
        upk(v.p25) + " a " + upk(v.p75) + "\nTonelaje: " + tons(v.kg) +
        "\nOperaciones: " + nf(v.ops)) + '"><i style="height:' + alto(v.uv) +
        '%"></i><b>' + y + "</b></div>";
    }).join("") + "</div>";

  var conP = anios.filter(function (y) { return P.anios[y]; });
  var pmin = null, pmax = null;
  conP.forEach(function (y) {
    var u = P.anios[y].uv;
    if (pmin === null || u < P.anios[pmin].uv) pmin = y;
    if (pmax === null || u > P.anios[pmax].uv) pmax = y;
  });
  document.getElementById("impPrecioNota").textContent =
    (pmin && pmax && pmin !== pmax
      ? "Del máximo de " + upk(P.anios[pmax].uv) + " en " + pmax +
        " al mínimo de " + upk(P.anios[pmin].uv) + " en " + pmin + ". "
      : "") +
    "Valor unitario: suma de FOB sobre suma de kilos, ponderado por " +
    "tonelada. La escala arranca en " + upk(piso) + " y no en cero, para que " +
    "se vea el movimiento: la altura de la barra no es proporcional al precio.";

  /* Mes a mes del año elegido. */
  var mm = [], hay = [];
  for (var m = 1; m <= 12; m++) {
    var k = a + "-" + (m < 10 ? "0" + m : m);
    var v = P.meses[k];
    hay.push(!!v);
    mm.push(v ? v.uv : 0);
  }
  var conV = mm.filter(function (v, i) { return hay[i]; });
  var hiM = conV.length ? Math.max.apply(null, conV) : 1;
  var loM = conV.length ? Math.min.apply(null, conV) : 0;
  var pisoM = loM - (hiM - loM) * 0.25;
  if (!(pisoM > 0)) pisoM = 0;
  document.getElementById("impPrecioMes").innerHTML =
    '<div class="serie">' + mm.map(function (v, i) {
      if (!hay[i]) {
        return '<div class="sb vacio" title="' + MESES_IMP[i] + " " + a +
          ' · sin operaciones suficientes para un precio"><i></i><b>' +
          MESES_IMP[i] + "</b></div>";
      }
      var k = a + "-" + (i < 9 ? "0" + (i + 1) : i + 1);
      return '<div class="sb" title="' + esc(MESES_IMP[i] + " " + a +
        "\n\nPrecio: " + upk(v) + "\nTonelaje: " + tons(P.meses[k].kg) +
        "\nOperaciones: " + nf(P.meses[k].ops)) + '"><i style="height:' +
        (hiM > pisoM
          ? Math.max(3, Math.round(100 * (v - pisoM) / (hiM - pisoM))) : 100) +
        '%"></i><b>' + MESES_IMP[i] + "</b></div>";
    }).join("") + "</div>";
  var n = hay.filter(Boolean).length;
  document.getElementById("impPrecioMesNota").textContent =
    n + " de 12 meses de " + a + " tienen operaciones suficientes para " +
    "calcular un precio. Escala desde " + upk(pisoM) + ", no desde cero. Un mes sin barra no es un mes sin precio: es un mes " +
    "con menos de cinco operaciones, donde el promedio diría más de lo que " +
    "aguanta." +
    (P.generica ? " Ojo: la subpartida es un casillero «los demás», así que " +
      "este precio es el del producto que domina su tonelada, no el de una " +
      "sola mercancía." : "");
}

/* ------------------------------------------- ranking de importadores ----- */
function impBloqueEmpresas() {
  return "<div class='eyebrow' style='margin-top:16px'>Principales " +
    "importadores</div>" +
    "<div class='filters' style='border-bottom:0; padding:10px 0'>" +
      "<div class='chips' id='impTope'></div>" +
      "<input type='search' id='impBuscar' placeholder='Buscar empresa o RUC…' " +
      "aria-label='Buscar empresa o RUC'></div>" +
    "<div class='tw'><table id='impEmpresas'></table></div>" +
    "<p class='sub' id='impEmpNota'></p>";
}

function impFilasEmpresas() {
  var a = IMPQ.anio, C = IMPP.cats[IMPQ.cat];
  if (IMPQ.part) return ((C.emp_part[a] || {})[IMPQ.part] || []);
  return (C.empresas[a] || []);
}

function impPintarEmpresas() {
  var todas = impFilasEmpresas();
  var base = todas.reduce(function (s, e) { return s + e.fob; }, 0) || 1;
  var q = IMPQ.q.trim().toLowerCase();
  var filtradas = !q ? todas : todas.filter(function (e) {
    return e.r.indexOf(q) >= 0 ||
      (IMPP.nombres[e.r] || "").toLowerCase().indexOf(q) >= 0;
  });
  var muestra = IMPQ.tope ? filtradas.slice(0, IMPQ.tope) : filtradas;

  var topes = document.getElementById("impTope");
  topes.innerHTML = [[10, "Top 10"], [25, "Top 25"], [50, "Top 50"],
                     [0, "Todos"]].map(function (t) {
    return '<button class="chip" data-t="' + t[0] + '" aria-pressed="' +
      (IMPQ.tope === t[0]) + '">' + t[1] + "</button>";
  }).join("");
  topes.onclick = function (ev) {
    var b = ev.target.closest("button");
    if (!b) return;
    IMPQ.tope = +b.dataset.t;
    impPintarEmpresas();
  };
  var bus = document.getElementById("impBuscar");
  bus.value = IMPQ.q;
  bus.oninput = function () { IMPQ.q = this.value; impPintarEmpresas(); };

  var t = document.getElementById("impEmpresas");
  /* Dentro de una partida con precio publicable, el ranking gana dos columnas:
     a qué precio compró cada empresa y cuánto se apartó del mercado de ese
     año. Es la pregunta comercial que el FOB solo no contesta —quién compra
     bien— y sale de dividir lo que ya estaba en cada declaración. */
  var pr = IMPQ.part && preciosDe(IMPQ.part);
  var prAnio = pr && pr.anios[IMPQ.anio];
  var prEmp = {};
  if (pr) {
    (pr.empresas[IMPQ.anio] || []).forEach(function (x) { prEmp[x.r] = x; });
  }
  var colP = prAnio ? "<th>US$/kg</th><th>vs mercado</th>" : "";

  t.innerHTML = "<thead><tr><th>#</th><th class='l'>Importador</th>" +
    "<th class='l'>RUC</th><th>FOB</th><th>%</th><th>Oper.</th>" + colP +
    "</tr></thead><tbody>" +
    (muestra.length ? muestra.map(function (e) {
      var x = prEmp[e.r], cel = "";
      if (prAnio) {
        var d = x ? 100 * (x.uv - prAnio.uv) / prAnio.uv : null;
        cel = "<td class='n'>" + (x ? upk(x.uv) : "—") + "</td>" +
          "<td class='n' title='" + (x ? esc("Precio del mercado en " +
            IMPQ.anio + ": " + upk(prAnio.uv) + "\n" +
            "Esta empresa: " + upk(x.uv) + " sobre " + tons(x.kg))
            : "sin peso declarado") +
          "'>" + (d === null ? "—"
            : (d >= 0 ? "+" : "") + nf(d, 1) + "%") + "</td>";
      }
      return "<tr><td class='l n'>" + (todas.indexOf(e) + 1) + "</td>" +
        "<td class='l name'><a href='#empresa=" + e.r + "'>" +
        esc(IMPP.nombres[e.r] || e.r) + "</a></td>" +
        "<td class='l n'>" + e.r + "</td>" +
        "<td class='n'>" + usd(e.fob) + "</td>" +
        "<td class='n'>" + pct(100 * e.fob / base, 1) + "</td>" +
        "<td class='n'>" + nf(e.ops) + "</td>" + cel + "</tr>";
    }).join("") : "<tr><td class='l' colspan='" + (prAnio ? 8 : 6) +
      "'>Ninguna empresa coincide con la búsqueda.</td></tr>") + "</tbody>";

  document.getElementById("impEmpNota").textContent =
    (q ? filtradas.length + " de " + todas.length + " importadores coinciden. "
       : nf(todas.length) + " importadores con operación registrada. ") +
    "El porcentaje es sobre el FOB de " +
    (IMPQ.part ? "la partida" : "la categoría") + " en " + impEt(IMPQ.anio) +
    ". Valor FOB importado, no facturación de la empresa." +
    (prAnio ? " «vs mercado» compara el precio pagado por cada empresa contra " +
      "el valor unitario de la partida ese año (" + upk(prAnio.uv) +
      "); un guion significa que esa empresa no declaró peso." : "");
}

/* ------------------------------------------------------------ orquesta --- */
function pintarPanelImp() {
  impControles();
  impMigas();
  var det = document.getElementById("impDetalle");
  det.innerHTML = "";
  document.getElementById("impEvol").hidden = true;
  if (IMPQ.vista === "evol") { impNivelEvolucion(); }
  else if (IMPQ.part) { impNivelPartida(); }
  else if (IMPQ.cat) { impNivelCategoria(); }
  else { impNivelMercado(); }
  impNotaCobertura();
}

function impNotaCobertura() {
  var con = IMPP.anios_con_dato;
  var faltan = IMPP.anios_pedidos.filter(function (a) {
    return con.indexOf(a) < 0; });
  document.getElementById("impCobertura").innerHTML =
    "<b>Cobertura de la fuente.</b> Los manifiestos de SUNAT se archivan " +
    "semana a semana; hoy hay <b>" +
    Object.keys(IMPP.cobertura_semanas).reduce(function (s, a) {
      return s + IMPP.cobertura_semanas[a]; }, 0) +
    " semanas</b> descargadas: " +
    con.map(function (a) {
      return a + " (" + IMPP.cobertura_semanas[a] + ")"; }).join(", ") + ". " +
    (faltan.length
      ? "<b>" + faltan.join(", ") + "</b> todavía no se descargan: esos años " +
        "no aparecen en cero, aparecen sin dato."
      : (function () {
          var ent = con.filter(function (a) {
            return !impEnCurso(a) && !impDiasFalta(a); });
          var par = con.filter(function (a) {
            return !impEnCurso(a) && impDiasFalta(a); });
          if (!par.length) return "Los cinco años están completos.";
          // Un año con sus 52 semanas todavía puede no estar entero, y es
          // preferible decirlo que dejar que se lea como cierre.
          return "Los cinco años están descargados, pero enteros día por día " +
            "solo lo están " + (ent.join(", ") || "ninguno") + ": a " +
            par.join(", ") + " le faltan días sueltos del calendario.";
        })()) +
    " El valor mostrado es <b>FOB importado</b> y no facturación de la " +
    "empresa." +
    (IMPP.reservado && IMPP.reservado.ops
      ? " <b>" + usd(IMPP.reservado.fob) + "</b> en " + nf(IMPP.reservado.ops) +
        " operaciones corresponden a importadores persona natural, cuyo " +
        "titular SUNAT no publica por la Ley 29733 de protección de datos " +
        "personales: suman en el mercado y quedan fuera de los rankings de " +
        "empresas, porque no son una empresa sino muchas."
      : "");
}

function iniPanelImp(P) {
  IMPP = P;
  if (!IMPQ.anio) {
    var con = P.anios_con_dato;
    IMPQ.anio = con.indexOf(P.anio_en_curso) >= 0
      ? P.anio_en_curso : con[con.length - 1];
  }
  document.getElementById("impVista").onclick = function (ev) {
    var b = ev.target.closest("button");
    if (!b) return;
    IMPQ.vista = b.dataset.v;
    IMPQ.cat = ""; IMPQ.part = "";
    pintarPanelImp();
  };
  document.getElementById("impAnio").onchange = function () {
    IMPQ.anio = this.value; IMPQ.tope = 10; IMPQ.q = "";
    pintarPanelImp();
  };
  document.getElementById("impSerie").onchange = function () {
    IMPQ.serie = this.value;
    pintarPanelImp();
  };
  pintarPanelImp();
}

/* --------------------------------------------------- perfil de una empresa -- */
function bloqueImportaciones(ruc, M, IMP) {
  var e = IMP[ruc];
  if (!e) {
    return '<div class="card" style="margin-top:16px"><div class="h">' +
      "<h3>Importaciones históricas</h3></div><div class='b'><p>" +
      "Sin información histórica suficiente. Esta empresa figura en el " +
      "directorio, pero no se encontraron operaciones de importación de " +
      "insumos en las semanas de manifiestos descargadas hasta ahora.</p>" +
      "</div></div>";
  }
  var actual = M.anio_en_curso;
  var aniosConDato = Object.keys(e.por_anio).sort();
  var completos = aniosConDato.filter(function (a) {
    return a !== actual && (M.cobertura_semanas[a] || 0) >= 45; });
  var ult = completos.length ? completos[completos.length - 1] : null;

  return '<div class="card" style="margin-top:16px"><div class="h">' +
      "<h3>Importaciones históricas</h3>" +
      '<span class="eyebrow">FOB registrado en aduanas</span></div>' +
    '<div class="b">' +
      '<div class="kpis" style="margin:0 0 14px">' +
        "<div><span class='v'>" + usd(e.por_anio[actual] ? e.por_anio[actual].fob : 0) +
          "</span><span class='l'>importado " + actual + " YTD</span>" +
          "<span class='s'>hasta " + esc(e.ultima) + "</span></div>" +
        "<div><span class='v'>" + (ult ? usd(e.por_anio[ult].fob) : "sin datos") +
          "</span><span class='l'>" + (ult ? "importado " + ult : "último año completo") +
          "</span><span class='s'>" + (ult ? M.cobertura_semanas[ult] +
            " de 52 semanas archivadas" : "sin año completo descargado") +
          "</span></div>" +
        "<div><span class='v'>" + usd(e.total.fob) + "</span><span class='l'>" +
          "acumulado registrado</span><span class='s'>" + nf(e.total.ops) +
          " operaciones · CIF " + usd(e.total.cif) + "</span></div>" +
        "<div><span class='v'>" + nf(e.paises.length) + "</span><span class='l'>" +
          "países de origen</span><span class='s'>" +
          esc(e.primera) + " a " + esc(e.ultima) + "</span></div>" +
      "</div>" +

      '<div class="eyebrow">Corte por año</div>' +
      '<div class="chips" id="impAnioSel" style="margin:6px 0 10px"></div>' +
      '<div id="impMesBloque">' +
        '<div class="eyebrow">Importaciones mensuales · FOB</div>' +
        '<div class="serie" id="impMes"></div>' +
        '<p class="sub" id="impMesNota"></p>' +
      "</div>" +

      '<div class="eyebrow" style="margin-top:14px">Importaciones anuales</div>' +
      '<div class="serie" id="impAnual"></div>' +
      '<p class="sub" id="impAnualNota"></p>' +

      '<div class="grid2" style="margin-top:14px">' +
        "<div><div class='eyebrow'>Principales productos importados</div>" +
          "<div class='barras compact' id='impCat'></div></div>" +
        "<div><div class='eyebrow'>Principales países de origen</div>" +
          "<div class='barras compact' id='impPais'></div></div>" +
      "</div>" +
      "<div class='eyebrow' style='margin-top:12px'>Partidas arancelarias</div>" +
      "<div class='barras compact' id='impPart'></div>" +
      '<p class="sub" id="impCorteNota"></p>' +
      '<p class="sub">Valor <b>FOB importado</b>, no facturación de la empresa. ' +
      'Fuente: microdatos de manifiestos de SUNAT bajo la Ley 27806.</p>' +
    "</div></div>";
}

function pintarImportaciones(ruc, M, IMP) {
  var e = IMP[ruc];
  if (!e) return;
  var actual = M.anio_en_curso;
  var conDato = Object.keys(e.por_anio).sort();

  /* Selector de año. Manda sobre toda la ficha: el mensual, los productos, los
     países y las partidas. Un año se puede elegir si tiene semanas detrás
     —eso lo dice el mercado, no la empresa—; los que no las tienen se muestran
     igual, apagados, para que se vea que el hueco es de la descarga y no de la
     empresa. «Todos» agrega lo medido hasta hoy. */
  var sel = document.getElementById("impAnioSel");
  var medibles = M.anios_pedidos.filter(function (a) {
    return (M.cobertura_semanas[a] || 0) > 0; });
  var elegido = conDato.indexOf(actual) >= 0
    ? actual : (conDato[conDato.length - 1] || medibles[medibles.length - 1]);
  sel.innerHTML = '<button class="chip" data-a="" aria-pressed="false">' +
    "Todos</button>" + M.anios_pedidos.map(function (a) {
    var hay = medibles.indexOf(a) >= 0;
    return '<button class="chip" data-a="' + a + '"' +
      (hay ? "" : " disabled title=\"sin semanas descargadas para " + a + "\"") +
      ' aria-pressed="' + (a === elegido) + '">' + a +
      (a === actual ? " YTD" : "") + "</button>";
  }).join("");

  function barrasDeAnio(anio) {
    var c = anio ? ((e.cubo[anio] || {}).cat || []) : e.categorias;
    var p = anio ? ((e.cubo[anio] || {}).pais || []) : e.paises;
    var t = anio ? ((e.cubo[anio] || {}).part || []) : e.partidas;
    barras(document.getElementById("impCat"), c.slice(0, 8).map(
      function (x) { return { n: x.n, v: x.fob, t: usd(x.fob) }; }));
    barras(document.getElementById("impPais"), p.slice(0, 8).map(
      function (x) { return { n: pais(x.n), v: x.fob, t: usd(x.fob) }; }));
    barras(document.getElementById("impPart"), t.slice(0, 8).map(
      function (x) { return { n: x.n, v: x.fob, t: usd(x.fob) }; }));
    var nota = document.getElementById("impCorteNota");
    if (!nota) return;
    if (!anio) {
      nota.textContent = "Todo lo medido: " + M.total.semanas +
        " semanas archivadas entre " + e.primera + " y " + e.ultima + ".";
    } else if (!c.length) {
      nota.textContent = anio + " sí se midió —" + M.cobertura_semanas[anio] +
        " semanas archivadas— y esta empresa no registra importaciones de " +
        "insumos en ese año.";
    } else {
      nota.textContent = "Corte de " + anio + ", sobre " +
        M.cobertura_semanas[anio] + " semanas archivadas.";
    }
  }

  function mensual(anio) {
    var caja = document.getElementById("impMesBloque");
    if (caja) caja.hidden = !anio;
    if (anio) {
      var val = [], hay = [];
      for (var m = 1; m <= 12; m++) {
        var k = anio + "-" + (m < 10 ? "0" + m : m);
        hay.push(!!M.cobertura_mes[k]);
        val.push(e.por_mes[k] || 0);
      }
      var mx = Math.max.apply(null, val.filter(function (v, i) {
        return hay[i]; }));
      if (!isFinite(mx) || mx <= 0) mx = 1;
      document.getElementById("impMes").innerHTML = val.map(function (v, i) {
        if (!hay[i]) {
          return '<div class="sb vacio" title="' + MESES_IMP[i] + " " + anio +
            ' · sin semanas descargadas"><i></i><b>' + MESES_IMP[i] +
            "</b></div>";
        }
        var h = Math.max(2, Math.round(100 * v / mx));
        return '<div class="sb' + (v > 0 ? '' : ' cero') + '" title="' +
          MESES_IMP[i] + " " + anio + " · " +
          (v > 0 ? usd(v) : "sin importaciones registradas") +
          '"><i style="height:' + (v > 0 ? h : 2) + '%"></i><b>' +
          MESES_IMP[i] + "</b></div>";
      }).join("");
      var conSem = hay.filter(Boolean).length;
      document.getElementById("impMesNota").textContent =
        conSem + " de 12 meses de " + anio + " tienen semanas descargadas. " +
        "Los meses sin barra no son cero: son meses cuyos manifiestos todavía " +
        "no se archivaron.";
    }
    barrasDeAnio(anio);
    sel.querySelectorAll(".chip").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.a === (anio || ""))); });
  }
  sel.onclick = function (ev) {
    var b = ev.target.closest("button");
    if (b && !b.disabled) mensual(b.dataset.a);
  };
  mensual(elegido);

  /* Anual. Hay dos maneras de que un año no tenga barra y significan cosas
     opuestas: que no se hayan descargado sus semanas —no sabemos— o que sí se
     hayan medido y esta empresa no haya importado —sabemos que no importó—.
     La primera es un hueco declarado; la segunda es un cero de verdad, y es la
     única circunstancia en que este módulo puede escribir US$ 0. */
  var va = M.anios_pedidos.map(function (a) {
    return e.por_anio[a] ? e.por_anio[a].fob : 0; });
  var medido = M.anios_pedidos.map(function (a) {
    return (M.cobertura_semanas[a] || 0) > 0; });
  /* Un año con cuatro semanas archivadas no es un año: es una muestra. Dibujar
     su barra al lado de uno completo invita a leer una caída donde solo hay
     archivo faltante, así que se marca y se dice cuántas semanas tiene. */
  var COMPLETO = 45;
  var parcial = M.anios_pedidos.map(function (a) {
    return (M.cobertura_semanas[a] || 0) < COMPLETO; });
  var mxa = Math.max.apply(null, va.filter(function (v, i) {
    return medido[i]; }));
  if (!isFinite(mxa) || mxa <= 0) mxa = 1;
  document.getElementById("impAnual").innerHTML =
    M.anios_pedidos.map(function (a, i) {
      if (!medido[i]) {
        return '<div class="sb vacio" title="' + a +
          ' · sin semanas descargadas: no hay información"><i></i><b>' +
          a + "</b></div>";
      }
      if (!e.por_anio[a]) {
        return '<div class="sb cero" title="' + a + " · " +
          M.cobertura_semanas[a] + ' semanas medidas, sin importaciones ' +
          'registradas de esta empresa"><i style="height:2%"></i><b>' +
          a + "</b></div>";
      }
      var h = Math.max(2, Math.round(100 * va[i] / mxa));
      return '<div class="sb' + (parcial[i] ? " parcial" : "") + '" title="' +
        a + " · " + usd(va[i]) + " · " + M.cobertura_semanas[a] +
        " de 52 semanas archivadas" +
        (parcial[i] ? " · año incompleto, no comparable" : "") +
        '"><i style="height:' + h + '%"></i><b>' + a +
        (parcial[i] ? "*" : "") + "</b></div>";
    }).join("");
  var sinSemanas = M.anios_pedidos.filter(function (a, i) {
    return !medido[i]; });
  var incompletos = M.anios_pedidos.filter(function (a, i) {
    return medido[i] && parcial[i]; });
  document.getElementById("impAnualNota").textContent =
    (incompletos.length
      ? "* " + incompletos.map(function (a) {
          return a + " (" + M.cobertura_semanas[a] + " de 52 semanas" +
            (a === M.anio_en_curso ? ", año en curso" : "") + ")"; }).join(", ") +
        ": barras sobre años incompletos, no comparables contra un año entero. "
      : "") +
    (sinSemanas.length
      ? sinSemanas.join(" y ") + " aparecen en hueco porque sus manifiestos " +
        "todavía no se descargan: no son años sin importaciones, son años sin " +
        "medir."
      : "");

}

/* --------------------------------------------------------------- perfil -- */
/* Una empresa por página. El directorio dice quién existe; el perfil dice qué
   compra afuera, a quién, cuándo y desde dónde, que es lo que hace falta para
   preparar una visita. Los perfiles viajan en cien archivos partidos por los
   dos últimos dígitos del RUC: uno por empresa serían 23 mil archivos, y uno
   solo obligaría a bajar 9.8 MB para ver una. */
var PERFIL = null;

function dibujarLocalizador(cv, p, GEO) {
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var W = cv.clientWidth, H = cv.clientHeight;
  if (!W || !H) return;
  cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  var g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  var css = getComputedStyle(document.documentElement);
  var tk = function (n) { return css.getPropertyValue(n).trim(); };

  /* El país entero de fondo y el departamento resaltado: sin el país, un
     contorno suelto no dice dónde queda; sin el departamento, el punto flota. */
  var bb = [1e9, 1e9, -1e9, -1e9];
  GEO.forEach(function (d) {
    d.r.forEach(function (a) {
      a.forEach(function (q) {
        if (q[0] < bb[0]) bb[0] = q[0]; if (q[1] < bb[1]) bb[1] = q[1];
        if (q[0] > bb[2]) bb[2] = q[0]; if (q[1] > bb[3]) bb[3] = q[1];
      });
    });
  });
  var pad = 8;
  var kx = Math.cos((bb[1] + bb[3]) / 2 * Math.PI / 180) || 1;
  var k = Math.min((W - 2 * pad) / ((bb[2] - bb[0]) * kx),
                   (H - 2 * pad) / (bb[3] - bb[1]));
  var ox = (W - (bb[2] - bb[0]) * kx * k) / 2;
  var oy = (H - (bb[3] - bb[1]) * k) / 2;
  var X = function (lo) { return ox + (lo - bb[0]) * kx * k; };
  var Y = function (la) { return H - oy - (la - bb[1]) * k; };

  var mio = (p.dep || "").normalize("NFD").replace(/[̀-ͯ]/g, "")
              .toUpperCase();
  GEO.forEach(function (d) {
    var suyo = d.k === mio;
    g.beginPath();
    d.r.forEach(function (a) {
      a.forEach(function (q, i) {
        var x = X(q[0]), y = Y(q[1]);
        if (i) g.lineTo(x, y); else g.moveTo(x, y);
      });
      g.closePath();
    });
    g.fillStyle = suyo ? tk("--forest2") || "#2C6B54" : tk("--surf2") || "#EEF1EA";
    g.globalAlpha = suyo ? .30 : 1;
    g.fill();
    g.globalAlpha = 1;
    g.strokeStyle = tk("--line") || "#D5DBD2";
    g.lineWidth = suyo ? 1.1 : .5;
    g.stroke();
  });

  if (p.lat === undefined) return;
  var x = X(p.lon), y = Y(p.lat);
  g.beginPath(); g.arc(x, y, 9, 0, 6.284);
  g.fillStyle = tk("--forest") || "#0F4C3F"; g.globalAlpha = .18; g.fill();
  g.globalAlpha = 1;
  g.beginPath(); g.arc(x, y, 3.4, 0, 6.284);
  g.fillStyle = tk("--forest") || "#0F4C3F"; g.fill();
  g.strokeStyle = "#fff"; g.lineWidth = 1.2; g.stroke();
}

/* Un despacho de 263 kg no es «0 t». Por debajo de la tonelada la unidad
   sigue siendo el kilo, y redondear a cero borra el dato. */
function peso(kg) {
  if (kg >= 1e6) return nf(Math.round(kg / 1000)) + " t";
  if (kg >= 1000) return nf(kg / 1000, 1) + " t";
  return nf(Math.round(kg)) + " kg";
}

/* ------------------------------------------------------- eje temporal ----
   Una sola función decide cómo se reparte el tiempo en TODOS los gráficos de
   serie del sitio, para que el eje no pueda contradecir al filtro de periodo.
   Antes cada gráfico reusaba el mismo arreglo de semanas, de modo que elegir
   «Mensual» cambiaba los montos pero seguía rotulando 15/06, 22/06, 06/07: el
   eje decía una granularidad y el número otra.

   La agregación es real —se suman los despachos de cada mes o de cada año— y
   no una extrapolación. El KPI de arriba sí extrapola, porque responde otra
   pregunta: «cuánto sería en un mes tipo». Aquí la barra de junio es lo que
   entró en junio.

   Los manifiestos de SUNAT son una ventana móvil de diez semanas, no un
   histórico: hoy cubren del 15 de junio al 27 de agosto de 2026. Los meses y
   los años fuera de esa ventana existen en el eje pero se dibujan como hueco
   declarado, nunca como cero. Un cero diría que no hubo importación; el hueco
   dice que no hay registro, que es lo cierto. */
var MES_COR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
var MES_LAR = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
               "Julio", "Agosto", "Setiembre", "Octubre", "Noviembre",
               "Diciembre"];
var ANIO_DESDE = 2021;          // el eje anual arranca aquí aunque no haya dato

function ejeTemporal(valores, fechas) {
  valores = valores || [];
  fechas = fechas || [];

  if (PERIODO === "mensual") {
    var vm = new Array(12).fill(0), hay = new Array(12).fill(false);
    fechas.forEach(function (f, i) {
      /* La semana se imputa al mes en que empieza. Una que cruza el cambio de
         mes queda entera del lado en que abre: partirla exigiría el detalle
         diario, que el manifiesto semanal no trae. */
      var m = parseInt(String(f).slice(5, 7), 10) - 1;
      if (m >= 0 && m < 12) { vm[m] += valores[i] || 0; hay[m] = true; }
    });
    return {
      etq: MES_COR, etqLarga: MES_LAR, val: vm, hay: hay,
      titulo: "Continuidad · FOB por mes",
      nota: "Suma medida de cada mes. Los meses sin barra están fuera de la " +
            "ventana de diez semanas que publica SUNAT: no hay registro, no " +
            "es que no haya habido importación."
    };
  }

  if (PERIODO === "anual") {
    var anios = fechas.map(function (f) { return parseInt(String(f).slice(0, 4), 10); })
                      .filter(function (a) { return a > 1900; });
    var hasta = anios.length ? Math.max.apply(null, anios) : ANIO_DESDE;
    var desde = Math.min(ANIO_DESDE, anios.length ? Math.min.apply(null, anios) : ANIO_DESDE);
    var etq = [], va = [], ha = [];
    for (var a = desde; a <= hasta; a++) {
      etq.push(String(a));
      va.push(0);
      ha.push(false);
    }
    fechas.forEach(function (f, i) {
      var k = parseInt(String(f).slice(0, 4), 10) - desde;
      if (k >= 0 && k < va.length) { va[k] += valores[i] || 0; ha[k] = true; }
    });
    return {
      etq: etq, etqLarga: etq, val: va, hay: ha,
      titulo: "Continuidad · FOB por año",
      nota: "Suma medida de cada año. SUNAT mantiene una ventana móvil de diez " +
            "semanas y no un histórico, así que solo el año en curso tiene " +
            "registro; los demás se muestran vacíos y no en cero."
    };
  }

  /* Medido: la semana tal cual, que es la unidad en que llega el manifiesto. */
  return {
    etq: fechas.map(function (f) {
      return String(f).slice(8) + "/" + String(f).slice(5, 7); }),
    etqLarga: fechas.map(function (f) { return "Semana del " + f; }),
    val: valores.slice(),
    hay: valores.map(function () { return true; }),
    titulo: "Continuidad · FOB por semana",
    nota: "Cada barra es una semana de manifiestos, tal como los publica SUNAT."
  };
}

/* Dibuja la serie con el eje que corresponda al periodo. Mantiene la misma
   marca visual de siempre: .serie > .sb > i + b. */
function pintarSerie(el, valores, fechas, elTitulo, elNota) {
  if (!el) return;
  var e = ejeTemporal(valores, fechas);
  var mx = Math.max.apply(null, e.val.filter(function (v, i) { return e.hay[i]; }));
  if (!isFinite(mx) || mx <= 0) mx = 1;
  el.innerHTML = e.val.map(function (v, i) {
    if (!e.hay[i]) {
      return '<div class="sb vacio" title="' + esc(e.etqLarga[i]) +
        ' · sin registro"><i></i><b>' + esc(e.etq[i]) + "</b></div>";
    }
    var h = Math.max(2, Math.round(100 * v / mx));
    return '<div class="sb" title="' + esc(e.etqLarga[i]) + " · " + usd(v) +
      '"><i style="height:' + h + '%"></i><b>' + esc(e.etq[i]) + "</b></div>";
  }).join("");
  if (elTitulo) elTitulo.textContent = e.titulo;
  if (elNota) elNota.textContent = e.nota;
}

function vistaEmpresa(ruc) {
  var caja = document.getElementById("empPerfil");
  caja.innerHTML = '<div class="load">Cargando el perfil…</div>';
  var grupo = ruc.slice(-2);
  Promise.all([cargar("perfil/" + grupo), cargar("perfil_idx"),
               cargar("geo_min")]).then(function (r) {
    var P = r[0][ruc], IDX = r[1], GEO = r[2];
    if (!P) {
      caja.innerHTML = '<div class="card"><div class="b"><p>No hay perfil ' +
        'para el RUC <span class="mono">' + esc(ruc) + '</span>. El directorio ' +
        'cubre el padrón agrícola y a quien registra comercio exterior.</p>' +
        '<p><a class="vermapa" href="#empresas">Volver al directorio</a></p>' +
        "</div></div>";
      return;
    }
    PERFIL = P;
    var SEM = IDX.semanas;
    var I = P.imp, E = P.exp;

    var kpis = [];
    if (I) {
      kpis.push([pFob(I.fob, SEM), "importación " + pSuf(SEM),
                 usd(I.fob) + " medidos en " + SEM + " semanas"]);
      kpis.push([peso(I.kg), "peso importado",
                 I.partidas + " partidas · " + I.lineas + " despachos"]);
      kpis.push([I.semanas + " de " + IDX.semanas, "semanas con despacho",
                 I.semanas >= IDX.semanas - 1 ? "flujo continuo"
                   : (I.semanas <= 2 ? "compra puntual" : "flujo intermitente")]);
    }
    if (E) {
      kpis.push([pFob(E.fob, SEM), "agroexportación " + pSuf(SEM),
                 usd(E.fob) + " medidos en " + SEM + " semanas"]);
      if (E.kg) {
        kpis.push([peso(E.kg), "peso exportado",
                   (E.partidas || 0) + " partidas · " +
                   (E.lineas || 0) + " embarques"]);
      }
      kpis.push([nf(E.destinos) + (E.destinos === 1 ? " país" : " países"),
                 "destinos", E.semanas
                   ? E.semanas + " de " + SEM + " semanas con embarque" : ""]);
    }
    if (!kpis.length) {
      kpis.push([esc(P.clase || "—"), "clase declarada",
                 "sin comercio exterior registrado"]);
      kpis.push([esc(P.estado || "—"), "estado en el padrón",
                 esc(P.condicion || "")]);
    }

    var loc = [P.dist, P.prov, P.dep].filter(Boolean).join(" · ");
    var pares = [];
    if (P.dir) pares.push(["Domicilio fiscal", esc(P.dir)]);
    if (loc) pares.push(["Ubicación", esc(loc)]);
    if (P.estado) pares.push(["Estado", esc(P.estado) +
      (P.condicion ? " · " + esc(P.condicion) : "")]);
    if (P.ter && P.ter !== "Fuera de territorio")
      pares.push(["Territorio de venta",
        enlaceMapa(esc(P.ter), "ter=" + P.rank)]);
    else if (P.lat !== undefined)
      pares.push(["Territorio de venta", "fuera de todo territorio"]);
    if (P.hub) pares.push(["Centro que la sirve", esc(P.hub) +
      (P.h_hub !== null && P.h_hub !== undefined
        ? " · " + nf(P.h_hub, 1) + " h" : "")]);
    if (P.rubro) pares.push(["Rubro de importación", esc(P.rubro)]);

    caja.innerHTML =
      '<div class="card"><div class="h">' +
        "<h3>" + esc(P.n || ruc) + "</h3>" +
        '<span class="eyebrow"><span class="mono">' + esc(ruc) + "</span>" +
        (P.clase ? " · " + esc(P.clase) : "") + "</span></div>" +
        '<div class="b"><p class="sub"><a class="vermapa" href="#empresas">' +
        "← Volver al directorio</a></p></div>" +
      "</div>" +
      '<div class="kpis" style="margin-top:14px">' +
        kpis.map(function (k) {
          return "<div><span class='v'>" + k[0] + "</span><span class='l'>" +
            k[1] + "</span><span class='s'>" + k[2] + "</span></div>";
        }).join("") +
      "</div>" +

      '<div class="grid2" style="margin-top:16px">' +
        '<div class="card"><div class="h"><h3>Dónde está</h3>' +
          '<span class="eyebrow">Domicilio fiscal</span></div>' +
          '<div class="b"><canvas id="empMapa" class="locmap"></canvas>' +
          '<dl class="pares">' + pares.map(function (x) {
            return "<dt>" + x[0] + "</dt><dd>" + x[1] + "</dd>"; }).join("") +
          "</dl>" +
          '<p class="sub">El domicilio fiscal no es el lugar de cultivo: un ' +
          'agroexportador con fundo en La Libertad suele estar inscrito en ' +
          'Lima. Sirve para saber a quién visitar cuando se está en la zona.</p>' +
          "</div></div>" +
        '<div class="card"><div class="h"><h3>Qué importa</h3>' +
          '<span class="eyebrow">FOB ' + pSuf(SEM) + "</span></div>" +
          '<div class="b">' + (I
            ? '<div class="barras compact" id="empCats"></div>' +
              '<div class="eyebrow" style="margin-top:12px" id="empSerieTit">' +
              "Continuidad</div>" +
              '<div class="serie" id="empSerie"></div>' +
              '<p class="sub" id="empSerieNota"></p>'
            : "<p>Sin importación registrada en la ventana de aduanas.</p>") +
          "</div></div>" +
      "</div>" +

      (I ? '<div class="grid2" style="margin-top:16px">' +
        '<div class="card"><div class="h"><h3>De dónde viene</h3>' +
          '<span class="eyebrow">País de origen</span></div>' +
          '<div class="b"><div class="barras compact" id="empPaises"></div></div></div>' +
        '<div class="card"><div class="h"><h3>Qué producto</h3>' +
          '<span class="eyebrow">Glosa de la partida</span></div>' +
          '<div class="b"><div class="barras compact" id="empGlosas"></div></div></div>' +
      "</div>" +
      '<div class="card" style="margin-top:16px"><div class="h">' +
        "<h3>Los mayores despachos, uno por uno</h3>" +
        '<span class="eyebrow">Descripción comercial del declarante</span></div>' +
        '<div class="tw"><table id="tEmpDesc"></table></div>' +
        '<div class="b"><p class="sub">La descripción la escribe el propio ' +
        'declarante en el manifiesto: es el detalle más fino que existe de qué ' +
        'compró esta empresa, marca y modelo incluidos cuando los declara.</p>' +
        "</div></div>" : "") +

      (E && E.partidas_top && E.partidas_top.length
        ? '<div class="grid2" style="margin-top:16px">' +
          '<div class="card"><div class="h"><h3>Qué exporta</h3>' +
            '<span class="eyebrow">Partida arancelaria</span></div>' +
            '<div class="b"><div class="barras compact" id="empExpP"></div></div></div>' +
          '<div class="card"><div class="h"><h3>Hacia dónde</h3>' +
            '<span class="eyebrow">País de destino</span></div>' +
            '<div class="b"><div class="barras compact" id="empExpD"></div></div></div>' +
          "</div>" : "") +

      '<div id="empImportHist"></div>' +
      '<p class="sub" style="margin-top:14px">Microdatos de manifiestos de ' +
      'SUNAT bajo la Ley 27806, ' + IDX.semanas + ' semanas de junio a agosto ' +
      'de 2026. El mensual y el anual extrapolan esa ventana sin corregir ' +
      'estacionalidad; «medido» es la única cifra dura. Identidad y ' +
      'domicilio, del padrón reducido del RUC.</p>';

    function barrasDe(id, filas) {
      var el = document.getElementById(id);
      if (el) barras(el, filas.map(function (x) {
        return { n: x.n, v: x.fob, t: pFob(x.fob, SEM) }; }));
    }
    if (I) {
      barrasDe("empCats", I.cats);
      barrasDe("empPaises", I.paises);
      barrasDe("empGlosas", I.glosas);
      pintarSerie(document.getElementById("empSerie"), I.serie, IDX.sems,
                  document.getElementById("empSerieTit"),
                  document.getElementById("empSerieNota"));
      tabla(document.getElementById("tEmpDesc"), [
        { k: "d", t: "Descripción declarada", l: 1, f: function (r) {
            return esc(r.d); } },
        { k: "p", t: "Partida", l: 1, f: function (r) {
            return '<span class="mono">' + esc(r.p) + "</span>"; } },
        { k: "o", t: "Origen", l: 1, f: function (r) { return esc(r.o); } },
        { k: "kg", t: "Kilos", f: function (r) { return nf(Math.round(r.kg)); } },
        { k: "fob", t: "FOB del despacho", f: function (r) {
            return usd(r.fob); } }
      ], I.desc, { sort: "fob" });
    }
    if (E && E.partidas_top && E.partidas_top.length) {
      barrasDe("empExpP", E.partidas_top);
      barrasDe("empExpD", E.paises);
    }
    /* El perfil ya tiene su localizador chico; el mapa completo va debajo,
       centrado en la empresa cuando se sabe donde esta. */
    mapaEn("mapPerfil", P.lat !== undefined
      ? "#pt=" + P.lat + "," + P.lon + ",0.6"
      : (P.rank > 0 ? "#ter=" + P.rank : "#peru"));

    pintarPerfilExport(ruc);

    /* La capa historica de importaciones. Se pide solo aqui: son 568 KB que
       quien mira una ficha de productor no tiene por que descargar. */
    impDatos().then(function (r) {
      var M = r[0], IMP = r[1];
      var slot = document.getElementById("empImportHist");
      if (!slot) return;
      slot.innerHTML = bloqueImportaciones(ruc, M, IMP);
      pintarImportaciones(ruc, M, IMP);
    }).catch(function () {});

    var cv = document.getElementById("empMapa");
    if (cv) {
      dibujarLocalizador(cv, P, GEO);
      if (!window.__locObs) {
        window.__locObs = true;
        window.addEventListener("resize", function () {
          var c = document.getElementById("empMapa");
          if (c && PERFIL) cargar("geo_min").then(function (G) {
            dibujarLocalizador(c, PERFIL, G); });
        });
      }
    }
  }).catch(fallo);
}

/* -------------------------------------------------------- estacionalidad -*/
function vistaEstacionalidad() {
  cargar("estacionalidad").then(function (D) {
    var mx = 0;
    D.regiones.forEach(function (r) {
      r.m.forEach(function (v) { if (v > mx) mx = v; }); });
    var RAMPA = ["#F1F4EE", "#CBD9C4", "#8FB585", "#4C8A6B", "#125A57", "#0B3B4A"];
    function col(v) {
      var t = Math.min(v / mx, 1);
      return RAMPA[Math.min(RAMPA.length - 1, Math.floor(t * RAMPA.length))];
    }
    var html = '<table class="cal"><thead><tr><th class="reg">Región</th>' +
      D.meses.map(function (m) { return "<th>" + m + "</th>"; }).join("") +
      '<th>Pico</th><th>4 meses</th></tr></thead><tbody>' +
      D.regiones.map(function (r) {
        return '<tr><td class="reg">' + esc(r.n) + "</td>" +
          r.m.map(function (v, i) {
            var p = D.meses[i] === r.pico;
            return '<td><span class="cel' + (p ? " pico" : "") +
              '" style="background:' + col(v) + '" title="' +
              D.meses[i] + ": " + v.toFixed(1) + '%"></span></td>';
          }).join("") +
          '<td class="mono">' + r.pico + "</td>" +
          '<td class="mono">' + nf(r.top4, 0) + "%</td></tr>";
      }).join("") + "</tbody></table>";

    document.getElementById("calWrap").innerHTML = html +
      '<p class="sub">Cada fila suma 100%: el color indica qué porción del año ' +
      'de esa región cae en cada mes, y el recuadro marca su pico. La última ' +
      'columna mide concentración —33% sería un año perfectamente parejo—.</p>' +
      '<div class="note"><span class="h">Cómo se usa</span>Una región por ' +
      'encima del 65% en cuatro meses no sostiene una oficina permanente: se ' +
      'atiende con brigada de campaña. Por debajo del 45%, la demanda alcanza ' +
      'para operar todo el año.</div>';
  }).catch(fallo);
}


/* --------------------------------------------------------- la red elegida -- */
/* Los seis que elige el algoritmo con vara de dos horas, más Huamachuco, con
   promesa de cuatro. El séptimo no salió de la optimización sino de mirar el
   caso de Sánchez Carrión y Pataz: el mayor territorio del país no lo sirve
   nadie a dos horas —el mejor centro posible alcanza el 22% de su mercado—,
   y con vara de cuatro Huamachuco pasa de ser el candidato catorce a ser el
   primero del país. */
function pintarRed() {
  var caja = document.getElementById("redElegida");
  if (!caja) return;
  cargar("red").then(function (R) {
    var dec = R.centros.filter(function (c) { return c.por === "decision"; });
    /* La promesa dejó de ser un número: son cuatro horas en costa y seis en
       sierra y selva. Mostrar solo una haría que media red pareciera
       incumplir, que es justamente lo que la diferenciación evita. */
    var pr = R.promesa_h;
    var horas = Object.keys(pr).map(function (k) { return pr[k]; })
      .filter(function (v, i, a) { return a.indexOf(v) === i; })
      .sort(function (a, b) { return a - b; });
    var etiqueta = horas.map(function (h) {
      var reg = Object.keys(pr).filter(function (k) { return pr[k] === h; })
        .map(function (k) { return k.toLowerCase(); });
      /* «sierra y selva alta y selva baja» se lee mal; la coma hasta el
         penúltimo es lo que hace legible una enumeración de tres. */
      var lista = reg.length < 2 ? reg[0]
        : reg.slice(0, -1).join(", ") + " y " + reg[reg.length - 1];
      return nf(h) + " h en " + lista;
    }).join(" · ");

    caja.innerHTML =
      '<div class="h"><h3>La red elegida</h3><span class="eyebrow">' +
      R.centros.length + " centros · promesa de " + esc(etiqueta) +
      "</span></div><div class='b'>" +
      '<div class="kpis">' +
      kpi(nf(R.centros.length), "centros", dec.length +
          (dec.length === 1 ? " por decisión" : " por decisión")) +
      kpi(pct(R.sam_cubierto_promesa_pct, 1), "del mercado en promesa",
          esc(etiqueta)) +
      kpi(pct(R.sam_cubierto_2h_pct, 1), "a menos de dos horas",
          "la vara anterior") +
      "</div>" +
      '<div class="tw" style="margin-top:14px"><table id="tRed"></table></div>' +
      '<p class="sub">' + esc(R.motivo) + " La cobertura no la decide el " +
      "número de centros sino la vara: los mismos " + R.centros.length +
      " cubren " + pct(R.sam_cubierto_promesa_pct, 1) +
      " con la promesa vigente y " + pct(R.sam_cubierto_2h_pct, 1) +
      " si se exigieran dos horas en todas partes." +
      (R.por_region || []).map(function (x) {
        return " " + esc(x.region.toLowerCase()) + ": " + pct(x.pct, 0) +
          " de sus " + usd(x.sam_mm * 1e6) + " dentro de " + nf(x.promesa_h) +
          " h.";
      }).join("") + "</p></div>";

    tabla(document.getElementById("tRed"), [
      { k: "hub", t: "Centro", l: 1, f: function (r) {
          return "<b>" + esc(r.hub) + "</b><span class='sub2'>" +
            esc(r.provincia) + " · " + esc(r.region) + "</span>"; } },
      { k: "por", t: "Cómo entró", l: 1, f: function (r) {
          return "<span class='tag'>" + (r.por === "decision"
            ? "por decisión" : "por cobertura") + "</span>"; } },
    ], R.centros, { sort: "hub", asc: true });
  }).catch(function () { caja.innerHTML = ""; });
}


/* ------------------------------------------------------------- el canal -- */
/* La red de centros dice dónde poner inventario. No dice quién le vende al
   agricultor: en el mayor territorio del país hay 9,114 clientes y 133
   empresas formales, así que el almacén —aunque esté en Huamachuco— atiende
   al 1.5% de ese mercado.

   Esta capa no inventa la red: el canal ya existe. Lo que hace falta es saber
   a cuántos alcanza, cuáles quedan fuera y dónde no hay a quién captar. Las
   tres cifras son distintas y confundirlas cambia la conclusión, así que se
   muestran las tres. */
function pintarCanal() {
  var caja = document.getElementById("redCanal");
  if (!caja) return;
  cargar("canal").then(function (C) {
    var cand = C.candidatos;
    var V = C.viabilidad;
    var mal = C.territorios.slice().sort(function (a, b) {
      return a.pct - b.pct; }).filter(function (t) { return t.clientes > 500; });

    caja.innerHTML =
      '<div class="h"><h3>La red de canal</h3><span class="eyebrow">' +
      "quién le vende al que no es empresa · radio de " + C.radio_base_min +
      " minutos</span></div><div class='b'>" +
      '<div class="kpis">' +
      kpi(pct(C.con_canal.pct, 1), "clientes con canal cerca",
          nf(C.con_canal.clientes) + " de " + nf(C.clientes)) +
      kpi(pct(C.sin_candidato.pct, 1), "sin ningún punto a " +
          C.radio_base_min + " min",
          nf(C.sin_candidato.clientes) + " clientes: ahí hay que abrir") +
      kpi(nf(cand.canal + cand.comercio), "puntos que ya existen",
          nf(cand.canal) + " del padrón · " + nf(cand.comercio) + " de OSM") +
      /* La cadena vale lo que valga su tramo más débil. Una tienda con
         clientes al lado pero a nueve horas de su almacén no está servida, y
         contarla entera es el error que este número evita. */
      kpi(pct(C.cadena_completa.pct, 1), "con la cadena completa",
          "tienda cerca Y su centro dentro de la promesa") +
      "</div>" +
      '<div class="grid2" style="margin-top:16px">' +
      '<div class="sub-card"><div class="eyebrow">Orden de captación: los ' +
      'doce que más clientes suman</div>' +
      '<div class="tw"><table id="tCanal"></table></div></div>' +
      '<div class="sub-card"><div class="eyebrow">Territorios sin canal</div>' +
      '<div class="tw"><table id="tCanalTer"></table></div></div></div>' +
      '<div class="sub-card" style="margin-top:16px">' +
      '<div class="eyebrow">Quién resurte a quién · del centro a la tienda' +
      "</div><div class='tw'><table id='tCanalHub'></table></div></div>" +
      /* El canal medido en clientes no alcanza para proponer nada: nadie toma
         una línea porque tenga gente cerca. Esto lo pone en plata, con la
         economía unitaria que la propia empresa midió sobre su libro de
         ventas, y con el reparto hecho —el mercado de cada punto es el que
         nadie más tiene más cerca, o se contaría a la misma gente dos veces—. */
      '<div class="sub-card" style="margin-top:16px">' +
      '<div class="eyebrow">Si el punto es negocio · mercado exclusivo y ' +
      "margen en el escenario base</div>" +
      '<div class="kpis" style="margin-top:10px">' +
      kpi(nf(V.puntos_con_mercado), "puntos con mercado propio",
          "de " + nf(V.puntos_que_venden) + "; el resto cae dentro del radio " +
          "de otro más cercano") +
      kpi(usd(V.sam_exclusivo_mm * 1e6), "mercado repartido entre ellos",
          "sin contar a nadie dos veces") +
      kpi(usd(V.escenarios[1].margen_mayor), "margen del mayor punto",
          "al año, escenario base") +
      "</div>" +
      '<div class="tw" style="margin-top:12px"><table id="tCanalViab"></table>' +
      "</div>" +
      '<p class="sub">' + esc(V.salvedad) + ". Por eso el piso de viabilidad " +
      "no lo fija esta pantalla: la tabla muestra cuántos puntos quedan sobre " +
      "cada vara para que la elija quien decide. Con la penetración base, " +
      "ningún punto del país pasa de " +
      usd(V.escenarios[1].margen_mayor) + " al año.</p></div>" +
      '<p class="sub">' +
      "Dos límites del dato, antes de leer ninguna cifra. <b>La ubicación del " +
      "padrón es el distrito, no la esquina</b>: SUNAT publica el domicilio " +
      "fiscal y aquí se lleva al centroide agrícola del distrito, lo que " +
      "alcanza para un radio de 45 minutos y no para decidir un local. Y " +
      "<b>que OpenStreetMap no mapee una tienda no significa que no exista</b>: " +
      "su cobertura en la sierra rural es pobre, así que el " +
      pct(C.sin_candidato.pct, 1) + " sin punto cerca es un techo —cuánto no " +
      "se puede demostrar que esté cubierto— y no una medición de abandono. " +
      "La capa del padrón existe justamente para acotar eso.</p></div>";

    tabla(document.getElementById("tCanal"), [
      { k: "k", t: "#", f: function (r) { return r.k; } },
      { k: "nombre", t: "Punto", l: 1, f: function (r) {
          return "<b>" + esc(r.nombre) + "</b><span class='sub2'>" +
            esc(r.dep) + "</span>"; } },
      { k: "clase", t: "Qué es", l: 1, f: function (r) {
          return "<span class='tag'>" +
            (r.clase === "canal" ? "padrón" :
             r.clase === "comercio" ? "comercio" : "poblado") + "</span>"; } },
      { k: "clientes_nuevos", t: "Clientes nuevos", f: function (r) {
          return nf(r.clientes_nuevos); } },
    ], C.apertura.slice(0, 12), { sort: "k", asc: true });

    tabla(document.getElementById("tCanalTer"), [
      { k: "provincias", t: "Territorio", l: 1, f: function (r) {
          return "<b>" + esc(r.provincias) + "</b><span class='sub2'>" +
            esc(r.dep) + "</span>"; } },
      { k: "clientes", t: "Clientes", f: function (r) {
          return nf(r.clientes); } },
      { k: "pct", t: "Con canal", f: function (r) {
          return "<span class='delta " + (r.pct < 25 ? "peor" : "") + "'>" +
            pct(r.pct, 0) + "</span>"; } },
    ], mal.slice(0, 8), { sort: "pct", asc: true });

    tabla(document.getElementById("tCanalHub"), [
      { k: "hub", t: "Centro", l: 1, f: function (r) {
          return "<b>" + esc(r.hub) + "</b>"; } },
      { k: "puntos", t: "Puntos que resurte", f: function (r) {
          return nf(r.puntos) + "<span class='sub2'>" + nf(r.del_padron) +
            " del padrón</span>"; } },
      { k: "pct_en_promesa", t: "Dentro de la promesa", f: function (r) {
          return "<span class='delta " + (r.pct_en_promesa < 50 ? "peor" : "") +
            "'>" + pct(r.pct_en_promesa, 0) + "</span>"; } },
      { k: "horas_mediana", t: "Horas, mediana", f: function (r) {
          return nf(r.horas_mediana, 1) + " h"; } },
      { k: "clientes", t: "Clientes detrás", f: function (r) {
          return nf(r.clientes); } },
    ], C.reparto, { sort: "puntos" });

    tabla(document.getElementById("tCanalViab"), [
      /* Sin abreviar: `usd` redondea y un umbral de 2,500 salía como «US$ 3
         mil», que en una tabla de varas es decir otra vara. */
      { k: "margen_min", t: "Margen al año, mínimo", l: 1, f: function (r) {
          return "<b>US$ " + nf(r.margen_min) + "</b>"; } },
      { k: "puntos", t: "Puntos que lo superan", f: function (r) {
          return nf(r.puntos); } },
      { k: "clientes", t: "Clientes detrás", f: function (r) {
          return nf(r.clientes); } },
    ], V.curva, { sort: "margen_min", asc: true });
  }).catch(function () { caja.innerHTML = ""; });
}

/* ------------------------------------------------------------ expansión -- */
function vistaExpansion(D) {
  var umbral = 2;
  var chips = document.getElementById("fUmbral");
  chips.innerHTML = [2, 4, 6].map(function (u) {
    return '<button class="chip" data-u="' + u + '" aria-pressed="' +
      (u === 2) + '">Radio de ' + u + " horas</button>";
  }).join("");

  function pintar() {
    var L = D.hubs.filter(function (h) { return h.u === umbral; });
    var seis = L.filter(function (h) { return h.k <= 6; });
    var p6 = seis.length ? seis[seis.length - 1].pct : 0;
    document.getElementById("hubMeta").textContent =
      "6 centros cubren " + pct(p6, 0) + " del mercado";

    tabla(document.getElementById("tHubs"), [
      { k: "k", t: "Orden", f: function (r) { return r.k; } },
      { k: "hub", t: "Ciudad", l: true, f: function (r) { return esc(r.hub); } },
      { k: "region", t: "Región", l: true, f: function (r) { return esc(r.region); } },
      { k: "pct", t: "% mercado cubierto", f: function (r) {
          return pct(r.pct) + '<span class="mini"><i style="width:' +
                 r.pct.toFixed(0) + '%"></i></span>'; } },
      { k: "marg", t: "Aporte marginal", f: function (r) {
          return "+" + pct(r.marg); } }
    ], L, { sort: "k", asc: true });

    var l2 = D.hubs.filter(function (h) { return h.u === 2 && h.k === 6; })[0];
    var l6 = D.hubs.filter(function (h) { return h.u === 6 && h.k === 6; })[0];
    document.getElementById("radioNota").innerHTML =
      "<p>Con <b>seis centros</b>, la cobertura del mercado cambia por completo " +
      "según el radio que se acepte:</p>" +
      '<div class="funnel">' + [[2, l2], [6, l6]].map(function (x) {
        return '<div class="fstep"><span class="n">Radio de ' + x[0] +
          ' horas</span><span class="v">' + pct(x[1].pct, 0) + "</span>" +
          '<span class="ftrack"><i style="width:' + x[1].pct.toFixed(0) +
          '%"></i></span></div>';
      }).join("") + "</div>" +
      '<div class="note brass"><span class="h">La conclusión</span>' +
      "Un radio de reparto de dos horas no es viable a escala nacional: la " +
      "agricultura peruana está demasiado dispersa y harían falta decenas de " +
      "almacenes para cubrir poco. Lo que decide la cobertura es el <b>radio de " +
      "operación</b>, no el número de centros. O red de canal con " +
      "distribuidores locales, o pocos centros con rutas largas y entrega " +
      "programada.</div>";

    /* La curva de arriba es lo que el algoritmo encuentra; esto es lo que se
       decidió. Separarlas importa: la promesa de servicio es una decisión
       comercial y con otra vara el ranking de ciudades cambia entero. */
    pintarRed();
    pintarCanal();

    tabla(document.getElementById("tSom"), [
      { k: "e", t: "Escenario", l: true, f: function (r) { return esc(r.e); } },
      { k: "pen", t: "Penetración", f: function (r) {
          return pct(100 * r.pen); } },
      { k: "cli", t: "Clientes activos", f: function (r) { return nf(r.cli); } },
      { k: "ventas", t: "Ventas anuales", f: function (r) { return usd(r.ventas); } },
      { k: "margen", t: "Margen bruto", f: function (r) { return usd(r.margen); } }
    ], D.som, { sort: "pen", asc: true });
  }

  chips.querySelectorAll(".chip").forEach(function (b) {
    b.onclick = function () {
      umbral = +b.dataset.u;
      chips.querySelectorAll(".chip").forEach(function (o) {
        o.setAttribute("aria-pressed", String(o === b)); });
      pintar();
    };
  });
  pintar();
}

/* ----------------------------------------------------------------- tema -- */
/* Tres estados. "auto" borra el atributo y deja que mande el sistema; los
   otros dos lo fijan. El gráfico de la curva se dibuja en canvas leyendo
   variables CSS, así que hay que repintarlo cuando el tema cambia: el CSS solo
   se ocupa del DOM. */
function aplicarTema(t) {
  if (t === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  try { localStorage.setItem("tema", t); } catch (e) {}
  document.querySelectorAll(".tema button").forEach(function (b) {
    b.setAttribute("aria-pressed", String(b.dataset.tema === t));
  });
  if (cache.resumen) {
    cache.resumen.then(function (D) { dibujarCurva(D.curva); });
  }
}

(function initTema() {
  var guardado = "auto";
  try { guardado = localStorage.getItem("tema") || "auto"; } catch (e) {}
  document.querySelectorAll(".tema button").forEach(function (b) {
    b.onclick = function () { aplicarTema(b.dataset.tema); };
  });
  aplicarTema(guardado);
  // Si el usuario dejó "auto", seguir los cambios del sistema en vivo.
  var mq = window.matchMedia("(prefers-color-scheme: dark)");
  var cb = function () {
    if (!document.documentElement.dataset.theme && cache.resumen) {
      cache.resumen.then(function (D) { dibujarCurva(D.curva); });
    }
  };
  if (mq.addEventListener) mq.addEventListener("change", cb);
  else if (mq.addListener) mq.addListener(cb);
})();


/* ------------------------------------------------------------- comunes -- */
/* Lista de barras horizontales. Se usa para composiciones —familias de
   insumo, países— donde lo que importa es la proporción entre filas y no el
   valor exacto, que igual va al lado. */
function barras(el, filas, opts) {
  opts = opts || {};
  var mx = Math.max.apply(null, filas.map(function (r) { return r.v; })) || 1;
  var tot = filas.reduce(function (a, r) { return a + r.v; }, 0) || 1;
  el.innerHTML = filas.map(function (r) {
    // Si la fila trae su propio porcentaje se respeta: cuando la lista es un
    // recorte —los 12 cultivos mayores de un departamento, por ejemplo—, el
    // reparto sobre lo mostrado no es el reparto real y contradice la tabla.
    var p = r.p === undefined ? 100 * r.v / tot : r.p;
    return '<div class="bar">' +
      '<span class="bn">' + esc(r.n) + "</span>" +
      '<span class="bv mono">' + r.t + "</span>" +
      '<span class="bt"><i style="width:' + (100 * r.v / mx).toFixed(1) +
      '%"></i></span>' +
      '<span class="bp mono">' + pct(p, 1) + "</span>" +
      "</div>";
  }).join("");
}

/* Códigos ISO del manifiesto de aduanas. Solo los que aparecen arriba: el
   resto se muestra con su código, que es preferible a inventar un nombre. */
var PAIS = {
  "AE": "Emiratos Árabes",
  "AG": "Antigua y Barbuda",
  "AO": "Angola",
  "AR": "Argentina",
  "AT": "Austria",
  "AU": "Australia",
  "AW": "Aruba",
  "BB": "Barbados",
  "BD": "Bangladés",
  "BE": "Bélgica",
  "BG": "Bulgaria",
  "BH": "Baréin",
  "BJ": "Benín",
  "BM": "Bermudas",
  "BO": "Bolivia",
  "BQ": "Caribe Neerlandés",
  "BR": "Brasil",
  "BS": "Bahamas",
  "BZ": "Belice",
  "CA": "Canadá",
  "CG": "Congo",
  "CH": "Suiza",
  "CI": "Costa de Marfil",
  "CL": "Chile",
  "CN": "China",
  "CO": "Colombia",
  "CR": "Costa Rica",
  "CU": "Cuba",
  "CV": "Cabo Verde",
  "CW": "Curazao",
  "CY": "Chipre",
  "CZ": "Chequia",
  "DE": "Alemania",
  "DK": "Dinamarca",
  "DM": "Dominica",
  "DO": "Rep. Dominicana",
  "DZ": "Argelia",
  "EC": "Ecuador",
  "EE": "Estonia",
  "EG": "Egipto",
  "ES": "España",
  "FI": "Finlandia",
  "FO": "Islas Feroe",
  "FR": "Francia",
  "GB": "Reino Unido",
  "GD": "Granada",
  "GE": "Georgia",
  "GF": "Guayana Francesa",
  "GH": "Ghana",
  "GM": "Gambia",
  "GN": "Guinea",
  "GP": "Guadalupe",
  "GR": "Grecia",
  "GT": "Guatemala",
  "GY": "Guyana",
  "HK": "Hong Kong",
  "HN": "Honduras",
  "HR": "Croacia",
  "HT": "Haití",
  "HU": "Hungría",
  "ID": "Indonesia",
  "IE": "Irlanda",
  "IL": "Israel",
  "IN": "India",
  "IR": "Irán",
  "IS": "Islandia",
  "IT": "Italia",
  "JM": "Jamaica",
  "JO": "Jordania",
  "JP": "Japón",
  "KE": "Kenia",
  "KG": "Kirguistán",
  "KH": "Camboya",
  "KN": "San Cristóbal y Nieves",
  "KP": "Corea del Norte",
  "KR": "Corea del Sur",
  "KW": "Kuwait",
  "KY": "Islas Caimán",
  "KZ": "Kazajistán",
  "LB": "Líbano",
  "LC": "Santa Lucía",
  "LK": "Sri Lanka",
  "LR": "Liberia",
  "LT": "Lituania",
  "LU": "Luxemburgo",
  "LV": "Letonia",
  "MA": "Marruecos",
  "MG": "Madagascar",
  "ML": "Malí",
  "MN": "Mongolia",
  "MQ": "Martinica",
  "MR": "Mauritania",
  "MU": "Mauricio",
  "MV": "Maldivas",
  "MX": "México",
  "MY": "Malasia",
  "MZ": "Mozambique",
  "NC": "Nueva Caledonia",
  "NG": "Nigeria",
  "NI": "Nicaragua",
  "NL": "Países Bajos",
  "NO": "Noruega",
  "NP": "Nepal",
  "NZ": "Nueva Zelanda",
  "OM": "Omán",
  "PA": "Panamá",
  "PE": "Perú",
  "PG": "Papúa Nueva Guinea",
  "PH": "Filipinas",
  "PK": "Pakistán",
  "PL": "Polonia",
  "PR": "Puerto Rico",
  "PT": "Portugal",
  "PY": "Paraguay",
  "QA": "Catar",
  "RO": "Rumanía",
  "RS": "Serbia",
  "RU": "Rusia",
  "SA": "Arabia Saudita",
  "SE": "Suecia",
  "SG": "Singapur",
  "SI": "Eslovenia",
  "SK": "Eslovaquia",
  "SL": "Sierra Leona",
  "SN": "Senegal",
  "SR": "Surinam",
  "SV": "El Salvador",
  "SX": "Sint Maarten",
  "SY": "Siria",
  "TG": "Togo",
  "TH": "Tailandia",
  "TN": "Túnez",
  "TR": "Turquía",
  "TT": "Trinidad y Tobago",
  "TW": "Taiwán",
  "TZ": "Tanzania",
  "UA": "Ucrania",
  "UG": "Uganda",
  "US": "Estados Unidos",
  "UY": "Uruguay",
  "UZ": "Uzbekistán",
  "VC": "San Vicente",
  "VE": "Venezuela",
  "VG": "Islas Vírgenes Br.",
  "VI": "Islas Vírgenes EE.UU.",
  "VN": "Vietnam",
  "ZA": "Sudáfrica",
  "ZM": "Zambia",
  "ZW": "Zimbabue"
};
function pais(c) { return PAIS[c] || c; }

/* -------------------------------------------------------- departamentos -- */
function vistaDepartamentos() {
  cargar("departamentos").then(function (D) {
    var SEM_DEP = D.semanas || 10;
    var sel = document.getElementById("fDepto");
    var orden = "rank";
    var actual = D.deps[0].k;

    document.getElementById("depMeta").textContent =
      D.deps.length + " departamentos";

    document.getElementById("fDeptoOrden").innerHTML =
      [["rank", "Por atractivo"], ["sam", "Por mercado"],
       ["n", "Alfabético"]].map(function (o) {
        return '<button class="chip" data-o="' + o[0] + '"' +
          (o[0] === orden ? ' aria-pressed="true"' : "") + ">" + o[1] +
          "</button>";
      }).join("");

    function llenar() {
      var d = D.deps.slice().sort(function (a, b) {
        if (orden === "n") return a.n.localeCompare(b.n, "es");
        if (orden === "sam") return b.sam - a.sam;
        return a.rank - b.rank;
      });
      sel.innerHTML = d.map(function (r) {
        return '<option value="' + r.k + '"' +
          (r.k === actual ? " selected" : "") + ">" +
          (orden === "rank" ? String(r.rank).padStart(2, "0") + " · " : "") +
          esc(r.n) + "</option>";
      }).join("");
    }

    function bloque(v, l, s) {
      return '<div><span class="v">' + v + '</span><span class="l">' + l +
        "</span>" + (s ? '<span class="s">' + s + "</span>" : "") + "</div>";
    }

    function pintar() {
      var r = D.deps.filter(function (x) { return x.k === actual; })[0];
      document.getElementById("depPos").innerHTML =
        "puesto " + r.rank + " de " + D.deps.length + " · " + esc(r.arq) +
        " · " + enlaceMapa("ver su mapa", "dep=" + (r.k || slugU(r.n)));

      var est = r.estratos || [0, 0, 0, 0];
      var estTot = est.reduce(function (a, b) { return a + b; }, 0) || 1;
      var ESTN = ["menos de 5 ha", "5 a 20 ha", "20 a 100 ha", "más de 100 ha"];

      var mx = 0;
      (r.meses || []).forEach(function (v) { if (v > mx) mx = v; });

      document.getElementById("depFicha").innerHTML =
        '<div class="kpis ficha">' +
          bloque(usd(r.sam), "mercado anual", "SAM · " + pct(r.pct_sam, 1) +
                 " del país") +
          bloque(nf(r.cli), "clientes", "de " + nf(r.prod) + " productores") +
          bloque("US$ " + nf(r.ticket), "ticket anual", "por cliente") +
          bloque(nf(r.ha), "hectáreas", "cosechadas en " + nf(r.cultivos) +
                 " cultivos") +
          bloque("US$ " + nf(r.gasto), "gasto por ha", "insumos comprados") +
          bloque(r.horas === null ? "—" : nf(r.horas, 1) + " h",
                 "al centro de provincia",
                 r.bajo2 === null ? "" : pct(r.bajo2, 0) + " bajo 2 h") +
        "</div>" +

        '<div class="grid2" style="margin-top:14px">' +

          '<div class="sub-card"><div class="eyebrow">Estructura de la tierra' +
          "</div>" +
          '<div class="barras compact">' + est.map(function (v, i) {
            return '<div class="bar"><span class="bn">' + ESTN[i] + "</span>" +
              '<span class="bv mono">' + nf(v) + "</span>" +
              '<span class="bt"><i style="width:' +
              (100 * v / estTot).toFixed(1) + '%"></i></span>' +
              '<span class="bp mono">' + pct(100 * v / estTot, 1) + "</span>" +
              "</div>";
          }).join("") + "</div>" +
          '<p class="sub">De ' + nf(r.prod) + " productores, " + nf(r.sobre5) +
          " superan las 5 ha. " + nf(r.compran) + " ya compran insumos y " +
          nf(r.credito) + " lo hacen a crédito (" + pct(r.t_cred, 1) +
          "). Aplican fertilizante " + pct(r.t_fert, 1) + ".</p></div>" +

          '<div class="sub-card"><div class="eyebrow">Cuándo compra</div>' +
          '<div class="minical">' + (r.meses || []).map(function (v, i) {
            var alto = D.meses[i] === r.mes;
            return '<span class="mc' + (alto ? " pico" : "") +
              '" title="' + D.meses[i] + ": " + nf(v, 1) + '%">' +
              '<i style="height:' + Math.max(4, 100 * v / (mx || 1)).toFixed(0) +
              '%"></i><b>' + D.meses[i].charAt(0) + "</b></span>";
          }).join("") + "</div>" +
          '<p class="sub">Pico en <b>' + esc(r.mes) + "</b>; cuatro meses " +
          "concentran " + pct(r.top4, 0) + " del año. " +
          (r.top4 >= 65
            ? "Por encima del 65% no sostiene oficina permanente: se atiende " +
              "con brigada de campaña."
            : r.top4 <= 45
              ? "Por debajo del 45%, la demanda alcanza para operar todo el año."
              : "Demanda de estacionalidad intermedia.") + "</p></div>" +

        "</div>" +

        '<div class="grid2" style="margin-top:14px">' +
          '<div class="sub-card"><div class="eyebrow">Llegar y sacar</div>' +
          '<dl class="pares">' +
            par("Al centro de provincia", r.horas === null ? "—" :
                nf(r.horas, 1) + " h") +
            par("Antes, en línea recta", r.horas_proxy === null ? "—" :
                nf(r.horas_proxy, 1) + " h") +
            par("Sectores bajo 2 h", r.bajo2 === null ? "—" : pct(r.bajo2, 1)) +
            par("Sectores sobre 4 h", r.sobre4 === null ? "—" : pct(r.sobre4, 1)) +
            par("Puerto más cercano", r.puerto ? esc(r.puerto) +
                (r.h_puerto === null ? "" : " · " + nf(r.h_puerto, 1) + " h") : "—") +
            par("Sin conexión vial a puerto",
                r.sin_puerto === null ? "—" : pct(r.sin_puerto, 1)) +
            par("Costo de viaje", r.costo === null ? "—" :
                "US$ " + nf(r.costo, 1)) +
          "</dl></div>" +

          '<div class="sub-card"><div class="eyebrow">Tejido empresarial</div>' +
          '<dl class="pares">' +
            par("Territorios de venta", nf(r.terr) +
                (r.terr ? " · " + nf(r.terr_dia) + " en un día" : "")) +
            par("Sectores estadísticos", r.sectores === null ? "—" :
                nf(r.sectores)) +
            par("Superficie agrícola", r.ha_agri === null ? "—" :
                nf(r.ha_agri) + " ha") +
            par("Empresas prospecto", r.emp === null ? "—" : nf(r.emp)) +
            par("Agroexportadores", nf(r.exp_n) +
                (r.exp_fob ? " · " + pFob(r.exp_fob, SEM_DEP) : "")) +
            par("Importadores de insumos", nf(r.imp_n) +
                (r.imp_fob ? " · " + pFob(r.imp_fob, SEM_DEP) : "")) +
            par("Mercado total (TAM)", usd(r.tam)) +
          "</dl></div>" +
        "</div>";
    }

    function par(k, v) {
      return "<dt>" + k + "</dt><dd class='mono'>" + v + "</dd>";
    }

    sel.onchange = function () { actual = sel.value; pintar(); };
    document.getElementById("fDeptoOrden").onclick = function (ev) {
      var b = ev.target.closest("button");
      if (!b) return;
      orden = b.dataset.o;
      this.querySelectorAll("button").forEach(function (x) {
        if (x === b) x.setAttribute("aria-pressed", "true");
        else x.removeAttribute("aria-pressed");
      });
      llenar();
    };

    llenar();
    pintar();
    REPINTAR.departamentos = pintar;
    /* El mapa del modulo sigue a la region elegida: abrir la ficha de Junin y
       ver el mapa del Peru entero obliga a un salto que la ficha ya resolvio. */
    var _pintarDep = pintar;
    pintar = function () {
      _pintarDep();
      mapaEn("mapDep", "#dep=" + actual);
    };
    mapaEn("mapDep", "#dep=" + actual);
  }).catch(fallo);
}

/* -------------------------------------------------------------- comercio -- */
/* Las dos mitades de esta pantalla dejaron de medir lo mismo y conviene
   decirlo donde se piden los datos. La importación de insumos sigue siendo la
   ventana de diez semanas que el sitio anualiza —es lo único que hay—. La
   agroexportación tiene cinco años medidos desde que se bajó el histórico, y
   no había razón para seguir mostrándola extrapolada al lado: se leía como si
   ambas cifras salieran del mismo periodo. Cada una declara el suyo. */
function vistaComercio() {
  Promise.all([cargar("comercio"),
               cargar("exportaciones/mercado"),
               cargar("exportaciones/exportadores_min")])
    .then(function (r) {
      REPINTAR.comercio = function () { pintarComercio(r[0], r[1], r[2]); };
      pintarComercio(r[0], r[1], r[2]);
    }).catch(fallo);
}

/* El último año que ya cerró. El año en curso está incompleto por definición
   —el rezago de regularización— y ponerlo al lado de uno entero inventa una
   caída que no ocurrió. */
function anioCerrado(E) {
  var c = E.anios_con_dato.filter(function (a) { return a < E.anio_en_curso; });
  return c[c.length - 1];
}

function pintarComercio(D, E, W) {
  var m = D.meta, si = m.semanas_imp;
  var anios = E.anios_con_dato, ac = anioCerrado(E);
  var rango = anios[0] + "–" + anios[anios.length - 1];

  /* El periodo elegido arriba mueve la mitad importadora y no la exportadora:
     una cifra medida no se anualiza. El pie de cada KPI dice cuál es cuál. */
  document.getElementById("comKpis").innerHTML = [
    [pFob(m.fob_imp, si), "insumos importados",
     pSuf(si) + ", desde " + si + " semanas medidas"],
    [nf(m.n_imp), "importadores de insumos", "con RUC identificado"],
    [usd(E.por_anio[ac].fob), "agroexportación " + ac,
     "año cerrado, medido sin extrapolar"],
    [nf(E.empresas_con_dato), "agroexportadores", "con RUC, " + rango],
  ].map(function (k) {
    return "<div><span class='v'>" + k[0] + "</span><span class='l'>" +
      k[1] + "</span><span class='s'>" + k[2] + "</span></div>";
  }).join("");

  barras(document.getElementById("comFamilias"),
    D.familias.map(function (r) {
      return { n: r.n, v: r.fob,
               t: pFob(r.fob, si) + " · " + pNum(r.tn, si) + " t" };
    }));

  barras(document.getElementById("comOrigenes"),
    D.origenes.slice(0, 12).map(function (r) {
      return { n: pais(r.n), v: r.fob, t: pFob(r.fob, si) };
    }));

  barras(document.getElementById("comDestinos"),
    E.destinos.slice(0, 12).map(function (r) {
      return { n: pais(r.n), v: r.fob, t: usd(r.fob) };
    }));

  tabla(document.getElementById("tImportadores"), [
    { k: "n", t: "Empresa", l: 1, f: function (r) {
        return "<b>" + esc(r.n) + "</b><span class='sub2'>" + r.r +
          (r.dep ? " · " + esc(r.dep) : "") + "</span>"; } },
    { k: "rubro", t: "Rubro", l: 1, f: function (r) {
        return "<span class='tag'>" + esc(r.rubro) + "</span>"; } },
    { k: "fob", t: "CIF " + pSuf(si), f: function (r) {
        return pFob(r.fob, si); } },
    { k: "tn", t: "Toneladas", f: function (r) { return pNum(r.tn, si); } },
    { k: "pct", t: "% del total", f: function (r) { return pct(r.pct, 2); } },
  ], D.importadores, { sort: "fob" });

  /* El ranking exportador sale del recorte de cinco años, no de la ventana.
     El departamento que acompaña al RUC es el ubigeo del manifiesto, que
     apunta al fundo: por eso Camposol aparece en La Libertad y no en Lima. */
  var top = W.emp.map(function (e) {
    return { r: e.r, n: e.n, d: e.d, t: e.t, ult: e.a[ac] || 0,
             np: e.np, o: e.o };
  }).sort(function (a, b) { return b.t - a.t; }).slice(0, 100);

  tabla(document.getElementById("tExportadores"), [
    { k: "n", t: "Empresa", l: 1, f: function (r) {
        return "<b>" + esc(r.n) + "</b><span class='sub2'>" + r.r +
          (r.d ? " · " + esc(depNom(r.d)) : "") + "</span>"; } },
    { k: "t", t: "FOB " + rango, f: function (r) { return usd(r.t); } },
    { k: "ult", t: "FOB " + ac, f: function (r) { return usd(r.ult); } },
    { k: "np", t: "Destinos", f: function (r) { return nf(r.np); } },
    { k: "o", t: "Embarques", f: function (r) { return nf(r.o); } },
  ], top, { sort: "t" });

  document.getElementById("comNota").innerHTML =
    "Esta pantalla junta dos relojes y conviene leerlos por separado. " +
    "<b>La importación de insumos</b> mide " + si + " semanas y las " +
    "anualiza: el mensual y el anual extrapolan esa ventana sin corregir " +
    "estacionalidad, así que son orden de magnitud y no el cierre del año. " +
    "El selector de periodo actúa solo sobre esa mitad. " +
    "<b>La agroexportación</b> ya no se extrapola: son " + rango + " " +
    "medidos sobre " + nf(E.total.semanas) + " semanas de manifiesto y " +
    nf(E.operaciones) + " series de embarque, depuradas de las " +
    "republicaciones con que SUNAT rectifica una declaración ya publicada. " +
    "Por eso no se mueve al cambiar el periodo, y por eso " + anios[anios.length - 1] +
    " no se compara con un año cerrado. El detalle por producto, destino y " +
    "territorio está en <a href='#exportacion'>Exportación</a>. " +
    "Fuente: microdatos de manifiestos de SUNAT, publicados bajo la Ley " +
    "27806 de transparencia. La agroexportación se restringe a los capítulos " +
    "arancelarios 07, 08, 09, 12, 18, 20 y 21: el archivo de aduanas trae la " +
    "exportación completa del país, donde el mineral de cobre y el oro por sí " +
    "solos son el 60% del FOB.";
}

/* ------------------------------------------------------------- logistica -- */
function vistaLogistica() {
  pintarPisos();
  cargar("logistica").then(function (D) {
    tabla(document.getElementById("tLogistica"), [
      { k: "n", t: "Departamento", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b>"; } },
      { k: "sam", t: "Mercado", f: function (r) { return usd(r.sam); } },
      { k: "alt", t: "Cota", f: function (r) {
          return r.alt === null || r.alt === undefined
            ? "—" : nf(r.alt) + " m"; } },
      { k: "real", t: "Horas reales", f: function (r) {
          return r.real === null ? "—" : nf(r.real, 1) + " h"; } },
      /* Lo que agrega el desnivel. Va con signo y en color porque el número
         que importa no es la hora sino cuánto de ella estaba sin contar: la
         sierra pagaba una cuarta parte de su viaje y la costa casi nada. */
      { k: "terr", t: "Del terreno", f: function (r) {
          if (r.terr === null || r.terr === undefined) return "—";
          return "<span class='delta " + (r.terr > 0.15 ? "peor" : "") +
            "' title='" + esc(nf(r.pct_terr, 1) + "% mas que en llano") +
            "'>+" + nf(r.terr, 2) + " h</span>"; } },
      { k: "proxy", t: "Línea recta", cls: "faint", f: function (r) {
          return r.proxy === null ? "—" : nf(r.proxy, 1) + " h"; } },
      { k: "dif", t: "Diferencia", f: function (r) {
          if (r.dif === null) return "—";
          var c = r.dif > 0 ? "peor" : "mejor";
          return "<span class='delta " + c + "'>" +
            (r.dif > 0 ? "+" : "") + nf(r.dif, 1) + " h</span>"; } },
      { k: "bajo2", t: "Bajo 2 h", f: function (r) {
          return r.bajo2 === null ? "—" : pct(r.bajo2, 1); } },
      { k: "sobre4", t: "Sobre 4 h", f: function (r) {
          return r.sobre4 === null ? "—" : pct(r.sobre4, 1); } },
      { k: "puerto", t: "Al puerto", f: function (r) {
          return r.puerto === null ? "—" : nf(r.puerto, 1) + " h"; } },
      { k: "sin_puerto", t: "Sin salida", f: function (r) {
          if (!r.sin_puerto) return "—";
          return "<span class='delta peor'>" + pct(r.sin_puerto, 1) + "</span>"; } },
      { k: "costo", t: "Costo viaje", f: function (r) {
          return r.costo === null ? "—" : "US$ " + nf(r.costo, 1); } },
    ], D.deps, { sort: "sam" });

    tabla(document.getElementById("tPuertos"), [
      { k: "n", t: "Puerto", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b>"; } },
      { k: "reg", t: "Región", l: 1, f: function (r) { return esc(r.reg); } },
      { k: "tipo", t: "Tipo", l: 1, f: function (r) {
          return "<span class='tag'>" + esc(r.tipo) + "</span>"; } },
      { k: "rel", t: "Relevancia agro", l: 1, f: function (r) {
          return esc(r.rel); } },
    ], D.puertos, { sort: "n", asc: true });

    /* Se nombran los casos concretos porque son los que cambian una decisión:
       el promedio nacional no dice a qué departamento se puede entrar. */
    var rescata = D.deps.filter(function (r) { return r.dif !== null && r.dif < -0.3; })
      .sort(function (a, b) { return a.dif - b.dif; }).slice(0, 4);
    var sin = D.deps.filter(function (r) { return r.sin_puerto > 20; })
      .sort(function (a, b) { return b.sin_puerto - a.sin_puerto; });

    /* El desnivel, dicho con nombres. Sin esto la columna «del terreno» es
       una cifra más; con esto es el aviso de que las comparaciones entre una
       región andina y una costeña que se hicieron antes están sesgadas. */
    /* El porcentaje viene calculado del origen. Sacarlo aquí dividiendo dos
       cifras ya redondeadas a un decimal convertía un +26% en un +33%. */
    var sube = D.deps.filter(function (r) {
      return r.pct_terr !== null && r.pct_terr !== undefined;
    }).map(function (r) {
      return {n: r.n, alt: r.alt, pct: r.pct_terr};
    }).sort(function (a, b) { return b.pct - a.pct; });

    document.getElementById("logNota").innerHTML =
      (sube.length
        ? "<div class='note'><span class='h'>La pendiente entra en la " +
          "cuenta</span>Hasta hace poco la hora de viaje salía de la clase " +
          "de vía y su superficie: un camión cargado subiendo tres mil " +
          "metros contaba igual que uno en llano. Ahora cada tramo lleva su " +
          "desnivel, medido sobre el relieve. El promedio nacional sube 13% " +
          "y el reparto es lo que importa: <b>" +
          sube.slice(0, 3).map(function (r) {
            return esc(r.n) + " +" + nf(r.pct, 0) + "%";
          }).join(", ") + "</b> contra <b>" +
          sube.slice(-2).map(function (r) {
            return esc(r.n) + " +" + nf(r.pct, 0) + "%";
          }).join(" y ") + "</b>. La sierra pagaba una cuarta parte de su " +
          "tiempo de viaje sin que ninguna cifra lo dijera, así que toda " +
          "comparación anterior entre una región andina y una costeña " +
          "—costo de servir, sectores bajo dos horas, orden de apertura— " +
          "favorecía a la sierra sin motivo.</div>"
        : "") +
      "<p>Medir la distancia en línea recta parecía inofensivo y no lo era. " +
      "Al rutear sobre la carretera real, " +
      (rescata.length
        ? "<b>" + rescata.map(function (r) { return esc(r.n); }).join(", ") +
          "</b> resultaron más accesibles de lo que el cálculo anterior " +
          "suponía —hasta " + nf(Math.abs(rescata[0].dif), 1) +
          " horas menos—, y dejaron de estar descartados."
        : "las diferencias resultaron menores.") + "</p>" +
      (sin.length
        ? "<div class='note brass'><span class='h'>El caso que no tiene " +
          "arreglo logístico</span>" +
          sin.map(function (r) {
            return "<b>" + esc(r.n) + "</b>: " + pct(r.sin_puerto, 1) +
              " de sus sectores no tiene ninguna ruta por carretera hasta un " +
              "puerto marítimo.";
          }).join("<br>") +
          " No es un problema de tiempo sino de red: no existe el camino. " +
          "Cualquier operación allí depende de vía fluvial o aérea.</div>"
        : "");
  }).catch(fallo);
}


/* ------------------------------------------------- el mercado por piso -- */
/* Los dos negocios de esta plataforma no viven a la misma altura, y sin la
   cota no había manera de verlo: el FOB exportador sale de valle costero
   irrigado y el padrón de compradores de insumos está en la sierra. Un
   inventario colocado siguiendo el dinero de exportación queda lejos de la
   mitad de los clientes, que es una decisión de capital tomada al revés.

   La banda de cada producto se mide sobre el embarque —el FOB de cada línea
   del manifiesto contra la cota del distrito que declara— y no se cita de un
   manual de agronomía. Que el café salga en su banda conocida es, de paso, la
   comprobación de que el ubigeo apunta al fundo y no a la oficina. */
function pintarPisos() {
  var caja = document.getElementById("altSam");
  if (!caja) return;
  cargar("altitud").then(function (A) {
    var sam = A.sectores.por_piso.slice().sort(function (a, b) {
      return b.sam_mm - a.sam_mm; });
    var fob = A.distritos.por_piso.slice().sort(function (a, b) {
      return b.fob_mm - a.fob_mm; });

    barras(caja, sam.map(function (r) {
      return {n: r.piso, v: r.sam_mm,
              t: usd(r.sam_mm * 1e6) + " · " + nf(r.clientes) + " clientes"};
    }));
    barras(document.getElementById("altFob"), fob.map(function (r) {
      return {n: r.piso, v: r.fob_mm, t: usd(r.fob_mm * 1e6)};
    }));

    tabla(document.getElementById("tAltBanda"), [
      { k: "familia", t: "Producto", l: 1, f: function (r) {
          return "<b>" + esc(r.familia) + "</b><span class='sub2'>" +
            nf(r.distritos) + " distritos</span>"; } },
      { k: "fob_mm", t: "FOB embarcado", f: function (r) {
          return usd(r.fob_mm * 1e6); } },
      { k: "p10", t: "p10", f: function (r) { return nf(r.p10) + " m"; } },
      { k: "p50", t: "Mediana", f: function (r) {
          return "<b>" + nf(r.p50) + " m</b>"; } },
      { k: "p90", t: "p90", f: function (r) { return nf(r.p90) + " m"; } },
    ], A.bandas, { sort: "fob_mm" });

    var sierra = sam.filter(function (r) {
      return ["quechua", "suni", "puna"].indexOf(r.piso) >= 0; });
    var mmS = sierra.reduce(function (a, r) { return a + r.sam_mm; }, 0);
    var cliS = sierra.reduce(function (a, r) { return a + r.clientes; }, 0);
    var cliT = sam.reduce(function (a, r) { return a + r.clientes; }, 0);
    var chala = sam.filter(function (r) { return r.piso === "chala"; })[0];
    var fobChala = fob.filter(function (r) { return r.piso === "chala"; })[0];

    document.getElementById("altNota").innerHTML =
      "El FOB de exportación sale <b>" + pct(fobChala ? fobChala.pct : 0, 1) +
      " de chala</b>, bajo los 500 m: agroexportación de valle costero " +
      "irrigado. El mercado de insumos vive en otra parte —quechua, suni y " +
      "puna suman <b>" + usd(mmS * 1e6) + " y " + nf(cliS) + " clientes, el " +
      pct(100 * cliS / cliT, 0) + " del padrón</b>, contra " +
      nf(chala ? chala.clientes : 0) + " en chala—. Son dos negocios " +
      "distintos: el exportador es concentrado, costero y de ticket grande; " +
      "el de sierra es disperso, de ticket chico y de muchos. " +
      "La cota sale del relieve a " + esc(A.fuente.split("zoom")[1] || "") +
      ", con error mediano de " + A.validacion.error_mediano_m + " m contra " +
      "veinte altitudes publicadas: sirve para separar pisos y no para " +
      "afirmar la cota de una parcela. La banda de cada producto se mide " +
      "sobre el embarque de " + A.anios_embarque.join(", ") + ", que son los " +
      "años en que el manifiesto trae el ubigeo lleno.";
  }).catch(function () { caja.innerHTML = ""; });
}

/* ---------------------------------------------------------------- metodo -- */
/* El método vive en el sitio y no solo en el PDF a propósito: quien discuta
   una cifra tiene que poder llegar al supuesto que la produce sin pedir un
   archivo adjunto. */
function vistaMetodo() {
  cargar("resumen").then(function (D) {
    var k = D.kpi;

    document.getElementById("metModelo").innerHTML =
      "<p>El mercado no se estima por encuesta de intención sino por lo que " +
      "la tierra obliga a gastar. El punto de partida es la <b>superficie " +
      "efectivamente cosechada</b> —no la sembrada ni la disponible— cruzada " +
      "con el <b>costo real de insumos por hectárea de cada cultivo</b>, que " +
      "difiere en un orden de magnitud entre una papa y un pasto.</p>" +
      "<dl class='pares'>" +
      "<dt>1 · Superficie</dt><dd class='mono'>" + nf(k.ha_cosechada) +
      " ha cosechadas</dd>" +
      "<dt>2 · Gasto por hectárea</dt><dd class='mono'>US$ " + nf(k.gasto_ha) +
      " promedio ponderado</dd>" +
      "<dt>3 · Mercado total (TAM)</dt><dd class='mono'>" + usd(k.tam) + "</dd>" +
      "<dt>4 · Mercado alcanzable (SAM)</dt><dd class='mono'>" + usd(k.sam) +
      "</dd>" +
      "<dt>5 · Clientes</dt><dd class='mono'>" + nf(k.clientes) + "</dd>" +
      "<dt>6 · Ticket anual</dt><dd class='mono'>US$ " + nf(k.ticket) +
      "</dd></dl>" +
      "<p>El paso del TAM al SAM es el que más recorta y el que más se " +
      "discute: de " + nf(k.productores) + " productores agropecuarios, solo " +
      nf(k.sobre5) + " superan las cinco hectáreas —debajo de ese umbral la " +
      "agricultura es de autoconsumo— y " + nf(k.credito) + " compran a " +
      "crédito, que es la forma en que AgroJuntos vende.</p>" +
      "<p>El ordenamiento de las regiones (v3) suma al tamaño dos factores " +
      "que el tamaño solo no captura: <b>logística</b>, con peso de 15%, " +
      "porque un mercado al que no se llega no es mercado; y " +
      "<b>estacionalidad</b>, con 10%, porque una demanda concentrada en " +
      "cuatro meses no sostiene una operación permanente.</p>";

    document.getElementById("metValida").innerHTML =
      "<p>Un modelo que solo se explica a sí mismo no vale nada. Estos son " +
      "los dos contrastes contra datos que el modelo no usó:</p>" +
      "<div class='note'><span class='h'>Contra ventas reales</span>" +
      "El modelo estima un gasto de <b>US$ " + nf(k.ticket) + " por cliente " +
      "al año</b>. El libro de ventas de AgroJuntos da <b>US$ 3,264</b>. La " +
      "coincidencia es mejor de lo que cabía esperar y no se forzó: el " +
      "modelo se construyó sin mirar esa cifra.</div>" +
      "<div class='note'><span class='h'>Contra la aduana</span>" +
      "El modelo estima <b>US$ 1,038 MM</b> de fertilizante a precio de " +
      "chacra. La importación registrada suma <b>US$ 693 MM</b> CIF, y el " +
      "producto importado cubre el <b>89.5%</b> de la oferta nacional. La " +
      "diferencia es la cadena de distribución, que es exactamente el margen " +
      "donde opera el negocio.</div>" +
      "<p class='sub'>Ninguna de las dos es una demostración. Son " +
      "comprobaciones de que las cifras están en el orden de magnitud " +
      "correcto, que es lo máximo que un dimensionamiento puede ofrecer.</p>";

    tabla(document.getElementById("tFuentes"), [
      { k: "f", t: "Fuente", l: 1, f: function (r) {
          return "<b>" + esc(r.f) + "</b><span class='sub2'>" + esc(r.d) +
            "</span>"; } },
      { k: "a", t: "Qué aporta", l: 1, f: function (r) { return esc(r.a); } },
      { k: "y", t: "Año", f: function (r) { return r.y; } },
    ], [
      { f: "MIDAGRI", d: "Padrón Nacional de Sectores Estadísticos · RM N.º 0026-2025",
        a: "7,043 sectores con UBIGEO, hectáreas y centroide", y: 2024 },
      { f: "MIDAGRI", d: "Anuario de Producción Agrícola",
        a: "Superficie cosechada y rendimiento por cultivo y mes", y: 2023 },
      { f: "INEI", d: "Censo Nacional Agropecuario (CENAGRO)",
        a: "Productores por estrato de tamaño y uso de insumos", y: 2012 },
      { f: "INEI", d: "Encuesta Nacional Agropecuaria · costos de producción",
        a: "Costo de insumos por hectárea y por cultivo", y: 2018 },
      { f: "SUNAT", d: "Padrón Reducido de Contribuyentes",
        a: "22,437 empresas con RUC, actividad y domicilio fiscal", y: 2025 },
      { f: "SUNAT", d: "Microdatos de aduanas · Ley 27806",
        a: "Importación de insumos y agroexportación por empresa", y: 2025 },
      { f: "OpenStreetMap", d: "Extracto de Perú · licencia ODbL",
        a: "88,962 vías para el ruteo y 194 capitales de provincia", y: 2025 },
      { f: "APN", d: "Autoridad Portuaria Nacional",
        a: "Ubicación y tipo de los 17 puertos", y: 2025 },
    ], { sort: "f", asc: true });

    document.getElementById("metLimites").innerHTML =
      "<div class='note brass'><span class='h'>El CENAGRO tiene doce años" +
      "</span>Es el último censo agropecuario disponible. Las tasas de uso " +
      "de insumos y la estructura de tamaño de las unidades se toman de él, " +
      "de modo que cualquier cambio estructural posterior a 2012 no está " +
      "recogido. La superficie y la producción sí son de 2023–2024.</div>" +
      "<div class='note brass'><span class='h'>Las cifras de aduanas " +
      "anualizan diez semanas</span>Los microdatos publicados cubren un " +
      "tramo, no el año. Anualizar supone que el resto del año se comporta " +
      "igual, lo que en un sector estacional es una simplificación fuerte. " +
      "Sirven para ordenar empresas por tamaño, no para declarar el FOB " +
      "anual de ninguna.</div>" +
      "<div class='note brass'><span class='h'>El domicilio fiscal no es el " +
      "fundo</span>La ubicación de cada empresa es la que declara ante " +
      "SUNAT. Las agroindustriales grandes suelen declarar en Lima y cultivar " +
      "en otra región, así que la distribución territorial del directorio " +
      "subestima las regiones productoras.</div>" +
      "<div class='note brass'><span class='h'>Discrepancia pendiente en " +
      "ventas propias</span>El dossier de AgroJuntos declara más de " +
      "US$ 200,000 en ventas; el libro de ventas analizado suma US$ 24,787. " +
      "La validación del ticket usa el libro, que es lo que se pudo " +
      "verificar. La diferencia sigue sin explicarse y debe resolverse antes " +
      "de usar la cifra mayor ante un tercero.</div>" +
      "<div class='note'><span class='h'>Corrección de una afirmación " +
      "anterior</span>En una versión previa se afirmó que el detalle " +
      "aduanero por empresa no era descargable públicamente en el Perú. Es " +
      "falso: SUNAT lo publica en " +
      "<span class='mono'>aduanet.gob.pe/aduanas/informae/</span> bajo la " +
      "Ley 27806. Todo el análisis de comercio exterior de este sitio se " +
      "construye sobre esa fuente.</div>";
  }).catch(fallo);
}


/* ------------------------------------------------------------ productos -- */
/* Tres preguntas que el resto del sitio no respondía: qué se siembra en cada
   departamento, qué producto se exporta y por qué aduana sale. Las dos
   primeras vienen de fuentes distintas —MIDAGRI para la tierra, SUNAT para el
   embarque— y no se suman entre sí: una mide hectáreas, la otra dólares FOB. */
/* Dos fuentes que miden cosas distintas y no se suman: la superficie es de
   MIDAGRI —hectáreas cosechadas— y el embarque es de SUNAT —dólares FOB—. Lo
   que cambió es de dónde sale el embarque: era la ventana de diez semanas
   anualizada, y son cinco años medidos.

   El corte por departamento del embarque no llega hasta 2026 sino hasta 2024,
   porque es el último año en que SUNAT llenó el ubigeo del manifiesto; y ese
   ubigeo apunta al fundo, no al domicilio fiscal, que es justamente lo que lo
   hace comparable con la hectárea de al lado. Las dos salvedades viajan a la
   vista, porque una cifra sin su salvedad viaja más rápido que la salvedad. */
function vistaProductos() {
  Promise.all([cargar("productos"), cargar("exportaciones/mercado")])
    .then(function (r) {
      REPINTAR.productos = function () { pintarProductos(r[0], r[1]); };
      pintarProductos(r[0], r[1]);
    }).catch(fallo);
}

function pintarProductos(D, E) {
    var m = D.meta;
    var dep = "";                       // "" = todo el país
    var anios = E.anios_con_dato;
    var cerrado = anios.filter(function (a) {
      return a < E.anio_en_curso; }).pop();
    var rango = anios[0] + "–" + anios[anios.length - 1];
    var aduNom = {};                    // código -> nombre y vía
    D.aduanas.forEach(function (a) { aduNom[a.c] = a; });
    var aduMed = E.aduanas.map(function (a) {
      var i = aduNom[a.n] || {};
      return {c: a.n, n: i.n || a.n, via: i.via || "—", fob: a.fob,
              tn: Math.round(a.kg / 1000), emp: a.empresas,
              mezcla: a.mezcla || []};
    });
    var depMed = {};
    E.departamentos.lista.forEach(function (x) { depMed[x.n] = x; });
    var anTer = E.departamentos.anios_usados;

    document.getElementById("proKpis").innerHTML = [
      [nf(m.ha), "hectáreas cosechadas", "en " + nf(m.cultivos) + " cultivos"],
      [D.cultivos[0].n, "mayor superficie", nf(D.cultivos[0].ha) + " ha"],
      [usd(E.por_anio[cerrado].fob), "agroexportación " + cerrado,
       "año cerrado, medido sin extrapolar"],
      [aduMed[0].n, "principal salida",
       pct(100 * aduMed[0].fob / E.total.fob, 0) + " del FOB de " + rango],
    ].map(function (k) {
      return "<div><span class='v'>" + esc(k[0]) + "</span><span class='l'>" +
        k[1] + "</span><span class='s'>" + esc(k[2]) + "</span></div>";
    }).join("");

    /* ---- selector de departamento ---- */
    var deps = Object.keys(D.cult_dep).sort(function (a, b) {
      return a.localeCompare(b, "es"); });
    document.getElementById("fProDep").innerHTML =
      '<option value="">Todo el Perú</option>' +
      deps.map(function (d) {
        return '<option value="' + esc(d) + '">' + esc(d) + "</option>"; }).join("");

    function pintarDep() {
      var cult = dep ? (D.cult_dep[dep] || []) : null;
      var titC = document.getElementById("proCultTit");
      var titE = document.getElementById("proExpTit");

      if (cult) {
        titC.textContent = "Cultivos de " + dep;
        barras(document.getElementById("proCultivos"),
          cult.map(function (c) {
            return { n: c.n, v: c.ha, t: nf(c.ha) + " ha", p: c.pct }; }));
      } else {
        titC.textContent = "Cultivos de mayor superficie del país";
        barras(document.getElementById("proCultivos"),
          D.cultivos.slice(0, 12).map(function (c) {
            return { n: c.n, v: c.ha, t: nf(c.ha) + " ha" }; }));
      }

      var fila = dep ? depMed[dep.toUpperCase()] : null;
      var ex = fila ? fila.familias : null;
      titE.textContent = dep ? "Qué exporta " + dep : "Qué se exporta del país";
      var fuente = ex || E.familias.slice(0, 8).map(function (f) {
        return { n: f.n, v: f.fob }; });
      if (!fuente.length) {
        document.getElementById("proExpDep").innerHTML =
          "<p class='sub'>Sin agroexportación con ubigeo en " +
          anTer.join(", ") + ".</p>";
      } else {
        barras(document.getElementById("proExpDep"),
          fuente.map(function (p) {
            return { n: p.n, v: p.v, t: usd(p.v) }; }));
      }

      document.getElementById("proExpNota").innerHTML = dep
        ? (fila
            ? "<b>" + nf(fila.empresas) + "</b> empresas embarcaron desde " +
              esc(dep) + ": " + usd(fila.fob) + " en " + anTer.join(", ") +
              ", medidos y no anualizados. El origen es el <b>ubigeo del " +
              "manifiesto</b>, que apunta al fundo y no al domicilio fiscal " +
              "—por eso se puede mirar al lado de la hectárea—, y el corte se " +
              "detiene en " + anTer[anTer.length - 1] + " porque es el último " +
              "año en que SUNAT llenó ese campo."
            : "Ninguna operación con ubigeo de " + esc(dep) +
              " en " + anTer.join(", ") + ".")
        : "La superficie es de MIDAGRI y el FOB de SUNAT: miden cosas " +
          "distintas —hectáreas cosechadas y dólares embarcados— y no se " +
          "suman entre sí. El embarque son " + rango + " medidos; el corte " +
          "por departamento se limita a " + anTer.join(", ") + ", que son los " +
          "años con ubigeo en el manifiesto.";

      var tot = cult
        ? cult.reduce(function (a, c) { return a + c.ha; }, 0) : m.ha;
      document.getElementById("proDepMeta").textContent = cult
        ? nf(tot) + " ha en los " + cult.length + " cultivos principales"
        : nf(m.ha) + " ha en " + nf(m.cultivos) + " cultivos";

      tabla(document.getElementById("tCultivos"), cult ? [
        { k: "n", t: "Cultivo", l: 1, f: function (r) {
            return "<b>" + esc(r.n) + "</b>"; } },
        { k: "tipo", t: "Tipo", l: 1, f: function (r) {
            return "<span class='tag'>" +
              (r.tipo === "tran" ? "transitorio" : "permanente") + "</span>"; } },
        { k: "ha", t: "Hectáreas", f: function (r) { return nf(r.ha); } },
        { k: "pct", t: "% del dep.", f: function (r) { return pct(r.pct, 1); } },
        { k: "usd", t: "Mercado de insumos", f: function (r) {
            return usd(r.usd); } },
        { k: "mes", t: "Pico de siembra", f: function (r) { return r.mes; } },
      ] : [
        { k: "n", t: "Cultivo", l: 1, f: function (r) {
            return "<b>" + esc(r.n) + "</b>"; } },
        { k: "ha", t: "Hectáreas", f: function (r) { return nf(r.ha); } },
        { k: "usd", t: "Mercado de insumos", f: function (r) {
            return usd(r.usd); } },
        { k: "usdha", t: "US$ por ha", f: function (r) {
            return nf(r.usdha); } },
        { k: "deps", t: "Departamentos", f: function (r) { return nf(r.deps); } },
        { k: "lider", t: "Dónde se concentra", l: 1, f: function (r) {
            return esc(r.lider) + "<span class='sub2'>" + pct(r.pct, 1) +
              " de la superficie</span>"; } },
      ], cult || D.cultivos, { sort: "ha" });
    }

    document.getElementById("fProDep").onchange = function () {
      dep = this.value; pintarDep();
      mapaEn("mapPro", dep ? "#dep=" + slugU(dep) : "#peru");
    };
    pintarDep();

    /* ---- qué se exporta ---- */
    /* Familias y no partidas: el agregado de cinco años trabaja por familia,
       que es la unidad con la que se decide una línea de producto. La partida
       vive en el panel exportador, para quien la necesite. */
    tabla(document.getElementById("tProductos"), [
      { k: "n", t: "Producto", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b>"; } },
      { k: "fob", t: "FOB " + rango, f: function (r) { return usd(r.fob); } },
      { k: "kg", t: "Toneladas", f: function (r) {
          return nf(Math.round(r.kg / 1000)); } },
      { k: "empresas", t: "Empresas", f: function (r) {
          return nf(r.empresas); } },
      { k: "pct", t: "% del FOB", f: function (r) { return pct(r.pct, 1); } },
    ], E.familias, { sort: "fob" });

    /* ---- por dónde sale ---- */
    tabla(document.getElementById("tAduanas"), [
      { k: "n", t: "Aduana", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b><span class='sub2'>código " +
            r.c + "</span>"; } },
      { k: "via", t: "Vía", l: 1, f: function (r) {
          return "<span class='tag'>" + esc(r.via) + "</span>"; } },
      { k: "fob", t: "FOB " + rango, f: function (r) { return usd(r.fob); } },
      { k: "tn", t: "Toneladas", f: function (r) { return nf(r.tn); } },
      { k: "emp", t: "Empresas", f: function (r) { return nf(r.emp); } },
      { k: "lider", t: "Producto principal", l: 1, f: function (r) {
          var p = r.mezcla[0];
          if (!p) return "—";
          return esc(p.n) + "<span class='sub2'>" +
            pct(100 * p.v / r.fob, 1) + " de su FOB</span>"; } },
    ], aduMed, { sort: "fob" });

    /* La mezcla de producto de cada aduana explica por qué existe: Paita es
       café, Pisco es uva. Se despliega al pulsar la fila. */
    var tA = document.getElementById("tAduanas");
    tA.onclick = function (ev) {
      var tr = ev.target.closest("tbody tr");
      if (!tr) return;
      var nombre = (tr.querySelector("td.l b") || {}).textContent;
      var a = aduMed.filter(function (x) { return x.n === nombre; })[0];
      if (!a) return;
      var mezcla = a.mezcla || [];
      document.getElementById("proAduDet").innerHTML =
        "<div class='eyebrow'>Mezcla de producto · " + esc(a.n) + "</div>" +
        "<div class='barras compact' id='proMez'></div>";
      barras(document.getElementById("proMez"), mezcla.map(function (p) {
        return { n: p.n, v: p.v, t: usd(p.v) }; }));
    };

    /* La salvedad que esta nota traía —que el reparto por departamento usaba
       el domicilio fiscal porque en 2026 el ubigeo viene vacío— dejó de
       aplicar: la pantalla ya no se alimenta de las diez semanas de 2026 sino
       del agregado, y el agregado se limita a los años en que el campo viene
       lleno. La salvedad que queda es la contraria y hay que decirla igual:
       el corte territorial se detiene en 2024. */
    document.getElementById("proNota").innerHTML =
      "Superficie cosechada del anuario de producción agrícola de MIDAGRI " +
      "(2023); agroexportación de los microdatos de manifiestos de SUNAT bajo " +
      "la Ley 27806, <b>" + rango + " medidos y sin anualizar</b>. La aduana " +
      "de salida sale del campo <span class='mono'>CADU</span> del manifiesto " +
      "y se nombra con la Tabla 4 del Anexo 01 de SUNAT; el código 370 " +
      "corresponde a Chancay, habilitada el 21 de octubre de 2024 y todavía " +
      "ausente de ese anexo. " +
      "El reparto por departamento se limita a <b>" + anTer.join(", ") +
      "</b>: son los años en que SUNAT llena el ubigeo del manifiesto —el " +
      "100% del FOB— y ese campo apunta al lugar de producción y no a la " +
      "oficina, que es lo que permite mirarlo junto a la hectárea. Desde 2025 " +
      "el campo se apaga y el corte no se extiende: extenderlo sería dibujar " +
      "el mapa de la caída del registro, no el de la producción. " +
      "Las dos mitades de esta pantalla no se suman entre sí: una mide " +
      "hectáreas y la otra dólares embarcados.";
}


/* ---------------------------------------------------------- exportación --
   El gemelo exportador del módulo de importación, y con la misma disciplina:
   años medidos, nunca anualizados, y cada año con las semanas que lo
   respaldan. Se lee de `exportaciones/mercado` —43 KB— y de
   `exportaciones/exportadores_min`, el recorte de 1.2 MB del directorio de
   4,062 empresas; el archivo completo pesa 7.7 MB y lleva por empresa un cubo
   de producto × destino × partida que esta vista no muestra.

   Dos advertencias viajan con los datos y se pintan, no se omiten:

   1. El último mes nunca está completo. El embarque se declara al salir pero
      el archivo se arma al regularizar, y de ahí sale una frontera de
      completitud que aquí se dice en palabras.
   2. El origen sale del ubigeo del manifiesto, que apunta al fundo y no al
      domicilio fiscal, pero que SUNAT dejó de llenar. El corte se limita a
      los años que lo traen y la vista lo declara. */
var EXPM = null, EXPE = null, EXPQ = { anio: "" };
var EXP_COMPLETO = 45;   /* semanas archivadas para llamar completo a un año */
var MESES_EXP = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Set", "Oct", "Nov", "Dic"];

function expCompleto(a) {
  return (EXPM.cobertura_semanas[a] || 0) >= EXP_COMPLETO;
}
function expEnCurso(a) { return a === EXPM.anio_en_curso; }
function expEt(a) { return expEnCurso(a) ? a + " YTD" : a; }
function expPie(a) {
  var s = EXPM.cobertura_semanas[a] || 0;
  if (!s) return "pendiente de carga";
  if (expEnCurso(a)) {
    return s + " semanas al " + EXPM.ultimo_registro +
      " · el último mes sigue regularizando";
  }
  return s + " semanas archivadas";
}

/* Los nombres de departamento viajan sin tilde, como en todo el proyecto; se
   acentúan al mostrarlos y en ningún otro lado. */
var DEP_TILDE = { "ANCASH": "Áncash", "APURIMAC": "Apurímac",
                  "HUANUCO": "Huánuco", "JUNIN": "Junín",
                  "SAN MARTIN": "San Martín" };
function depNom(n) {
  var u = String(n).toUpperCase();
  if (DEP_TILDE[u]) return DEP_TILDE[u];
  return u.toLowerCase().replace(/(^|\s)([a-záéíóúñ])/g, function (m, a, c) {
    return a + c.toUpperCase();
  });
}
function expPico(r) {
  if (!r.perfil || !r.perfil.length) return -1;
  return r.perfil.indexOf(Math.max.apply(null, r.perfil));
}

/* La serie por año. Misma gramática de barras que la de importación: medida,
   parcial —rayada, con asterisco— o sin descargar —hueco punteado—. */
function expSerie(el, anios) {
  var vals = anios.map(function (a) {
    var b = EXPM.por_anio[a];
    return { a: a, hay: !!b, v: b ? b.fob : 0, emp: b ? b.empresas : 0,
             ops: b ? b.ops : 0 };
  });
  var mx = Math.max.apply(null, vals.map(function (f) {
    return f.hay ? f.v : 0; })) || 1;
  el.innerHTML = '<div class="serie">' + vals.map(function (f) {
    if (!f.hay) {
      return '<div class="sb vacio" title="' + esc(f.a +
        "\n\nSin semanas descargadas: no hay información para este año") +
        '"><i></i><b>' + f.a + "</b></div>";
    }
    var par = !expCompleto(f.a);
    var h = Math.max(2, Math.round(100 * f.v / mx));
    return '<div class="sb' + (par ? " parcial" : "") + '" title="' +
      esc(expEt(f.a) + "\n\nFOB: US$ " + nf(f.v) +
          "\nExportadores: " + nf(f.emp) +
          "\nOperaciones: " + nf(f.ops) + "\n" + expPie(f.a)) +
      '"><i style="height:' + h + '%"></i><b>' + f.a +
      (par ? "*" : "") + "</b></div>";
  }).join("") + "</div>";
}

function vistaExportacion() {
  Promise.all([cargar("exportaciones/mercado"),
               cargar("exportaciones/exportadores_min")])
    .then(function (r) {
      EXPM = r[0];
      EXPE = r[1].emp;
      /* Se abre en el último año completo, no en el año en curso: un año a
         medias de titular invita a compararlo con años enteros. */
      var completos = EXPM.anios_con_dato.filter(function (a) {
        return !expEnCurso(a) && expCompleto(a); });
      EXPQ.anio = completos[completos.length - 1] || EXPM.anio_en_curso;

      var sel = document.getElementById("expAnio");
      sel.innerHTML = EXPM.anios_pedidos.map(function (a) {
        return '<option value="' + a + '"' +
          (a === EXPQ.anio ? " selected" : "") + ">" + expEt(a) + "</option>";
      }).join("");
      sel.onchange = function () { EXPQ.anio = sel.value; pintarExpAnio(); };

      REPINTAR.exportacion = function () { pintarExportacion(); };
      pintarExportacion();
      pintarAcopio();
    }).catch(fallo);
}

function pintarExportacion() {
  var y = EXPQ.anio, yoy = EXPM.yoy;

  document.getElementById("expKpis").innerHTML = [
    [usd(EXPM.por_anio[y] ? EXPM.por_anio[y].fob : 0),
     "agroexportado en " + expEt(y), expPie(y)],
    [nf(EXPM.empresas_con_dato), "exportadores con RUC",
     "en " + EXPM.anios_con_dato.length + " años medidos"],
    [nf(EXPM.familias.length), "familias de producto",
     "a cuatro dígitos de partida"],
    [yoy ? (yoy.variacion_pct >= 0 ? "+" : "") + nf(yoy.variacion_pct, 1) + "%"
         : "N/D",
     yoy ? yoy.tramo.replace("-", " a ") + " de " + yoy.anios[1] : "variación",
     yoy ? "contra " + yoy.anios[0] + ", solo meses cerrados" : ""],
  ].map(function (k) { return kpi(esc(k[0]), k[1], k[2]); }).join("");

  // El total no coincide con el oficial y hay que decirlo donde se lee la
  // cifra, no en una nota al pie: es la diferencia entre publicar una
  // medición y publicarla como si fuera la estadística del país.
  var _ofi = 15013, _a = "2025";
  var _nuestro = EXPM.por_anio[_a] ? EXPM.por_anio[_a].fob / 1e6 : 0;
  document.getElementById("expAviso").innerHTML = _nuestro ?
    "<span class='h'>Este total no coincide con el oficial, y por cuánto</span>" +
    "MIDAGRI publica <b>US$ 15,013 MM</b> de agroexportación para " + _a +
    " y aquí sale <b>" + usd(_nuestro * 1e6) + "</b>, un <b>" +
    nf(Math.abs(100 * (_nuestro - _ofi) / _ofi), 0) + "% menos</b>. " +
    "Contrastarlo contra esa cifra destapó que <b>SUNAT republica cada " +
    "declaración con el valor rectificado</b>: en " + _a + " el 51% del " +
    "valor estaba repetido entre semanas, y sumarlo contaba varias veces el " +
    "mismo embarque. Lo que resta está medido y es el universo: faltan " +
    "capítulos que esta plataforma no cuenta como agro —aceites US$ 802 MM, " +
    "preparaciones de cereales 308, quinua 181, pisco 167, esencias 141—, y " +
    "con ellos sumaría <b>US$ 15,206 MM</b>, un 1.3% de la cifra oficial. " +
    "Los dos mayores que quedan fuera —alimento para animales y " +
    "preparaciones de carne— son harina de pescado y conservas." : "";

  expSerie(document.getElementById("expSerie"), EXPM.anios_pedidos);
  document.getElementById("expSerieNota").innerHTML =
    "El asterisco marca el año que no está completo. El último embarque " +
    "registrado es del " + esc(EXPM.ultimo_registro) + ", pero la serie solo " +
    "se puede leer hasta el <b>" + esc(EXPM.rezago.frontera_completitud) +
    "</b>: el embarque se declara al salir y el archivo se arma cuando la " +
    "declaración se regulariza, " + EXPM.rezago.mediana + " días después en " +
    "la mediana. Lo posterior a esa fecha está incompleto por rezago, no " +
    "porque haya caído.";

  /* El corte territorial no depende del año elegido: se calcula sobre los
     años en que el manifiesto trae el ubigeo, y decir cuáles son es parte
     del dato. */
  var dep = EXPM.departamentos, du = dep.anios_usados;
  var ult = du[du.length - 1];
  document.getElementById("expDepEt").textContent =
    "Ubigeo del manifiesto · " + du[0] + "–" + ult;
  tabla(document.getElementById("tExpDeps"), [
    { k: "n", t: "Departamento", l: 1, f: function (r) {
        return "<b>" + esc(depNom(r.n)) + "</b><span class='sub2'>" +
          nf(r.empresas) + " empresas</span>"; } },
    { k: "fob", t: "FOB " + du[0] + "–" + ult, f: function (r) {
        return usd(r.fob); } },
    { k: "pct", t: "% del total", f: function (r) { return pct(r.pct, 1); } },
    { k: "pico", t: "Mes pico", v: expPico, f: function (r) {
        var i = expPico(r);
        return i < 0 ? "—" : "<span class='tag'>" + MESES_EXP[i] + "</span>" +
          "<span class='sub2'>" + pct(r.perfil[i], 0) + " de su año</span>"; } },
  ], dep.lista, { sort: "fob" });

  var cob = dep.cobertura_fob_por_anio;
  document.getElementById("expDepNota").innerHTML =
    "<span class='h'>Fundo, no oficina — y por cuánto tiempo</span>" +
    "El ubigeo del manifiesto no es el domicilio fiscal: cruzado contra el " +
    "padrón de SUNAT sobre " + ult + " coincide en el distrito el 26.6% de " +
    "las veces y en el departamento el 48.8%, y donde el manifiesto dice Ica " +
    "o La Libertad el padrón dice Lima. Apunta al lugar de producción, que " +
    "es el dato que sirve para ubicar demanda de insumo. <b>Pero SUNAT lo " +
    "está dejando de llenar</b>: viene en el " + pct(cob[ult], 0) + " del " +
    "FOB en " + ult + " y en el " + pct(cob[EXPM.anio_en_curso], 1) + " en " +
    EXPM.anio_en_curso + ", así que el corte se limita a " + du[0] + "–" +
    ult + " y no se extiende a los demás años.";

  pintarExpAnio();
}

/* Lo que sí depende del año elegido: quién embarcó y cuánto. La composición
   por producto y destino se muestra acumulada de los cinco años —es lo que
   `mercado.json` trae sumado— y se etiqueta como tal, en vez de recortarla a
   un año que el archivo no separa. */
function pintarExpAnio() {
  var y = EXPQ.anio;
  var rango = EXPM.anios_con_dato[0] + "–" +
              EXPM.anios_con_dato[EXPM.anios_con_dato.length - 1];
  document.getElementById("expAnioPie").textContent = expPie(y);

  barras(document.getElementById("expFamilias"),
    EXPM.familias.slice(0, 12).map(function (r) {
      return { n: r.n, v: r.fob, t: usd(r.fob), p: r.pct };
    }));
  document.getElementById("expFamEt").textContent = "Acumulado " + rango;

  barras(document.getElementById("expDestinos"),
    EXPM.destinos.slice(0, 12).map(function (r) {
      return { n: pais(r.n), v: r.fob, t: usd(r.fob), p: r.pct };
    }));
  document.getElementById("expDestEt").textContent = "Acumulado " + rango;

  var filas = EXPE.filter(function (e) { return (e.a[y] || 0) > 0; });
  document.getElementById("expTopEt").textContent =
    nf(filas.length) + " con embarque en " + expEt(y) + " · 100 mayores";
  tabla(document.getElementById("tExpEmpresas"), [
    { k: "n", t: "Empresa", l: 1, f: function (r) {
        return "<b>" + esc(r.n) + "</b><span class='sub2'>" + esc(r.r) +
          (r.d ? " · " + esc(depNom(r.d)) : "") + "</span>"; } },
    { k: "fob", t: "FOB " + expEt(y), v: function (r) { return r.a[y] || 0; },
      f: function (r) { return usd(r.a[y] || 0); } },
    { k: "prod", t: "Producto principal", l: 1,
      v: function (r) { return r.f.length ? r.f[0].n : ""; },
      f: function (r) {
        return r.f.length ? "<span class='tag'>" + esc(r.f[0].n) + "</span>"
                          : "—"; } },
    { k: "dest", t: "Destino principal", l: 1,
      v: function (r) { return r.p.length ? r.p[0].n : ""; },
      f: function (r) {
        return r.p.length
          ? esc(pais(r.p[0].n)) + "<span class='sub2'>" + nf(r.np) +
            " destinos</span>" : "—"; } },
    { k: "t", t: "FOB total · " + rango, f: function (r) {
        return usd(r.t); } },
  ], filas, { sort: "fob", limite: 100 });

  document.getElementById("expNota").innerHTML =
    "Fuente: microdatos de manifiestos de SUNAT bajo la Ley 27806, " +
    nf(EXPM.operaciones) + " líneas de embarque en " +
    nf(EXPM.declaraciones) + " declaraciones, último registro " +
    esc(EXPM.ultimo_registro) + ". Nada aquí se anualiza: son años medidos. " +
    "La tabla muestra los 100 mayores del año elegido, de " +
    nf(EXPE.length) + " exportadores con RUC. Quedan fuera " +
    usd(EXPM.reservado.fob) + " en " + nf(EXPM.reservado.ops) +
    " operaciones de exportadores persona natural, cuyo titular SUNAT no " +
    "publica por la Ley 29733: están en los totales del mercado y en ningún " +
    "corte por empresa.";
}


/* ------------------------------------------------ dónde está la carga ----
   El resto de la plataforma reparte el valor exportado por el domicilio
   fiscal, que lo acumula en Lima. Este bloque lo sitúa con el ubigeo del
   manifiesto, que apunta al fundo, y por eso contesta una pregunta que las
   otras vistas no pueden: a cuánta carga llega cada centro según el radio
   que se acepte, y dónde hay carga que ningún centro alcanza. */
function pintarAcopio() {
  cargar("acopio").then(function (A) {
    var s = A.senasa || {};
    document.getElementById("expAcopioEt").textContent =
      nf(A.distritos) + " distritos · " + A.anios[0] + "–" +
      A.anios[A.anios.length - 1] + " · ubigeo del manifiesto";

    tabla(document.getElementById("tAcopioHub"), [
      { k: "hub", t: "Centro", l: 1, f: function (r) {
          return "<b>" + esc(r.hub) + "</b><span class='sub2'>" +
            nf(r.distritos) + " distritos</span>"; } },
      { k: "fob_2h_mm", t: "Alcanza a 2 h", f: function (r) {
          return usd(r.fob_2h_mm * 1e6); } },
      { k: "fob_4h_mm", t: "a 4 h", f: function (r) {
          return usd(r.fob_4h_mm * 1e6); } },
      { k: "fob_6h_mm", t: "a 6 h", f: function (r) {
          return usd(r.fob_6h_mm * 1e6); } },
    ], A.hubs, { sort: "fob_2h_mm", limite: 8 });

    var sc = A.sin_centro;
    document.getElementById("expAcopioNota").innerHTML =
      "La pregunta de inventario no es cuánto mercado hay sino cuánto se " +
      "alcanza: el mismo centro cambia de valor con el radio que se " +
      "comprometa. Y <b>" + usd(sc.fob) + " en " + sc.distritos +
      " distritos no tienen centro que los sirva</b> —" +
      sc.mayores.slice(0, 2).map(function (x) {
        return esc(x.n) + " son " + usd(x.fob); }).join(", ") +
      "—: no es carga cero, es carga fuera de alcance. Y hay otra brecha, " +
      "más grande: <b>" + usd(A.huerfanos.fob) + " en " +
      A.huerfanos.distritos + " distritos (" + nf(A.huerfanos.pct, 0) +
      "%)</b> no caen en ninguno de los 57 territorios de venta, que se " +
      "trazaron sobre la densidad del mercado de insumos —donde la " +
      "exportación no se concentra—. Los mayores son " +
      A.huerfanos.top.slice(0, 4).map(function (x) {
        return esc(x.n); }).join(", ") + ".";

    tabla(document.getElementById("tAcopioDist"), [
      { k: "n", t: "Distrito", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b><span class='sub2'>" + esc(r.dep) +
            " · pico " + esc(r.mes) + "</span>"; } },
      { k: "fob", t: "FOB", f: function (r) { return usd(r.fob); } },
      { k: "empresas", t: "Empresas", f: function (r) {
          return nf(r.empresas); } },
    ], A.top_distritos, { sort: "fob", limite: 10 });

    tabla(document.getElementById("tAcopioTer"), [
      { k: "n", t: "Territorio", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b><span class='sub2'>" +
            nf(r.cartera) + " en cartera · " + nf(r.importadores) +
            " importadores</span>"; } },
      { k: "fob", t: "FOB export", f: function (r) { return usd(r.fob); } },
      { k: "empresas_export", t: "Exportadores", f: function (r) {
          return nf(r.empresas_export); } },
    ], A.territorios, { sort: "fob", limite: 10 });

    /* Las plantas certificadas no ubican nada —SENASA da región y nada más
       fino— pero dicen quién tiene infraestructura de acopio, que es lo que
       separa a un socio posible de una razón social. */
    if (s.empacadoras) {
      var reg = Object.keys(s.por_region || {}).slice(0, 4).join(", ");
      document.getElementById("expSenasa").innerHTML =
        "<span class='h'>Quién tiene planta, y quién no la usa para exportar</span>" +
        "SENASA certifica establecimientos por producto y mercado: hay <b>" +
        nf(s.empacadoras) + " plantas de empaque</b> y " +
        nf(s.lugares_produccion) + " lugares de producción en las listas de " +
        esc((A.senasa_cobertura || {productos: []}).productos.join(", ")) +
        ". De las plantas, <b>" +
        nf(s.sin_embarque_propio) + " no embarcan a su nombre</b>: tienen " +
        "acopio y venden por medio de terceros, que es el perfil de un socio " +
        "logístico. Están sobre todo en " + esc(reg) + ". Los fundos " +
        "certificados no son socios: son demanda de insumo con certificación " +
        "encima. Estas listas no ubican —traen región y nada más fino—, así " +
        "que se usan como atributo sobre empresas que el manifiesto ya sitúa. " +
        "De " + esc((A.senasa_cobertura || {sin_lista: []}).sin_lista.join(" y ")) +
        " SENASA publica solo los protocolos por mercado, sin lista de " +
        "establecimientos: de esos dos no se sabe quién tiene planta, pero el " +
        "manifiesto sí los sitúa.";
      /* Y se sitúan aquí: es lo único que hay para los dos productos que la
         capa de certificación no cubre, y son 6,070 MM entre ambos. */
      var sl = A.sin_lista_senasa || {};
      var filas = [];
      Object.keys(sl).forEach(function (k) {
        sl[k].top.slice(0, 5).forEach(function (t) {
          filas.push({prod: k, n: t.n, dep: t.dep, fob: t.fob,
                      empresas: t.empresas,
                      hub: t.hub || "sin centro",
                      horas: t.horas === null ? 99 : t.horas});
        });
      });
      if (filas.length) {
        var cont = document.getElementById("expSinLista");
        cont.innerHTML = "<div class='eyebrow'>Uva y espárrago · dónde están, " +
          "según el manifiesto</div><div class='tw'><table id='tSinLista'></table></div>" +
          "<p class='sub'>" + esc(Object.keys(sl).map(function (k) {
            return k + ": " + sl[k].salvedad; }).join(" · ")) + "</p>";
        tabla(document.getElementById("tSinLista"), [
          { k: "prod", t: "Producto", l: 1, f: function (r) {
              return "<span class='tag'>" + esc(r.prod) + "</span>"; } },
          { k: "n", t: "Distrito", l: 1, f: function (r) {
              return "<b>" + esc(r.n) + "</b><span class='sub2'>" +
                esc(r.dep) + "</span>"; } },
          { k: "fob", t: "FOB", f: function (r) { return usd(r.fob); } },
          { k: "empresas", t: "Empresas", f: function (r) {
              return nf(r.empresas); } },
          { k: "horas", t: "Al centro", f: function (r) {
              return r.horas === 99 ? "—" : nf(r.horas, 1) + " h"; } },
        ], filas, { sort: "fob" });
      }
    }
  }).catch(fallo);
}


/* ------------------------------- la ficha, del lado exportador ----------
   La ficha traía la exportación de la ventana de diez semanas, que es lo
   único que había cuando se escribió. Hoy existen cinco años medidos y el
   recorte pesa 1.25 MB: se pide aquí y no en la portada, igual que la capa
   histórica de importación.

   Y trae algo que la ventana de diez semanas no podía dar: el origen
   declarado en el manifiesto, que apunta al fundo y no al domicilio fiscal.
   Por eso una empresa con oficina en Lima aparece aquí en La Libertad. */
function pintarPerfilExport(ruc) {
  var caja = document.getElementById("empExpHist");
  if (!caja) return;
  cargar("exportaciones/exportadores_min").then(function (D) {
    var e = (D.emp || []).filter(function (x) { return x.r === ruc; })[0];
    if (!e) {
      caja.innerHTML = "";
      return;
    }
    var m = D.meta, anios = m.anios;
    var serie = anios.map(function (a) {
      return {a: a, v: e.a[a] || 0, hay: e.a[a] !== undefined};
    });
    var mx = Math.max.apply(null, serie.map(function (s) { return s.v; })) || 1;

    caja.innerHTML =
      '<div class="card" style="margin-top:16px">' +
      '<div class="h"><h3>Cinco años de embarques</h3>' +
      '<span class="eyebrow">' + esc(anios[0]) + "–" +
      esc(anios[anios.length - 1]) + " · manifiesto de SUNAT</span></div>" +
      '<div class="b">' +
      '<div class="kpis">' +
      kpi(usd(e.t), "FOB exportado", "medido, no anualizado") +
      kpi(nf(e.np), e.np === 1 ? "destino" : "destinos",
          e.f.length ? e.f[0].n : "") +
      kpi(e.d ? esc(depNom(e.d)) : "—", "origen declarado",
          e.d ? "ubigeo del manifiesto, no domicilio fiscal"
              : "sin ubigeo en el manifiesto") +
      kpi(esc(e.de) + " → " + esc(e.ha), "primer y último embarque",
          nf(e.o) + " operaciones") +
      "</div>" +
      '<div class="serie" style="margin-top:14px">' +
      serie.map(function (s) {
        var h = Math.max(2, Math.round(100 * s.v / mx));
        if (!s.hay) {
          return '<div class="sb vacio" title="' + esc(s.a +
            "\n\nsin embarque en este año") + '"><i></i><b>' + s.a +
            "</b></div>";
        }
        return '<div class="sb" title="' + esc(s.a + "\n\nFOB: " + usd(s.v)) +
          '"><i style="height:' + h + '%"></i><b>' + s.a + "</b></div>";
      }).join("") + "</div>" +
      '<div class="grid2" style="margin-top:22px">' +
      '<div class="sub-card"><div class="eyebrow">Qué embarca</div>' +
      '<div class="barras compact" id="empExpFam"></div></div>' +
      '<div class="sub-card"><div class="eyebrow">A dónde</div>' +
      '<div class="barras compact" id="empExpPais"></div></div>' +
      "</div>" +
      '<p class="sub">FOB de exportación registrado en aduanas: no es ' +
      "facturación ni ventas. El último mes de la serie está incompleto por " +
      "el rezago de regularización, así que " + esc(anios[anios.length - 1]) +
      " no se compara con un año cerrado.</p>" +
      "</div></div>";

    barras(document.getElementById("empExpFam"), e.f.map(function (x) {
      return {n: x.n, v: x.v, t: usd(x.v)}; }));
    barras(document.getElementById("empExpPais"), e.p.map(function (x) {
      return {n: pais(x.n), v: x.v, t: usd(x.v)}; }));
  }).catch(function () { caja.innerHTML = ""; });
}

/* ------------------------------------------------------------ navegación -*/
function fallo(e) {
  console.error(e);
  document.querySelectorAll(".load").forEach(function (n) {
    n.textContent = "No se pudieron cargar los datos. Recarga la página.";
  });
}

var CARGADO = {};
function ir(hash) {
  var id = (hash || "#resumen").replace("#", "");
  /* El perfil no es una vista mas: lleva el RUC en el propio hash, de modo
     que cada empresa tiene su direccion y se comparte como cualquier pagina. */
  var mE = /^empresa=(\d+)$/.exec(id);
  if (mE) {
    document.querySelectorAll(".view").forEach(function (v) {
      v.classList.toggle("on", v.id === "v-empresa"); });
    document.querySelectorAll("nav a").forEach(function (a) {
      a.classList.toggle("on", a.getAttribute("href") === "#empresas"); });
    vistaEmpresa(mE[1]);
    return;
  }
  if (!document.getElementById("v-" + id)) id = "resumen";
  document.querySelectorAll(".view").forEach(function (v) {
    v.classList.toggle("on", v.id === "v-" + id); });
  document.querySelectorAll("nav a").forEach(function (a) {
    a.classList.toggle("on", a.getAttribute("href") === "#" + id); });

  var slot = document.querySelector("#v-" + id + " .mapaslot");
  if (slot) mapaEn(slot.id, slot.dataset.hash);

  if (!CARGADO[id]) {
    CARGADO[id] = true;
    if (id === "territorios") vistaTerritorios();
    if (id === "empresas") vistaEmpresas();
    if (id === "estacionalidad") vistaEstacionalidad();
    if (id === "departamentos") vistaDepartamentos();
    if (id === "comercio") vistaComercio();
    if (id === "productos") vistaProductos();
    if (id === "importacion") vistaImportacion();
    if (id === "exportacion") vistaExportacion();
    if (id === "logistica") vistaLogistica();
    if (id === "metodo") vistaMetodo();
  }
}
window.addEventListener("hashchange", function () { ir(location.hash); });

vistaResumen();
ir(location.hash);
window.addEventListener("resize", function () {
  if (cache.resumen) cache.resumen.then(function (D) { dibujarCurva(D.curva); });
});
})();
