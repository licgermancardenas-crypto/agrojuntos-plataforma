# -*- coding: utf-8 -*-
"""List the customs archives SUNAT currently publishes, from the page's own hrefs.

The filenames encode a week as ddDDmmyy and are not derivable from a date
range, so they are read off the index page rather than generated.
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

h = io.open("data/bases.html", encoding="latin-1").read()
hrefs = re.findall(r'href="([^"]*informae[^"]*\.zip)"', h, re.I)

archivos = sorted({os.path.basename(u.replace("\\", "/")) for u in hrefs})
print(f"archivos publicados: {len(archivos)}")

# ma = importación formato A, x = exportación. mb/idv/mam are complementary.
quiero = [a for a in archivos if re.match(r"^(ma|x)\d{8}\.zip$", a, re.I)]
print(f"importacion + exportacion: {len(quiero)}")
with open("data/aduanas/archivos.txt", "w") as fh:
    fh.write("\n".join(quiero))
for a in quiero:
    print("  ", a)
