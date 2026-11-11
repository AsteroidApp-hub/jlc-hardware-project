#!/usr/bin/env python3
"""基板の部品配置を JSON に書き出す (KiCad 同梱 Python で実行)。tools/handover.py から呼ばれる。

使い方: <KiCad python> tools/dump_pcb.py <出力.json>
"""
import json, os, sys
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from project import PROJECT  # noqa: E402
OX, OY = 100.0, 80.0
b = pcbnew.LoadBoard(os.path.join(ROOT, "kicad", PROJECT + ".kicad_pcb"))
T = pcbnew.ToMM
out = []
for fp in b.GetFootprints():
    try:
        cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        if cy.GetWidth() == 0:
            raise ValueError
    except Exception:
        cy = fp.GetBoundingBox(False, False)
    pads = []
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        pads.append(dict(num=p.GetNumber(), x=T(p.GetPosition().x) - OX, y=T(p.GetPosition().y) - OY,
                         w=T(bb.GetWidth()), h=T(bb.GetHeight()),
                         tht=p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH,
                         rect=p.GetShape(pcbnew.F_Cu) in (pcbnew.PAD_SHAPE_RECTANGLE, pcbnew.PAD_SHAPE_ROUNDRECT)
                         if hasattr(pcbnew, "PAD_SHAPE_RECTANGLE") else False))
    out.append(dict(ref=fp.GetReference(), value=fp.GetValue(), fp=fp.GetFPIDAsString(),
                    x=T(fp.GetPosition().x) - OX, y=T(fp.GetPosition().y) - OY, rot=fp.GetOrientationDegrees(),
                    box=[T(cy.GetLeft()) - OX, T(cy.GetTop()) - OY, T(cy.GetRight()) - OX, T(cy.GetBottom()) - OY],
                    pads=pads))
json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=0)
print(len(out), "footprints")
