# -*- coding: utf-8 -*-
"""Visual system for the printed report.

The register is institutional research: a document that has to survive being
printed, passed across a table and read by someone deciding where to put money.
That drives three choices.

Type carries authority through contrast, not decoration: a text serif
(Newsreader) for headings and pull quotes, a neutral grotesque (IBM Plex Sans)
for running text and labels, and a monospace (IBM Plex Mono) wherever digits
must line up in a column.

Colour is deliberately narrow. One deep forest green does all the structural
work — rules, section marks, filled headers — and a single brass accent marks
the few things the reader must not miss. Everything else is a warm-neutral grey
so the maps, which are the only saturated objects on the page, keep their
weight.

The grid is a 12-column field with a wide outer margin, which leaves room for
marginal notes and keeps measure near 65 characters.
"""

FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;"
         "1,6..72,400&family=IBM+Plex+Mono:wght@400;500;600&"
         "family=IBM+Plex+Sans:wght@400;500;600&display=swap")

CSS = """
@page { size:A4; margin:18mm 16mm 15mm; }
/* Full-bleed sheets need their own named page: a 297 mm block inside the
   default margin box spills onto a second sheet. */
@page bleed { size:A4; margin:0; }
.cover, .divider { page:bleed; }

*{box-sizing:border-box; margin:0; padding:0}
:root{
  --ink:#0F1A16;        /* text */
  --ink2:#37443E;       /* secondary text */
  --muted:#6E7872;      /* labels, captions */
  --faint:#9AA39D;
  --line:#D5DBD2;
  --line2:#E8EBE4;
  --paper:#FFFFFF;
  --surf:#F6F8F3;       /* table zebra, cards */
  --forest:#0F4C3F;     /* structural brand colour */
  --forest2:#16624F;
  --brass:#B07D2E;      /* the one accent */
  --brass-soft:#FBF3E4;
  --sky:#2E6E8E;
  --danger:#A34A25;
  --costa:#C1873F; --sierra:#3E7F93; --salta:#5D9330; --sbaja:#1F6B4C;
}
html{-webkit-print-color-adjust:exact; print-color-adjust:exact}
body{
  font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;
  font-size:9pt; line-height:1.55; color:var(--ink); background:var(--paper);
  font-feature-settings:"kern" 1,"liga" 1;
}
h1,h2,h3,h4,.serif{font-family:Newsreader,Georgia,"Times New Roman",serif}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums}

/* ---------------------------------------------------------------- pages -- */
.page{page-break-after:always; display:flex; flex-direction:column;
  min-height:252mm; position:relative}
.page:last-child{page-break-after:auto}
.bleed{page-break-after:always; height:297mm; width:210mm; position:relative;
  overflow:hidden}

/* running head */
.rh{display:flex; justify-content:space-between; align-items:baseline;
  border-bottom:.6pt solid var(--line); padding-bottom:5px; margin-bottom:16px;
  font-size:6.6pt; letter-spacing:.14em; text-transform:uppercase;
  color:var(--faint); font-family:"IBM Plex Mono",monospace}
.rh .sec{color:var(--forest); font-weight:500}

.foot{margin-top:auto; padding-top:9px; border-top:.6pt solid var(--line2);
  display:flex; justify-content:space-between; align-items:baseline;
  font-size:6.4pt; color:var(--faint);
  font-family:"IBM Plex Mono",monospace; letter-spacing:.08em}
.foot .pg{color:var(--forest); font-weight:600; font-size:8pt;
  letter-spacing:0}

/* ------------------------------------------------------------ headings -- */
.kicker{font-family:"IBM Plex Mono",monospace; font-size:6.8pt; font-weight:500;
  letter-spacing:.2em; text-transform:uppercase; color:var(--brass);
  display:block; margin-bottom:9px}
h2.title{font-size:21pt; font-weight:500; letter-spacing:-.012em;
  line-height:1.12; color:var(--ink); max-width:24ch}
h2.title em{font-style:italic; color:var(--forest)}
.deck{font-size:10.5pt; line-height:1.5; color:var(--ink2); max-width:56ch;
  margin-top:9px}
h3{font-size:11pt; font-weight:500; margin:19px 0 6px; letter-spacing:-.008em}
h3.rule{border-top:1.4pt solid var(--ink); padding-top:6px}
h4{font-family:"IBM Plex Sans",sans-serif; font-size:8pt; font-weight:600;
  letter-spacing:.02em; margin:12px 0 3px; color:var(--ink)}
h4.lab{font-family:"IBM Plex Mono",monospace; font-size:6.8pt; font-weight:500;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted);
  margin:0 0 5px}
p{margin:0 0 8px; max-width:66ch}
p:last-child{margin-bottom:0}
.sub{font-size:7.4pt; color:var(--muted); line-height:1.5; margin-top:4px}
em.i{font-family:Newsreader,serif; font-style:italic}

/* ---------------------------------------------------------------- cover -- */
.cover{height:297mm; display:flex; flex-direction:column;
  padding:26mm 20mm 18mm; position:relative; background:var(--paper)}
.cover .bar{position:absolute; top:0; left:0; right:0; height:9mm;
  background:var(--forest)}
.cover .brandline{display:flex; align-items:baseline; gap:9px;
  font-family:"IBM Plex Mono",monospace; font-size:7.4pt; letter-spacing:.22em;
  text-transform:uppercase; color:var(--forest)}
.cover .brandline span:last-child{color:var(--faint); letter-spacing:.14em}
.cover h1{font-size:40pt; font-weight:400; line-height:1.03;
  letter-spacing:-.028em; margin:16mm 0 0; max-width:15ch}
.cover h1 em{font-style:italic; color:var(--forest)}
.cover .lede{font-size:11pt; line-height:1.55; color:var(--ink2);
  max-width:50ch; margin-top:9mm}
.cover .hero{margin:auto 0; text-align:center}
.cover .hero img{max-height:132mm; width:auto}
.cover .cstats{display:grid; grid-template-columns:repeat(4,1fr);
  border-top:1.4pt solid var(--ink); margin-top:8mm}
.cover .cstats div{padding:11px 14px 0; border-right:.6pt solid var(--line)}
.cover .cstats div:last-child{border-right:0}
.cover .cstats div:first-child{padding-left:0}
.cover .cstats .v{font-family:"IBM Plex Mono",monospace; font-size:15pt;
  font-weight:600; letter-spacing:-.03em; display:block; line-height:1.1;
  color:var(--forest)}
.cover .cstats .l{font-size:6.9pt; color:var(--muted); display:block;
  margin-top:5px; line-height:1.4}
.cover .foot2{display:flex; gap:26px; margin-top:9mm; padding-top:10px;
  border-top:.6pt solid var(--line); font-size:7.4pt; color:var(--muted)}
.cover .foot2 b{display:block; color:var(--ink); font-size:8.4pt;
  font-weight:600; margin-bottom:1px; font-family:"IBM Plex Sans",sans-serif}

/* -------------------------------------------------------------- divider -- */
.divider{height:297mm; display:flex; flex-direction:column;
  justify-content:center; padding:0 20mm; background:var(--forest);
  color:#EDF2EC}
.divider .n{font-family:Newsreader,serif; font-size:82pt; font-weight:400;
  line-height:.9; color:rgba(255,255,255,.26); letter-spacing:-.04em}
.divider h2{font-size:27pt; font-weight:400; line-height:1.14;
  letter-spacing:-.018em; margin:6mm 0 0; max-width:20ch; color:#fff}
.divider h2 em{font-style:italic; color:#D8C08A}
.divider p{font-size:10.5pt; line-height:1.6; color:rgba(237,242,236,.82);
  max-width:52ch; margin-top:6mm}
.divider .idx{margin-top:12mm; padding-top:8px;
  border-top:.6pt solid rgba(255,255,255,.28); display:flex; gap:22px;
  font-family:"IBM Plex Mono",monospace; font-size:7pt; letter-spacing:.14em;
  text-transform:uppercase; color:rgba(237,242,236,.6)}

/* -------------------------------------------------------------- contents -*/
.toc{list-style:none; margin:0}
.toc li{display:flex; flex-wrap:wrap; align-items:baseline; gap:10px;
  padding:8px 0; border-bottom:.6pt solid var(--line2)}
.toc .n{font-family:"IBM Plex Mono",monospace; font-size:7.4pt;
  color:var(--brass); font-weight:600; width:22px; flex:none}
.toc .t{font-family:Newsreader,serif; font-size:11.5pt; font-weight:400;
  white-space:nowrap}
.toc .d{flex:1; border-bottom:.6pt dotted var(--line); margin:0 4px 3px}
.toc .p{font-family:"IBM Plex Mono",monospace; font-size:8pt;
  color:var(--muted)}
.toc .desc{font-size:7.6pt; color:var(--muted); width:100%; margin:2px 0 0 32px}

/* ------------------------------------------------------------------ kpi -- */
.kpis{display:grid; grid-template-columns:repeat(4,1fr);
  border-top:1.4pt solid var(--ink); border-bottom:.6pt solid var(--line);
  margin:14px 0 4px}
.kpis > div{padding:10px 13px; border-right:.6pt solid var(--line2)}
.kpis > div:last-child{border-right:0}
.kpis > div:first-child{padding-left:0}
.kpis .v{font-family:"IBM Plex Mono",monospace; font-size:14pt; font-weight:600;
  letter-spacing:-.025em; display:block; line-height:1.12; color:var(--forest)}
.kpis .l{font-size:6.8pt; color:var(--muted); display:block; margin-top:4px;
  line-height:1.4}

/* --------------------------------------------------------------- layout -- */
.two{display:grid; grid-template-columns:1fr 1fr; gap:9mm; align-items:start}
.mapl{display:grid; grid-template-columns:1.02fr 1fr; gap:9mm; align-items:start}
.mapr{display:grid; grid-template-columns:1fr 1.02fr; gap:9mm; align-items:start}
.fig{width:100%; display:block}
figure{margin:0}
figcaption{font-size:7pt; color:var(--muted); line-height:1.5; margin-top:6px;
  padding-top:5px; border-top:.6pt solid var(--line2)}
figcaption b{color:var(--ink2); font-weight:600}

/* --------------------------------------------------------------- tables -- */
table{border-collapse:collapse; width:100%; font-size:7.8pt; margin:9px 0 0}
th,td{padding:3.8px 7px}
thead th{background:var(--forest); color:#fff; font-size:6.5pt; font-weight:500;
  letter-spacing:.09em; text-transform:uppercase;
  font-family:"IBM Plex Sans",sans-serif}
thead{display:table-header-group}
tbody td{border-bottom:.6pt solid var(--line2)}
tbody tr:nth-child(even) td{background:var(--surf)}
td.r,th.r{text-align:right; font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums}
td.l,th.l{text-align:left}
tbody td:first-child{font-weight:500}
tfoot td{font-weight:600; background:#EDF1EA; border-top:1.2pt solid var(--forest);
  font-family:"IBM Plex Mono",monospace}
tfoot td.l{font-family:"IBM Plex Sans",sans-serif}
table.tight th,table.tight td{padding:3px 6px; font-size:7.4pt}

/* ------------------------------------------------------------- callouts -- */
.note{border-left:2pt solid var(--forest); background:var(--surf);
  padding:10px 13px; margin:12px 0; font-size:8.3pt; line-height:1.55}
.note.brass{border-color:var(--brass); background:var(--brass-soft)}
.note.warn{border-color:var(--danger); background:#FAF0EB}
.note b{font-weight:600}
.note p{max-width:none}
.note .h{display:block; font-family:"IBM Plex Mono",monospace; font-size:6.5pt;
  letter-spacing:.16em; text-transform:uppercase; color:var(--muted);
  margin-bottom:4px}

.cards{display:grid; gap:5mm; margin:12px 0}
.cards.c3{grid-template-columns:repeat(3,1fr)}
.cards.c2{grid-template-columns:repeat(2,1fr)}
.card{border-top:1.2pt solid var(--ink); padding-top:8px}
.card .big{font-family:"IBM Plex Mono",monospace; font-size:16pt;
  font-weight:600; letter-spacing:-.03em; display:block; line-height:1.05;
  color:var(--forest)}
.card p{font-size:7.8pt; color:var(--ink2); margin-top:5px}

ul.pts{list-style:none; margin:6px 0 0}
ul.pts li{position:relative; padding-left:15px; margin-bottom:7px;
  font-size:8.6pt; color:var(--ink2); line-height:1.5}
ul.pts li::before{content:""; position:absolute; left:0; top:.52em;
  width:5px; height:5px; background:var(--brass)}
ul.pts li b{color:var(--ink)}
ul.num{list-style:none; counter-reset:n; margin:6px 0 0}
ul.num li{counter-increment:n; position:relative; padding-left:20px;
  margin-bottom:8px; font-size:8.6pt; color:var(--ink2); line-height:1.5}
ul.num li::before{content:counter(n,decimal-leading-zero); position:absolute;
  left:0; top:.05em; font-family:"IBM Plex Mono",monospace; font-size:7pt;
  color:var(--brass); font-weight:600}

b.hl{box-shadow:inset 0 -.42em 0 #F3E4C4; font-weight:600}

/* ---------------------------------------------------------------- fiche -- */
.fiche{display:grid; grid-template-columns:56mm 1fr; gap:6mm;
  padding:4.4mm 0; border-top:1.2pt solid var(--ink); align-items:start}
.fiche:first-of-type{margin-top:1mm}
/* Department outlines differ wildly in aspect; capping the height keeps every
   row the same depth so three fiches land on one sheet. */
.fiche .mp{display:flex; justify-content:center; align-items:flex-start}
.fiche img{max-width:100%; max-height:41mm; width:auto; display:block}
.fiche .hd{display:flex; align-items:baseline; gap:9px; margin-bottom:6px}
.fiche .rk{font-family:"IBM Plex Mono",monospace; font-size:8pt; font-weight:600;
  color:#fff; background:var(--forest); padding:2px 6px; letter-spacing:0}
.fiche h3{font-family:Newsreader,serif; font-size:13.5pt; font-weight:500;
  margin:0; letter-spacing:-.01em; line-height:1}
.fiche .tag{font-family:"IBM Plex Mono",monospace; font-size:6.4pt;
  letter-spacing:.12em; text-transform:uppercase; color:var(--muted);
  margin-left:auto}
.fgrid{display:grid; grid-template-columns:repeat(4,1fr); gap:0;
  border-top:.6pt solid var(--line); border-bottom:.6pt solid var(--line);
  margin:5px 0 7px}
.fgrid div{padding:3.6px 8px 3.6px 0}
.fgrid .v{font-family:"IBM Plex Mono",monospace; font-size:9.6pt;
  font-weight:600; display:block; line-height:1.1; letter-spacing:-.02em;
  color:var(--forest)}
.fgrid .l{font-size:6.2pt; color:var(--muted); display:block; margin-top:2px;
  line-height:1.3}
.fbars{margin:0 0 6px}
.fbar{display:flex; align-items:center; gap:6px; font-size:6.6pt;
  color:var(--ink2); margin-bottom:1.8px}
.fbar .nm{width:31mm; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap}
.fbar .tr{flex:1; height:5px; background:var(--line2)}
.fbar .tr i{display:block; height:100%; background:var(--forest2)}
.fbar .vl{font-family:"IBM Plex Mono",monospace; width:15mm; text-align:right;
  color:var(--muted)}
.fread{font-size:7.2pt; color:var(--ink2); line-height:1.5;
  border-left:1.6pt solid var(--brass); padding-left:8px}
.fread b{color:var(--ink)}

/* --------------------------------------------------------------- source -- */
.srcs{list-style:none; margin:6px 0 0}
.srcs li{font-size:7.3pt; color:var(--muted); line-height:1.55;
  margin-bottom:7px; padding-left:15px; position:relative}
.srcs li::before{content:"—"; position:absolute; left:0; color:var(--brass)}
.srcs b{color:var(--ink2); font-weight:600}
"""
