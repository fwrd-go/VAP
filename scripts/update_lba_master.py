#!/usr/bin/env python3
"""Regenerate the LBA master CSV from the latest Citywide VAP source snapshot.
Update citywide-base.html with a verified fresh Metro/Landbank extract before running.
Does not imply an address is currently advertised for sale.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "citywide-base.html").read_text(encoding="utf-8")
match = re.search(r"const DATA_METRO = (\{.*?\});\s*\n", source, re.S)
if not match:
    raise SystemExit("DATA_METRO source not found")
features = json.loads(match.group(1))["features"]
rows = []
for feature in features:
    p = feature.get("properties") or {}
    if p.get("owner") != "Landbank Authority":
        continue
    coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
    rows.append({
        "address": p.get("address", ""),
        "owner": p.get("owner", ""),
        "neighborhood": p.get("neighborhood", ""),
        "zoning": p.get("zone", ""),
        "parcel_type": p.get("parcel_type", ""),
        "latitude": coords[1],
        "longitude": coords[0],
        "link_label": "VIEW Property",
        "property_link": "https://public-lky.epropertyplus.com/landmgmtpub/app/base/propertySearch",
        "link_type": "portal_search",
        "source_snapshot": "2026 VAP source snapshot",
    })
rows.sort(key=lambda x: x["address"])
out = ROOT / "data" / "lba-master.csv"
with out.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [
        "address","owner","neighborhood","zoning","parcel_type","latitude","longitude",
        "link_label","property_link","link_type","source_snapshot"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Wrote {len(rows)} LBA properties to {out}")
