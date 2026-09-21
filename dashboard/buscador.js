/* Buscador global de AgroJuntos, compartido por el sitio y por el atlas.

   Vive en su propio archivo porque las dos paginas lo necesitan y solo una
   carga `app.js`. Duplicarlo habria garantizado que un dia divergieran: el
   sitio buscaria una cosa y el mapa otra.

   No sabe nada de ninguna de las dos paginas. Recibe como quiera cargar los
   datos y que hacer con lo elegido, y eso es todo lo que las distingue:

     montarBuscador({
       cargar: function (nombre) -> Promise del JSON,
       irA:    function (destino, item) -> navega
     })

   El indice sale entero de `empresas.json`, que ya trae los cuatro catalogos
   -empresas, regiones, provincias y territorios- y la correspondencia entre
   ellos. Se construye la primera vez que se abre el buscador y no antes: son
   dos megas y no se le cobran a quien no busca.
*/
(function (global) {
"use strict";

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}
function slug(s) {
  return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "");
}

var OPTS = {};
var BUSCA = null;
var BUSCA_CARGANDO = null;

function normalizar(s) {
  return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function construirIndice(E) {
  var c = E.campos;
  var iRuc = c.indexOf("ruc"), iNom = c.indexOf("nombre");
  var iDep = c.indexOf("dep"), iProv = c.indexOf("prov"), iTer = c.indexOf("territorio");
  var items = [];

  E.filas.forEach(function (f) {
    items.push({ t: "empresa", n: f[iNom], sub: f[iRuc], ruc: f[iRuc] });
  });

  E.deps.forEach(function (n) {
    items.push({ t: "region", n: n, sub: "región", k: slug(n) });
  });

  /* Provincia con su departamento, tomado de las filas: el mapa las direcciona
     como «departamento-provincia» y sin el par no se puede construir el
     enlace. */
  var vistas = {};
  E.filas.forEach(function (f) {
    var d = E.deps[f[iDep]], p = E.provs[f[iProv]];
    if (!d || !p) return;
    var clave = d + "|" + p;
    if (vistas[clave]) return;
    vistas[clave] = 1;
    items.push({ t: "provincia", n: p, sub: d,
                 k: slug(d) + "-" + slug(p) });
  });

  (E.ters || []).forEach(function (n, i) {
    var rk = (E.ters_rank || [])[i];
    if (!rk) return;
    items.push({ t: "territorio", n: n, sub: "territorio " + rk, rank: rk });
  });

  items.forEach(function (x) { x.norm = normalizar(x.n); });
  return items;
}

function indice() {
  if (BUSCA) return Promise.resolve(BUSCA);
  if (!BUSCA_CARGANDO) {
    BUSCA_CARGANDO = OPTS.cargar("empresas").then(function (E) {
      BUSCA = construirIndice(E);
      return BUSCA;
    });
  }
  return BUSCA_CARGANDO;
}

var GRUPOS_BUSCA = [
  ["empresa", "Empresas"], ["region", "Regiones"],
  ["provincia", "Provincias"], ["territorio", "Territorios"]
];
var TOPE_GRUPO = 6;

function buscar(items, q) {
  var n = normalizar(q.trim());
  if (!n) return [];
  var soloDigitos = /^\d+$/.test(n);
  var out = [];
  for (var i = 0; i < items.length && out.length < 400; i++) {
    var x = items[i], p = -1;
    if (soloDigitos && x.ruc) {
      if (x.ruc.indexOf(n) === 0) p = 0;
      else if (x.ruc.indexOf(n) > 0) p = 2;
    }
    if (p < 0) {
      var k = x.norm.indexOf(n);
      /* Empezar por lo buscado pesa más que contenerlo: quien escribe «agro»
         quiere AGROVISION antes que CORPORACION AGROLATINA. */
      if (k === 0) p = 0;
      else if (k > 0) p = x.norm[k - 1] === " " ? 1 : 3;
    }
    if (p >= 0) out.push({ x: x, p: p });
  }
  out.sort(function (a, b) {
    return a.p - b.p || a.x.n.length - b.x.n.length ||
           a.x.n.localeCompare(b.x.n, "es");
  });
  return out.map(function (r) { return r.x; });
}

/* Posición del primer resultado de un tipo dentro de la lista ya ordenada por
   calidad. Si el tipo no aparece, va al final. */
function primero(lista, tipo) {
  for (var i = 0; i < lista.length; i++) if (lista[i].t === tipo) return i;
  return 1e9;
}

/* El destino de cada resultado es una direccion, no una llamada a una funcion.
   Asi el resultado se puede copiar, compartir y volver a abrir, y el buscador
   no necesita saber como esta hecha la pagina que lo hospeda: quien la conoce
   es `irA`, que llega por parametro. */
function destinoDe(x) {
  if (x.t === "empresa") return "#empresa=" + x.ruc;
  if (x.t === "region") return "#departamentos/" + x.k;
  if (x.t === "provincia") return "/mapa#prov=" + x.k;
  return "/mapa#ter=" + x.rank;
}

function montarBuscador(opts) {
  OPTS = opts || {};
  var caja = document.getElementById("buscador");
  var campo = document.getElementById("bq");
  var res = document.getElementById("bres");
  var cuenta = document.getElementById("bCuenta");
  var abrir = document.getElementById("bAbrir");
  if (!caja || !campo || !res) return;

  var sel = 0, actuales = [], devolverFoco = null;

  function pintar(lista, aviso, orden) {
    actuales = lista;
    if (aviso) { res.innerHTML = '<p class="bvacio">' + esc(aviso) + "</p>"; return; }
    if (!lista.length) {
      res.innerHTML = '<p class="bvacio">Sin resultados.</p>';
      cuenta.textContent = "";
      return;
    }
    var html = "", i = 0;
    (orden || GRUPOS_BUSCA).forEach(function (g) {
      var del = lista.filter(function (x) { return x.t === g[0]; });
      if (!del.length) return;
      html += '<div class="bgrupo">' + g[1] + "</div>";
      del.forEach(function (x) {
        var idx = lista.indexOf(x);
        html += '<button class="bitem" role="option" type="button" data-i="' + idx +
          '" aria-selected="' + (idx === sel) + '">' +
          '<span class="bn">' + esc(x.n) + "</span>" +
          '<span class="' + (x.t === "empresa" ? "bruc" : "bs") + '">' +
          esc(x.sub) + "</span></button>";
        i++;
      });
    });
    res.innerHTML = html;
    cuenta.textContent = lista.length + (lista.length === 1 ? " resultado" : " resultados");
    res.querySelectorAll(".bitem").forEach(function (b) {
      b.onclick = function () { elegir(+b.dataset.i); };
    });
  }

  function marcar() {
    res.querySelectorAll(".bitem").forEach(function (b) {
      var on = +b.dataset.i === sel;
      b.setAttribute("aria-selected", String(on));
      if (on) b.scrollIntoView({ block: "nearest" });
    });
  }

  function elegir(i) {
    var x = actuales[i];
    if (!x) return;
    cerrar();
    OPTS.irA(destinoDe(x), x);
  }

  function consultar() {
    var q = campo.value;
    if (!q.trim()) { sel = 0; pintar([], "Escribe para buscar."); cuenta.textContent = ""; return; }
    if (!BUSCA) {
      pintar([], "Cargando el índice…");
      indice().then(function () { if (caja.hasAttribute("hidden")) return; consultar(); });
      return;
    }
    sel = 0;
    var todo = buscar(BUSCA, q);

    /* El orden de los grupos lo decide la calidad de la coincidencia, no una
       jerarquía fija. Hay veinticinco mil empresas y veinticuatro regiones, así
       que con orden fijo «Junín» aparecía debajo de seis razones sociales que
       apenas contienen la palabra. Manda quien tenga la mejor coincidencia. */
    var orden = GRUPOS_BUSCA.slice().sort(function (a, b) {
      return primero(todo, a[0]) - primero(todo, b[0]);
    });

    /* Y se recorta por grupo, para que una consulta con mil empresas no
       entierre la única provincia que coincide. */
    var lista = [];
    orden.forEach(function (g) {
      lista = lista.concat(todo.filter(function (x) { return x.t === g[0]; })
                               .slice(0, TOPE_GRUPO));
    });
    pintar(lista, null, orden);
  }

  function abrirBuscador() {
    devolverFoco = document.activeElement;
    caja.removeAttribute("hidden");
    campo.value = "";
    pintar([], "Escribe para buscar.");
    cuenta.textContent = "";
    campo.focus();
    indice();
  }

  function cerrar() {
    caja.setAttribute("hidden", "");
    if (devolverFoco && devolverFoco.focus) devolverFoco.focus();
  }

  campo.addEventListener("input", consultar);
  campo.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); if (sel < actuales.length - 1) { sel++; marcar(); } }
    else if (e.key === "ArrowUp") { e.preventDefault(); if (sel > 0) { sel--; marcar(); } }
    else if (e.key === "Enter") { e.preventDefault(); elegir(sel); }
    else if (e.key === "Escape") { e.preventDefault(); cerrar(); }
  });
  caja.querySelectorAll("[data-cerrar]").forEach(function (el) {
    el.onclick = cerrar;
  });
  if (abrir) abrir.onclick = abrirBuscador;

  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      if (caja.hasAttribute("hidden")) abrirBuscador(); else cerrar();
    }
  });
}
global.montarBuscador = montarBuscador;
})(window);
