#!/usr/bin/env python3
"""Regenerate both master CSVs from the VAP source used by the live maps."""
import csv
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
html = (root / "west-end-map.html").read_text(encoding="utf-8")

def dataset(name):
    match = re.search(r"const " + re.escape(name) + r" = (\{.*?\});\s*\n", html, re.S)
    if not match:
        raise SystemExit(f"Missing {name}")
    return json.loads(match.group(1))["features"]

features = dataset("DATA_METRO")
boundaries = dataset("DATA_NEIGHBORHOODS")
names = {"RUSSELL", "SHAWNEE", "PORTLAND", "CHICKASAW", "PARKLAND",
         "CALIFORNIA", "PARK HILL", "ALGONQUIN", "TAYLOR BERRY"}
polygons = [f for f in boundaries if str(f["properties"].get("name", "")).upper() in names]
if len(polygons) != 9:
    raise SystemExit("Expected nine West End neighborhood boundaries")

def ring_contains(pt, ring):
    inside = False
    for i in range(len(ring)):
        a, b = ring[i], ring[i-1]
        if (a[1] > pt[1]) != (b[1] > pt[1]):
            if pt[0] < (b[0]-a[0]) * (pt[1]-a[1]) / (b[1]-a[1]) + a[0]:
                inside = not inside
    return inside

def contains(pt, geometry):
    typ = geometry.get("type")
    groups = [geometry["coordinates"]] if typ == "Polygon" else geometry["coordinates"] if typ == "MultiPolygon" else []
    return any(rings and ring_contains(pt, rings[0]) and not any(ring_contains(pt, hole) for hole in rings[1:]) for rings in groups)

fields = ["address","owner","neighborhood","zoning","parcel_type","latitude","longitude","link_label","property_link","link_type","source_snapshot"]
portal = "https://public-lky.epropertyplus.com/landmgmtpub/app/base/propertySearch"
lba, west = [], []
for f in features:
    p = f.get("properties") or {}
    xy = (f.get("geometry") or {}).get("coordinates")
    if not xy or len(xy) < 2:
        continue
    hood = next((poly["properties"]["name"] for poly in polygons if contains(xy, poly["geometry"])), None)
    row = dict(address=p.get("address", ""), owner=p.get("owner", ""),
               neighborhood=hood or p.get("neighborhood", ""), zoning=p.get("zone", ""),
               parcel_type=p.get("parcel_type", ""), latitude=xy[1], longitude=xy[0],
               link_label="VIEW Property", property_link=portal, link_type="portal_search",
               source_snapshot="2026 VAP source snapshot")
    if p.get("owner") == "Landbank Authority":
        lba.append(row)
    if hood:
        west.append(row)

def write(path, rows):
    rows.sort(key=lambda r: r["address"])
    with (root / path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

write("data/lba-master.csv", lba)
write("data/metro-landbank-west-master.csv", west)
print(f"LBA citywide: {len(lba)}; West End combined: {len(west)}")
if len(lba) < 200 or len(west) < 250:
    raise SystemExit("Unexpectedly low source counts; review before committing")
