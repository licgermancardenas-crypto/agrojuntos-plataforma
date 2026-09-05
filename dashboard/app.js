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
      { k: "d2h", t: "Cartera a <2 h", f: function (r) {
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
  US: "Estados Unidos", NL: "Países Bajos", ES: "España", GB: "Reino Unido",
  MX: "México", CN: "China", CL: "Chile", EC: "Ecuador", CO: "Colombia",
  BR: "Brasil", CA: "Canadá", DE: "Alemania", BE: "Bélgica", FR: "Francia",
  IT: "Italia", RU: "Rusia", JP: "Japón", KR: "Corea del Sur", HK: "Hong Kong",
  AR: "Argentina", BO: "Bolivia", PA: "Panamá", CR: "Costa Rica",
  IL: "Israel", IN: "India", ID: "Indonesia", MA: "Marruecos", EG: "Egipto",
  SA: "Arabia Saudita", QA: "Catar", OM: "Omán", AE: "Emiratos Árabes",
  NO: "Noruega", SE: "Suecia", FI: "Finlandia", DK: "Dinamarca",
  PL: "Polonia", TR: "Turquía", UA: "Ucrania", LT: "Lituania",
  BY: "Bielorrusia", JO: "Jordania", TH: "Tailandia", VN: "Vietnam",
  AU: "Australia", NZ: "Nueva Zelanda", ZA: "Sudáfrica", PT: "Portugal",
  CH: "Suiza", TW: "Taiwán", MY: "Malasia", SG: "Singapur", GT: "Guatemala",
  DO: "R. Dominicana", CU: "Cuba", PY: "Paraguay", UY: "Uruguay",
  VE: "Venezuela", NI: "Nicaragua", HN: "Honduras", SV: "El Salvador"
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
function vistaComercio() {
  cargar("comercio").then(function (D) {
    var m = D.meta;
    REPINTAR.comercio = function () { pintarComercio(D); };
    pintarComercio(D);
  }).catch(fallo);
}

function pintarComercio(D) {
  var m = D.meta, si = m.semanas_imp, se = m.semanas_exp;
    document.getElementById("comKpis").innerHTML = [
      ["v", pFob(m.fob_imp, si), "insumos importados",
       pSuf(si) + ", desde " + si + " semanas medidas"],
      ["v", nf(m.n_imp), "importadores de insumos", "con RUC identificado"],
      ["v", pFob(m.fob_exp, se), "agroexportación",
       pSuf(se) + ", capítulos 07–21"],
      ["v", nf(m.n_exp), "agroexportadores", "empresas distintas"],
    ].map(function (k) {
      return "<div><span class='v'>" + k[1] + "</span><span class='l'>" +
        k[2] + "</span><span class='s'>" + k[3] + "</span></div>";
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
      D.destinos.slice(0, 12).map(function (r) {
        return { n: pais(r.n), v: r.fob, t: pFob(r.fob, se) };
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

    tabla(document.getElementById("tExportadores"), [
      { k: "n", t: "Empresa", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b><span class='sub2'>" + r.r +
            (r.dep ? " · " + esc(r.dep) : "") + "</span>"; } },
      { k: "fob", t: "FOB " + pSuf(se), f: function (r) {
          return pFob(r.fob, se); } },
      { k: "tn", t: "Toneladas", f: function (r) { return pNum(r.tn, se); } },
      { k: "dest", t: "Destinos", f: function (r) { return nf(r.dest); } },
    ], D.exportadores, { sort: "fob" });

    document.getElementById("comNota").innerHTML =
      "Fuente: microdatos de manifiestos de SUNAT, publicados bajo la Ley " +
      "27806 de transparencia. Lo medido son " + m.semanas_imp +
      " semanas; el mensual y el anual extrapolan esa ventana sin corregir " +
      "estacionalidad y deben leerse como orden de magnitud, no como el " +
      "cierre del año. La agroexportación se restringe a los capítulos " +
      "arancelarios 07, 08, 09, 12, 18, 20 y 21: el archivo de aduanas trae " +
      "la exportación completa del país, donde el mineral de cobre y el oro " +
      "por sí solos son el 60% del FOB.";
}

/* ------------------------------------------------------------- logistica -- */
function vistaLogistica() {
  cargar("logistica").then(function (D) {
    tabla(document.getElementById("tLogistica"), [
      { k: "n", t: "Departamento", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b>"; } },
      { k: "sam", t: "Mercado", f: function (r) { return usd(r.sam); } },
      { k: "real", t: "Horas reales", f: function (r) {
          return r.real === null ? "—" : nf(r.real, 1) + " h"; } },
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

    document.getElementById("logNota").innerHTML =
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
function vistaProductos() {
  cargar("productos").then(function (D) {
    REPINTAR.productos = function () { pintarProductos(D); };
    pintarProductos(D);
  }).catch(fallo);
}

function pintarProductos(D) {
    var m = D.meta, SEM = m.semanas, anual = pFactor(SEM);
    var dep = "";                       // "" = todo el país

    document.getElementById("proKpis").innerHTML = [
      [nf(m.ha), "hectáreas cosechadas", "en " + nf(m.cultivos) + " cultivos"],
      [D.cultivos[0].n, "mayor superficie", nf(D.cultivos[0].ha) + " ha"],
      [pFob(m.fob_exp, SEM), "agroexportación " + pSuf(SEM),
       usd(m.fob_exp) + " medidos en " + SEM + " semanas"],
      [D.aduanas[0].n, "principal salida", pct(100 * D.aduanas[0].fob /
       m.fob_exp, 0) + " del FOB"],
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

      var ex = dep ? (D.exp_por_dep[dep] || []) : null;
      titE.textContent = dep ? "Qué exporta " + dep : "Qué se exporta del país";
      var fuente = ex || D.productos.slice(0, 6).map(function (p) {
        return { n: p.n, v: p.fob, tn: p.tn }; });
      if (!fuente.length) {
        document.getElementById("proExpDep").innerHTML =
          "<p class='sub'>Sin agroexportación registrada en las " +
          m.semanas + " semanas publicadas.</p>";
      } else {
        barras(document.getElementById("proExpDep"),
          fuente.map(function (p) {
            return { n: p.n, v: p.v, t: usd(p.v * anual) }; }));
      }

      var fila = D.exp_dep.filter(function (r) { return r.n === dep; })[0];
      document.getElementById("proExpNota").innerHTML = dep
        ? (fila
            ? "<b>" + nf(fila.emp) + "</b> empresas exportan desde " + esc(dep) +
              ", " + usd(fila.fob * anual) + " al año. La ubicación es el " +
              "domicilio fiscal declarado ante SUNAT, no necesariamente donde " +
              "está el fundo."
            : "Ninguna empresa con domicilio fiscal en " + esc(dep) +
              " registra agroexportación en el periodo.")
        : "La superficie es de MIDAGRI y el FOB de SUNAT: miden cosas " +
          "distintas —hectáreas y dólares embarcados— y no se suman entre sí.";

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
    tabla(document.getElementById("tProductos"), [
      { k: "n", t: "Producto", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b><span class='sub2'>partida " +
            r.p + "</span>"; } },
      { k: "fob", t: "FOB " + pSuf(SEM), f: function (r) {
          return pFob(r.fob, SEM); } },
      { k: "tn", t: "Toneladas " + pSuf(SEM), f: function (r) {
          return pNum(r.tn, SEM); } },
      { k: "emp", t: "Empresas", f: function (r) { return nf(r.emp); } },
      { k: "dest", t: "Destinos", f: function (r) { return nf(r.dest); } },
    ], D.productos, { sort: "fob" });

    /* ---- por dónde sale ---- */
    tabla(document.getElementById("tAduanas"), [
      { k: "n", t: "Aduana", l: 1, f: function (r) {
          return "<b>" + esc(r.n) + "</b><span class='sub2'>código " +
            r.c + "</span>"; } },
      { k: "via", t: "Vía", l: 1, f: function (r) {
          return "<span class='tag'>" + esc(r.via) + "</span>"; } },
      { k: "fob", t: "FOB " + pSuf(SEM), f: function (r) {
          return pFob(r.fob, SEM); } },
      { k: "tn", t: "Toneladas " + pSuf(SEM), f: function (r) {
          return pNum(r.tn, SEM); } },
      { k: "emp", t: "Empresas", f: function (r) { return nf(r.emp); } },
      { k: "lider", t: "Producto principal", l: 1, f: function (r) {
          return esc(r.lider) + "<span class='sub2'>" + pct(r.pct, 1) +
            " de su FOB</span>"; } },
    ], D.aduanas, { sort: "fob" });

    /* La mezcla de producto de cada aduana explica por qué existe: Paita es
       café, Pisco es uva. Se despliega al pulsar la fila. */
    var tA = document.getElementById("tAduanas");
    tA.onclick = function (ev) {
      var tr = ev.target.closest("tbody tr");
      if (!tr) return;
      var nombre = (tr.querySelector("td.l b") || {}).textContent;
      var a = D.aduanas.filter(function (x) { return x.n === nombre; })[0];
      if (!a) return;
      var mezcla = D.exp_por_adu[a.n] || [];
      document.getElementById("proAduDet").innerHTML =
        "<div class='eyebrow'>Mezcla de producto · " + esc(a.n) + "</div>" +
        "<div class='barras compact' id='proMez'></div>";
      barras(document.getElementById("proMez"), mezcla.map(function (p) {
        return { n: p.n, v: p.v, t: usd(p.v * anual) }; }));
    };

    document.getElementById("proNota").innerHTML =
      "Superficie cosechada del anuario de producción agrícola de MIDAGRI " +
      "(2023); agroexportación de los microdatos de manifiestos de SUNAT bajo " +
      "la Ley 27806, anualizando " + m.semanas + " semanas. La aduana de " +
      "salida sale del campo <span class='mono'>CADU</span> del manifiesto y " +
      "se nombra con la Tabla 4 del Anexo 01 de SUNAT; el código 370 " +
      "corresponde a Chancay, habilitada el 21 de octubre de 2024 y todavía " +
      "ausente de ese anexo. El reparto por departamento usa el domicilio " +
      "fiscal del exportador, porque el ubigeo del propio manifiesto viene " +
      "vacío en el 97% del FOB.";
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
