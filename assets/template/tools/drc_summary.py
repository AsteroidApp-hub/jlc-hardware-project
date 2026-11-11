#!/usr/bin/env python3
"""kicad-cli pcb drc --format json の結果を要約する。 使い方: drc_summary.py drc.json [--all]"""
import collections, json, sys
d = json.load(open(sys.argv[1]))
skip = set() if "--all" in sys.argv else {"silk_overlap", "silk_over_copper", "silk_edge_clearance"}
for key in ("violations", "unconnected_items", "schematic_parity"):
    items = d.get(key, [])
    print(key, len(items), dict(collections.Counter(v.get("type") for v in items)))
    seen = collections.Counter()
    for v in items:
        if v["type"] in skip:
            continue
        seen[v["type"]] += 1
        if seen[v["type"]] <= 6:
            print("   [%s] %s | %s" % (v["type"], v.get("description", "")[:70],
                                       " / ".join(i.get("description", "")[:45] for i in v.get("items", []))))
