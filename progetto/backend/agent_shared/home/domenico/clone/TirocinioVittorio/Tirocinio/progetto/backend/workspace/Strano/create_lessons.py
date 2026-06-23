#!/usr/bin/env python3
"""Helper to create lessons for microlearning course."""
import json, sys, os

WORKSPACE = "/home/domenico/clone/TirocinioVittorio/Tirocinio/progetto/backend/workspace/Strano"

with open(os.path.join(WORKSPACE, "reports/corso_plan.json")) as f:
    data = json.load(f)

pts = data["punti_taglio"]

if len(sys.argv) > 1:
    start = int(sys.argv[1])
    end = int(sys.argv[2]) if len(sys.argv) > 2 else start + 10
else:
    start = 0
    end = 20

for p in pts[start:end]:
    segs = p.get("segmenti_fonte", [])
    sources = [s.get("source_id", "?") for s in segs]
    print(f"  {p['id']} (ord={p['ordine']}): {p['titolo'][:80]} | src={set(sources)} | seg={len(segs)}")
    for s in segs:
        print(f"    -> {s.get('source_id','?')[:40]}: righe {s.get('riga_inizio','?')}-{s.get('riga_fine','?')}")