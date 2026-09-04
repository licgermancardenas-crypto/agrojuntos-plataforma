# -*- coding: utf-8 -*-
"""Give the operable territories a shape.

The clustering already decided which H3 cells belong to the same sales zone and
`clusters_territorio.csv` reports each zone's market, clients and extent -- but
as a table. On the plate a territory has to be an area the reader can point at
and say "that is one route".

The shape is the union of the cluster's own H3 cells, not a hull around their
centroids: the cells are the unit the clustering actually ran on, so their union
is the territory rather than an approximation of it. A convex hull would have
swallowed the ridge between two valleys and claimed market that is not there.

Input is `clusters_celda.csv`, written by build_clusters.py in the same run as
`clusters_territorio.csv`, so the cluster ids match. (`clusters_sector.csv` in
out/ is an orphan from an earlier design and no current script writes it.)
"""
import os

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon

AEA = ("+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 +x_0=0 +y_0=0 "
       "+ellps=aust_SA +units=m +no_defs")

# Cells that only touch at a vertex leave hairline slivers in the union; a
# buffer of a few hundred metres out and back closes them without moving the
# outline anywhere a reader could measure.
SUAVIZAR_M = 400


def celda(h):
    """H3 cell to polygon. h3 v4 hands back (lat, lng); shapely wants (x, y)."""
    b = h3.cell_to_boundary(h)
    return Polygon([(lng, lat) for lat, lng in b])


def main():
    cel = pd.read_csv("out/clusters_celda.csv", encoding="utf-8-sig")
    ter = pd.read_csv("out/clusters_territorio.csv", encoding="utf-8-sig")
    cel = cel[cel.cluster >= 0]

    g = gpd.GeoDataFrame(cel, geometry=[celda(h) for h in cel.h3], crs=4326)
    g = g.to_crs(AEA)

    disuelto = g.dissolve(by="cluster", aggfunc={"sam_usd": "sum",
                                                 "clientes": "sum",
                                                 "h3": "size"})
    disuelto = disuelto.rename(columns={"h3": "celdas"}).reset_index()
    disuelto["geometry"] = (disuelto.geometry
                            .buffer(SUAVIZAR_M).buffer(-SUAVIZAR_M))

    # keep only the clusters the model promoted to territories, and carry their
    # ranking, extent and day-trip verdict across
    meta = ter.set_index("cluster")[["rank", "dep", "provincias", "pct_sam",
                                     "extension_km", "horas_capital",
                                     "visitable_en_dia", "sam_por_cliente"]]
    t = disuelto.join(meta, on="cluster", how="inner").to_crs(4326)
    t.to_file("out/territorios.gpkg", driver="GPKG", layer="territorios")

    ok = int(t.visitable_en_dia.astype(bool).sum())
    print(f"{len(t)} territorios de {len(ter)} en la tabla  ->  "
          f"out/territorios.gpkg")
    print(f"  {ok} visitables en un dia de ruta, {len(t) - ok} no")
    print(f"  cubren US$ {t.sam_usd.sum()/1e6:,.0f} MM y "
          f"{t.clientes.sum():,.0f} clientes")
    print(f"  regiones con territorio propio: {t.dep.nunique()} de 24")


if __name__ == "__main__":
    main()
