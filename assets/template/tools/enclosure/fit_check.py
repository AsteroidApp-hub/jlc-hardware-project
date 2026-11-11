#!/usr/bin/env python3
"""基板 (KiCad から書き出した STEP) を筐体に組み込んで干渉と高さを確認する。

使い方: kicad-cli pcb export step --subst-models -o board.step kicad/P48_2CH.kicad_pcb
        python3 tools/enclosure/fit_check.py board.step [Neutrik STEP フォルダ]
"""
import json, os, sys
from build123d import import_step, Location, Compound
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_enclosure as E

board_step = sys.argv[1]
neutrik = sys.argv[2] if len(sys.argv) > 2 else ""
bottom, feats = E.make_bottom()
cover = E.make_cover()
b = import_step(board_step)
bb = b.bounding_box()
print("board STEP bbox", [round(v, 1) for v in bb.min], [round(v, 1) for v in bb.max])
# KiCad STEP: x = KiCad X, y = -KiCad Y, z: 基板下面 = 0 (KiCad座標 = 基板座標 + (100, 80))
# 筐体: x = bx + 5.5, y = 88.5 - by, z = PCB_BOT + z
loc = Location((E.PCB_X[0] - 100.0, E.PCB_Y[1] + 80.0, E.PCB_BOT))
b = b.moved(loc)
bb = b.bounding_box()
print("board in enclosure bbox", [round(v, 1) for v in bb.min], [round(v, 1) for v in bb.max])
solids = b.solids()
print("solids:", len(solids))
top_inner = E.HB            # 天板下面の高さ
res = []
for i, so in enumerate(solids):
    sb = so.bounding_box()
    hits = []
    for name, part in (("bottom", bottom), ("cover", cover)):
        r = so & part
        v = 0.0 if r is None else r.volume
        if v > 0.01:
            hits.append((name, round(v, 2)))
    res.append(dict(i=i, zmax=round(sb.max.Z, 2), x=(round(sb.min.X, 1), round(sb.max.X, 1)),
                    y=(round(sb.min.Y, 1), round(sb.max.Y, 1)), hits=hits))
tall = sorted(res, key=lambda r: -r["zmax"])[:8]
print("inner top z =", top_inner)
print("tallest solids:")
for r in tall:
    print("  z_max %.2f (clearance %.2f)  x %s y %s %s" % (r["zmax"], top_inner - r["zmax"], r["x"], r["y"], r["hits"]))
bad = [r for r in res if r["hits"]]
print("solids touching enclosure:", len(bad))
for r in bad:
    print("  ", r)

# ---- 組立プレビュー (基板 + XLR を筐体に入れた状態)
try:
    import numpy as np
    import pyvista as pv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
except ImportError:
    sys.exit(0)
for f in ("Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans JP", "Noto Sans CJK JP"):
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
pv.OFF_SCREEN = True


def tomesh(shp):
    allp, allf, off = [], [], 0
    for fc in shp.faces():
        v, tri = [], []
        for tol in ((0.15, 0.3), (0.4, 0.6), (1.0, 1.0)):
            try:
                v, tri = fc.tessellate(*tol)
                break
            except Exception:
                pass
        if not tri:
            continue
        allp += [(p.X, p.Y, p.Z) for p in v]
        allf += [[3, a + off, b_ + off, c + off] for a, b_, c in tri]
        off += len(v)
    return pv.PolyData(np.array(allp), np.array(allf, dtype=np.int64).ravel()).compute_normals(split_vertices=True,
                                                                                             feature_angle=35)


xlrs = []
if neutrik and os.path.isdir(neutrik):
    fm = import_step(os.path.join(neutrik, "nc3faah2.stp"))
    mm_ = import_step(os.path.join(neutrik, "nc3maah1.stp"))
    for ch, xc in E.XLR_X.items():
        xlrs += [E.place_neutrik(fm, "front", xc), E.place_neutrik(mm_, "rear", xc)]
m_bottom, m_cover = tomesh(bottom), tomesh(cover)
m_board = [tomesh(s) for s in solids]
m_x = [tomesh(s) for s in xlrs]
imgs = []
for title, cam, closed in (("カバーを外した状態 (前から)", (-40, -95, 150), False),
                           ("カバーを外した状態 (後ろから)", (150, 200, 150), False),
                           ("完成状態", (-95, -150, 95), True)):
    pl = pv.Plotter(off_screen=True, window_size=(1000, 760))
    pl.set_background("white")
    pl.add_mesh(m_bottom, color="#c9ced4", specular=0.4)
    if closed:
        pl.add_mesh(m_cover, color="#2b2f36", specular=0.3)
    for k, m in enumerate(m_board):
        bbz = solids[k].bounding_box()
        thin = bbz.max.Z - bbz.min.Z < 1.8 and bbz.max.X - bbz.min.X > 50
        pl.add_mesh(m, color="#1f6f3a" if thin else "#5b6470", specular=0.2)
    for m in m_x:
        pl.add_mesh(m, color="#1d1d1d", specular=0.2)
    pl.camera_position = [cam, (E.X / 2, E.Y / 2, 12), (0, 0, 1)]
    pl.camera.zoom(1.3)
    pl.enable_anti_aliasing("ssaa")
    imgs.append((title, pl.screenshot(return_img=True)))
    pl.close()
fig, axs = plt.subplots(1, 3, figsize=(17, 5))
for ax, (title, img) in zip(axs, imgs):
    ax.imshow(img); ax.set_title(title); ax.axis("off")
fig.suptitle("P48 2CH  基板と筐体の組立確認 (XLRはNeutrik公式3Dモデル)", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(E.OUT, "組立プレビュー.png"), dpi=110)
print("saved", os.path.join(E.OUT, "組立プレビュー.png"))
