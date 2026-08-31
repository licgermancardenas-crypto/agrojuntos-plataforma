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
      { k: "horas", t: "Horas centro", f: function (r) { return nf(r.horas, 1); } },
      { k: "ext", t: "Extensión km", f: function (r) { return nf(r.ext); } },
      { k: "dia", t: "Ruta", l: true, f: function (r) {
          return r.dia ? '<span class="tag P">un día</span>'
                       : '<span class="tag">pernocte</span>'; } }
    ], T, { sort: "rank", asc: true });
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
        s: (f[1] + " " + f[0] + " " + dep + " " + prov)
             .normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      };
    });
    EMP = { d: D, filas: filas, clase: -1, reg: "", q: "" };

    var sel = document.getElementById("fReg");
    sel.innerHTML = '<option value="">Todas las regiones</option>' +
      D.deps.map(function (r) {
        return '<option value="' + esc(r) + '">' + esc(r) + "</option>"; }).join("");

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
    if (EMP.q && r.s.indexOf(EMP.q) < 0) return false;
    return true;
  });
  document.getElementById("cCount").textContent =
    nf(f.length) + " de " + nf(EMP.filas.length) +
    (f.length > 400 ? " · se muestran 400" : "");

  tabla(document.getElementById("tEmpresas"), [
    { k: "n", t: "Razón social", l: true, cls: "name",
      f: function (r) { return esc(r.n); } },
    { k: "ruc", t: "RUC", l: true, f: function (r) {
        return '<span class="mono">' + r.ruc + "</span>"; } },
    { k: "c", t: "Clase", l: true, f: function (r) {
        return '<span class="tag ' + CL[r.c] + '">' +
               esc(EMP.d.clases[r.c]) + "</span>"; } },
    { k: "dep", t: "Región", l: true, f: function (r) { return esc(r.dep); } },
    { k: "prov", t: "Provincia", l: true, f: function (r) { return esc(r.prov); } },
    { k: "x", t: "Exporta US$/año", f: function (r) {
        return r.x ? usd(r.x) : "—"; } },
    { k: "i", t: "Importa US$/año", f: function (r) {
        return r.i ? usd(r.i) : "—"; } }
  ], f, { sort: "x", limite: 400 });
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
  if (!document.getElementById("v-" + id)) id = "resumen";
  document.querySelectorAll(".view").forEach(function (v) {
    v.classList.toggle("on", v.id === "v-" + id); });
  document.querySelectorAll("nav a").forEach(function (a) {
    a.classList.toggle("on", a.getAttribute("href") === "#" + id); });

  if (!CARGADO[id]) {
    CARGADO[id] = true;
    if (id === "territorios") vistaTerritorios();
    if (id === "empresas") vistaEmpresas();
    if (id === "estacionalidad") vistaEstacionalidad();
  }
}
window.addEventListener("hashchange", function () { ir(location.hash); });

vistaResumen();
ir(location.hash);
window.addEventListener("resize", function () {
  if (cache.resumen) cache.resumen.then(function (D) { dibujarCurva(D.curva); });
});
})();
