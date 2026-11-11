#!/usr/bin/env python3
"""2ch P48 ファンタム電源 — 板金筐体ジェネレーター (JLCCNC 向け)

build123d (OpenCascade) で 3D モデルを作り、以下を 筐体/ に出力する。
  P48_2CH_bottom.step / P48_2CH_cover.step : 発注用 (部品ごと)
  P48_2CH_enclosure.step                      : 発注用 (2部品を組立位置で1ファイルに)
  flat_bottom.dxf / flat_cover.dxf               : 展開図 (曲げ線つき, 参考)
  silk_front.dxf / silk_rear.dxf                 : パネル印刷 (シルク) データ
  筐体図面.pdf                                   : 寸法図 + 圧入ナット指示 (JLCCNCの Riveting File 用)
  筐体プレビュー.png                             : 組立イメージ (基板・XLRの干渉確認つき)
  pcb_constraints.json                           : 基板設計 (工程4) に渡す寸法

座標系: 原点 = ボトムの 左・前・下 の外側の角。x = 幅 (右が+), y = 奥行き (前→後), z = 高さ。
"""
import json, math, os, sys
from build123d import (Box, Cylinder, Pos, Rot, Align, Compound, export_step, import_step, Location,
                       Text, Rectangle, Circle, Line, Sketch, Axis)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
from project import PROJECT  # noqa: E402
OUT = os.path.join(ROOT, "筐体")
os.makedirs(OUT, exist_ok=True)
NEUTRIK_DIR = os.environ.get("NEUTRIK_STEP_DIR", "")   # 干渉チェック用 (任意)

# ------------------------------------------------------------------ 基本寸法
T = 1.5                 # 板厚 A5052
R_IN = 1.25             # 曲げ内R (JLCCNC: 1.5mm 板の外R 2.75)
R_O = R_IN + T          # 曲げ外R
K = 0.44                # Kファクター (展開長の計算用)
BA = math.pi / 2 * (R_IN + K * T)   # 90°曲げの曲げ代

X = 107.0               # ボトム外幅 (左右の立ち上がり外面間)
Y = 91.0                # 奥行き (前後パネル外面間)
H_IN = 36.0             # 内寸高さ (底板上面〜天板下面)
HB = T + H_IN           # 前後パネルの高さ (底面から)
LIP_H = 14.0            # 左右の立ち上がり (カバー固定用) の高さ
LIP_Y = (6.0, 85.0)     # 立ち上がりの範囲 (前後の角は逃がし)
RELIEF = 1.0            # 曲げ逃がし幅
CLEAR = 0.2             # カバー側板と立ち上がりのすき間
XT0, XT1 = -CLEAR - T, X + CLEAR + T     # カバー外面の x 範囲
HT = HB + T             # 全高

STANDOFF = 6.0          # 基板スペーサー高さ
PCB_T = 1.6
PCB_BOT = T + STANDOFF
PCB_TOP = PCB_BOT + PCB_T
PCB_X = (5.5, 101.5)    # 基板外形 (立ち上がり・圧入ナット・カバー固定ねじの先端から逃がす)
PCB_Y = (T + 1.0, Y - T - 1.0)
XLR_AXIS_Z = PCB_TOP + 12.5          # Neutrik AA: 基板上面から軸まで 12.5mm (STEPモデルで確認)
XLR_HOLE = 22.5                       # パネル穴 (Neutrik: 22以上)
XLR_SCREW = 3.2                       # 取付穴 (Neutrik: 3.2以上), 対角 19.8
XLR_X = {"L": 21.0, "R": 53.0}        # チャンネルの中心 x
SW_POS = (80.0, 25.0)                 # 電源SW (MS-500K-B, M6ブッシュ)
SW_HOLE = 6.2
LED_POS = (93.0, PCB_TOP + 2.0)       # 3mm LED 横向き (フットプリント: LED中心が基板上面から2.0mm)
LED_HOLE = 3.2
DC_POS = (90.0, PCB_TOP + 6.5)        # MJ-179PH: 基板上面から中心 6.5mm
DC_HOLE = 8.5
PCB_HOLES = [(37.0, 12.0), (37.0, 79.0), (98.0, 25.5), (97.5, 70.0)]   # 基板設計 (工程4) で決定   # M3 スペーサー位置
SIDE_SCREWS = [(20.0, 8.5), (71.0, 8.5)]   # (y, z) カバー側板 ↔ 立ち上がり
NUT_HOLE = 4.2          # M3 圧入ナット (クリンチナット) の下穴
SCREW_HOLE = 3.4
FEET = [(12, 12), (95, 12), (12, 79), (95, 79)]   # ゴム足の位置 (目安)


# ------------------------------------------------------------------ 形状ヘルパー
def box(x0, x1, y0, y1, z0, z1):
    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN))


def bend_x(cy, cz, quadrant, x0, x1):
    """x方向に伸びる曲げ部 (内R R_IN, 外R R_O)。quadrant: (sy, sz) 円弧が中心から見てどちら側か"""
    tube = Pos((x0 + x1) / 2, cy, cz) * Rot(0, 90, 0) * (Cylinder(R_O, x1 - x0) - Cylinder(R_IN, x1 - x0))
    sy, sz = quadrant
    q = box(x0, x1, cy if sy > 0 else cy - R_O, cy + R_O if sy > 0 else cy,
            cz if sz > 0 else cz - R_O, cz + R_O if sz > 0 else cz)
    return tube & q


def bend_y(cx, cz, quadrant, y0, y1):
    tube = Pos(cx, (y0 + y1) / 2, cz) * Rot(90, 0, 0) * (Cylinder(R_O, y1 - y0) - Cylinder(R_IN, y1 - y0))
    sx, sz = quadrant
    q = box(cx if sx > 0 else cx - R_O, cx + R_O if sx > 0 else cx, y0, y1,
            cz if sz > 0 else cz - R_O, cz + R_O if sz > 0 else cz)
    return tube & q


def hole_y(x, z, d, y0, y1):
    """y方向の貫通穴 (前後パネル)"""
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(d / 2, abs(y1 - y0) + 2)


def hole_x(y, z, d, x0, x1):
    return Pos((x0 + x1) / 2, y, z) * Rot(0, 90, 0) * Cylinder(d / 2, abs(x1 - x0) + 2)


def hole_z(x, y, d, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(d / 2, abs(z1 - z0) + 2)


def xlr_holes(xc, zc, panel, y0, y1):
    """Neutrik AA のパネル穴。panel='front' は外から見て 左上/右下、'rear' は外から見て 左上/右下 (=グローバル右上/左下)"""
    s = 9.9
    pts = [(xc - s, zc + s), (xc + s, zc - s)] if panel == "front" else [(xc + s, zc + s), (xc - s, zc - s)]
    h = hole_y(xc, zc, XLR_HOLE, y0, y1)
    for px, pz in pts:
        h = h + hole_y(px, pz, XLR_SCREW, y0, y1)
    return h, pts


# ------------------------------------------------------------------ ボトム (底板 + 前後パネル + 左右の立ち上がり)
def make_bottom():
    y1, y2 = LIP_Y
    parts = [
        box(R_O, X - R_O, y1, y2, 0, T),                       # 底板 (立ち上がりの範囲)
        box(0, X, R_O, y1 - RELIEF, 0, T),                      # 底板 (前側)
        box(0, X, y2 + RELIEF, Y - R_O, 0, T),                  # 底板 (後側)
        box(R_O, X - R_O, y1 - RELIEF, y1, 0, T),
        box(R_O, X - R_O, y2, y2 + RELIEF, 0, T),
        bend_x(R_O, R_O, (-1, -1), 0, X), box(0, X, 0, T, R_O, HB),            # 前パネル
        bend_x(Y - R_O, R_O, (1, -1), 0, X), box(0, X, Y - T, Y, R_O, HB),     # 後パネル
        bend_y(R_O, R_O, (-1, -1), y1, y2), box(0, T, y1, y2, R_O, LIP_H),     # 左の立ち上がり
        bend_y(X - R_O, R_O, (1, -1), y1, y2), box(X - T, X, y1, y2, R_O, LIP_H),
    ]
    b = parts[0]
    for p in parts[1:]:
        b = b + p
    cuts = []
    feats = {"front": [], "rear": []}
    for ch, xc in XLR_X.items():
        h, pts = xlr_holes(xc, XLR_AXIS_Z, "front", 0, T)
        cuts.append(h)
        feats["front"].append(dict(kind="XLR-F", ch=ch, x=xc, z=XLR_AXIS_Z, d=XLR_HOLE, screws=pts))
        h, pts = xlr_holes(xc, XLR_AXIS_Z, "rear", Y - T, Y)
        cuts.append(h)
        feats["rear"].append(dict(kind="XLR-M", ch=ch, x=xc, z=XLR_AXIS_Z, d=XLR_HOLE, screws=pts))
    cuts.append(hole_y(*SW_POS, SW_HOLE, 0, T))
    feats["front"].append(dict(kind="SW", x=SW_POS[0], z=SW_POS[1], d=SW_HOLE))
    cuts.append(hole_y(*LED_POS, LED_HOLE, 0, T))
    feats["front"].append(dict(kind="LED", x=LED_POS[0], z=LED_POS[1], d=LED_HOLE))
    cuts.append(hole_y(*DC_POS, DC_HOLE, Y - T, Y))
    feats["rear"].append(dict(kind="DC", x=DC_POS[0], z=DC_POS[1], d=DC_HOLE))
    for (x, y) in PCB_HOLES:
        cuts.append(hole_z(x, y, SCREW_HOLE, 0, T))
    for (y, z) in SIDE_SCREWS:
        cuts.append(hole_x(y, z, NUT_HOLE, 0, T))
        cuts.append(hole_x(y, z, NUT_HOLE, X - T, X))
    for c in cuts:
        b = b - c
    return b, feats


# ------------------------------------------------------------------ カバー (天板 + 左右側板)
def make_cover():
    parts = [
        box(XT0 + R_O, XT1 - R_O, 0, Y, HT - T, HT),
        bend_y(XT0 + R_O, HT - R_O, (-1, 1), 0, Y), box(XT0, XT0 + T, 0, Y, 0, HT - R_O),
        bend_y(XT1 - R_O, HT - R_O, (1, 1), 0, Y), box(XT1 - T, XT1, 0, Y, 0, HT - R_O),
    ]
    c = parts[0]
    for p in parts[1:]:
        c = c + p
    for (y, z) in SIDE_SCREWS:
        c = c - hole_x(y, z, SCREW_HOLE, XT0, XT0 + T)
        c = c - hole_x(y, z, SCREW_HOLE, XT1 - T, XT1)
    return c


# ------------------------------------------------------------------ 展開図 (DXF)
def flat_patterns(feats):
    import ezdxf
    out = {}
    # --- ボトム: v 方向 = 前パネル上端(0) → 底板 → 後パネル上端
    wall = HB - R_O
    base = Y - 2 * R_O
    v_front_bend = wall
    v_base0 = wall + BA
    v_base1 = v_base0 + base
    v_rear0 = v_base1 + BA
    v_total = v_rear0 + wall
    lip = LIP_H - R_O
    u_base0 = lip + BA                      # 底板平坦部の左端 (x = R_O)
    def U(x):
        return x - R_O + u_base0
    def Vb(y):
        return v_base0 + (y - R_O)
    doc = ezdxf.new(setup=True)
    doc.layers.add("CUT", color=7)
    doc.layers.add("BEND", color=1, linetype="DASHED")
    doc.layers.add("NOTE", color=3)
    m = doc.modelspace()
    y1, y2 = LIP_Y
    outline = [
        (U(0), 0), (U(X), 0), (U(X), Vb(y1 - RELIEF)), (U(X - R_O), Vb(y1 - RELIEF)), (U(X - R_O), Vb(y1)),
        (U(X - R_O) + BA + lip, Vb(y1)), (U(X - R_O) + BA + lip, Vb(y2)), (U(X - R_O), Vb(y2)),
        (U(X - R_O), Vb(y2 + RELIEF)), (U(X), Vb(y2 + RELIEF)), (U(X), v_total), (U(0), v_total),
        (U(0), Vb(y2 + RELIEF)), (U(R_O), Vb(y2 + RELIEF)), (U(R_O), Vb(y2)), (0, Vb(y2)), (0, Vb(y1)),
        (U(R_O), Vb(y1)), (U(R_O), Vb(y1 - RELIEF)), (U(0), Vb(y1 - RELIEF)), (U(0), 0)]
    m.add_lwpolyline(outline, dxfattribs={"layer": "CUT"})
    for v in (v_front_bend + BA / 2, v_base1 + BA / 2):
        m.add_line((U(0), v), (U(X), v), dxfattribs={"layer": "BEND"})
    for u in (U(R_O) - BA / 2, U(X - R_O) + BA / 2):
        m.add_line((u, Vb(y1)), (u, Vb(y2)), dxfattribs={"layer": "BEND"})
    for f in feats["front"]:
        m.add_circle((U(f["x"]), HB - f["z"]), f["d"] / 2, dxfattribs={"layer": "CUT"})
        for (px, pz) in f.get("screws", []):
            m.add_circle((U(px), HB - pz), XLR_SCREW / 2, dxfattribs={"layer": "CUT"})
    for f in feats["rear"]:
        m.add_circle((U(f["x"]), v_rear0 + (f["z"] - R_O)), f["d"] / 2, dxfattribs={"layer": "CUT"})
        for (px, pz) in f.get("screws", []):
            m.add_circle((U(px), v_rear0 + (pz - R_O)), XLR_SCREW / 2, dxfattribs={"layer": "CUT"})
    for (x, y) in PCB_HOLES:
        m.add_circle((U(x), Vb(y)), SCREW_HOLE / 2, dxfattribs={"layer": "CUT"})
    for (y, z) in SIDE_SCREWS:
        m.add_circle((u_base0 - BA - (z - R_O), Vb(y)), NUT_HOLE / 2, dxfattribs={"layer": "CUT"})
        m.add_circle((U(X - R_O) + BA + (z - R_O), Vb(y)), NUT_HOLE / 2, dxfattribs={"layer": "CUT"})
    m.add_text(f"P48 2CH BOTTOM  A5052 t{T}  inner R{R_IN}  K={K}  (flat pattern, reference)",
               dxfattribs={"layer": "NOTE", "height": 3}).set_placement((0, -8))
    p = os.path.join(OUT, "flat_bottom.dxf")
    doc.saveas(p)
    out["bottom"] = (U(X) + lip + BA - 0, v_total)
    # --- カバー: u 方向 = 左側板下端(0) → 天板 → 右側板下端
    wallc = HT - R_O
    top = (XT1 - XT0) - 2 * R_O
    utot = wallc + BA + top + BA + wallc
    doc = ezdxf.new(setup=True)
    doc.layers.add("CUT", color=7)
    doc.layers.add("BEND", color=1, linetype="DASHED")
    doc.layers.add("NOTE", color=3)
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (utot, 0), (utot, Y), (0, Y), (0, 0)], dxfattribs={"layer": "CUT"})
    for u in (wallc + BA / 2, wallc + BA + top + BA / 2):
        m.add_line((u, 0), (u, Y), dxfattribs={"layer": "BEND"})
    for (y, z) in SIDE_SCREWS:
        m.add_circle((z, y), SCREW_HOLE / 2, dxfattribs={"layer": "CUT"})
        m.add_circle((utot - z, y), SCREW_HOLE / 2, dxfattribs={"layer": "CUT"})
    m.add_text(f"P48 2CH COVER  A5052 t{T}  inner R{R_IN}  K={K}  (flat pattern, reference)",
               dxfattribs={"layer": "NOTE", "height": 3}).set_placement((0, -8))
    doc.saveas(os.path.join(OUT, "flat_cover.dxf"))
    out["cover"] = (utot, Y)
    return out


# ------------------------------------------------------------------ パネル印刷 (シルク)
FONT = next((f for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                         "/System/Library/Fonts/Supplemental/Arial.ttf",
                         "/Library/Fonts/Arial.ttf") if os.path.exists(f)), None)

SILK = {
    # パネルを外から見た座標 (u: 左→右, w: 下→上)。前面は u = x、後面は u = X - x
    "front": [("MIC IN", 37.0, 35.3, 2.5), ("L", XLR_X["L"], 6.0, 3.5), ("R", XLR_X["R"], 6.0, 3.5),
              ("PHANTOM", SW_POS[0], 34.3, 2.4), ("ON", SW_POS[0], 31.4, 1.8), ("OFF", SW_POS[0], 18.4, 1.8),
              ("48V", LED_POS[0], LED_POS[1] + 4.0, 2.6), ("P48 2CH", 98.0, 33.6, 2.0)],
    "rear": [("OUTPUT", X - 37.0, 35.3, 2.5), ("L", X - XLR_X["L"], 6.0, 3.5), ("R", X - XLR_X["R"], 6.0, 3.5),
             ("DC 12-18V", X - DC_POS[0], DC_POS[1] + 7.5, 2.4), ("+  (o-  -", X - DC_POS[0], DC_POS[1] - 8.0, 2.2)],
}


def silk_dxf(feats):
    import ezdxf
    from build123d import Text as B3Text
    for panel in ("front", "rear"):
        doc = ezdxf.new(setup=True)
        doc.layers.add("OUTLINE", color=8)
        doc.layers.add("HOLES", color=8)
        doc.layers.add("SILK", color=7)
        m = doc.modelspace()
        m.add_lwpolyline([(0, 0), (X, 0), (X, HB), (0, HB), (0, 0)], dxfattribs={"layer": "OUTLINE"})
        for f in feats[panel]:
            u = f["x"] if panel == "front" else X - f["x"]
            m.add_circle((u, f["z"]), f["d"] / 2, dxfattribs={"layer": "HOLES"})
            for (px, pz) in f.get("screws", []):
                uu = px if panel == "front" else X - px
                m.add_circle((uu, pz), XLR_SCREW / 2, dxfattribs={"layer": "HOLES"})
        for txt, u, w, size in SILK[panel]:
            if txt.startswith("+  (o"):
                # センタープラス記号: (+)-(o-  -(-)
                cx, cy = u, w
                m.add_circle((cx, cy), 1.6, dxfattribs={"layer": "SILK"})
                m.add_circle((cx, cy), 0.5, dxfattribs={"layer": "SILK"})
                m.add_line((cx - 1.6, cy), (cx - 4.5, cy), dxfattribs={"layer": "SILK"})
                m.add_line((cx + 1.6, cy), (cx + 4.5, cy), dxfattribs={"layer": "SILK"})
                m.add_line((cx - 6.5, cy), (cx - 5.3, cy), dxfattribs={"layer": "SILK"})   # ＋
                m.add_line((cx - 5.9, cy - 0.6), (cx - 5.9, cy + 0.6), dxfattribs={"layer": "SILK"})
                m.add_line((cx + 5.3, cy), (cx + 6.5, cy), dxfattribs={"layer": "SILK"})   # −
                continue
            t = B3Text(txt, font_size=size, font_path=FONT) if FONT else B3Text(txt, font_size=size)
            bb = t.bounding_box()
            t = Pos(u - (bb.min.X + bb.max.X) / 2, w - (bb.min.Y + bb.max.Y) / 2) * t
            for face in t.faces():
                for wire in face.wires():
                    pts = [(v.X, v.Y) for v in wire.edges().vertices()]
                    for e in wire.edges():
                        n = 12 if e.geom_type != "LINE" else 1
                        seg = [e.position_at(i / n) for i in range(n + 1)]
                        m.add_lwpolyline([(p.X, p.Y) for p in seg], dxfattribs={"layer": "SILK"})
        m.add_text(f"P48 2CH {panel.upper()} PANEL - silkscreen white, double-line outline font. "
                   f"Viewed from outside. Outline {X} x {HB} mm", dxfattribs={"layer": "OUTLINE", "height": 2.5}
                   ).set_placement((0, -6))
        doc.saveas(os.path.join(OUT, f"silk_{panel}.dxf"))


# ------------------------------------------------------------------ 干渉チェック + プレビュー
def place_neutrik(model, panel, xc):
    """Neutrik STEP を組立位置へ。両モデルとも y=上, 軸=z。メス(NC3FAAH2)は +z が前方・パネルに当たる面 (ねじボスの前面) z=5.5、
    オス(NC3MAAH-1)は +z が奥・パネル面 z=0 (STEPの平面から確認)"""
    if panel == "front":       # メス: model +z → global -y
        return model.moved(Location((xc, T + 5.5, XLR_AXIS_Z), (90, 0, 0)))
    else:                      # オス: model +z → global -y (箱の内側へ)
        return model.moved(Location((xc, Y - T, XLR_AXIS_Z), (90, 0, 0)))


def preview(bottom, cover, feats):
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from matplotlib import font_manager
    for f in ("Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP"):
        if any(f in x.name for x in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = f
            break
    pcb = box(PCB_X[0], PCB_X[1], PCB_Y[0], PCB_Y[1], PCB_BOT, PCB_TOP)
    for (x, y) in PCB_HOLES:
        pcb = pcb - hole_z(x, y, 3.2, PCB_BOT, PCB_TOP)
    spacers = [Pos(x, y, T + STANDOFF / 2) * Cylinder(2.75, STANDOFF) for (x, y) in PCB_HOLES]
    xlrs, report = [], []
    if NEUTRIK_DIR and os.path.isdir(NEUTRIK_DIR):
        f_model = import_step(os.path.join(NEUTRIK_DIR, "nc3faah2.stp"))
        m_model = import_step(os.path.join(NEUTRIK_DIR, "nc3maah1.stp"))
        for ch, xc in XLR_X.items():
            for panel, mdl in (("front", f_model), ("rear", m_model)):
                s = place_neutrik(mdl, panel, xc)
                xlrs.append(s)
                def ov(a, b):
                    r = a & b
                    return 0.0 if r is None else r.volume
                vb = ov(s, bottom)
                vc = ov(s, cover)
                bb = s.bounding_box()
                report.append(dict(xlr=f"{panel}-{ch}", overlap_bottom_mm3=round(vb, 2), overlap_cover_mm3=round(vc, 2),
                                   z_top=round(bb.max.Z, 2), z_bottom_body=round(bb.min.Z, 2),
                                   y_range=(round(bb.min.Y, 2), round(bb.max.Y, 2))))
    # 3D 描画 (PyVista/VTK)。なければ省略
    try:
        import pyvista as pv
    except ImportError:
        print("pyvista がないためプレビュー画像は省略")
        return report
    pv.OFF_SCREEN = True

    def tomesh(shp):
        """面ごとに三角形分割 (分割できない面は飛ばす)"""
        allp, allf, off = [], [], 0
        for fc in shp.faces():
            for tol in ((0.15, 0.3), (0.4, 0.6), (1.0, 1.0)):
                try:
                    v, tri = fc.tessellate(*tol)
                    break
                except Exception:
                    v, tri = [], []
            if not tri:
                continue
            allp += [(p.X, p.Y, p.Z) for p in v]
            allf += [[3, a + off, b + off, c + off] for a, b, c in tri]
            off += len(v)
        mesh_ = pv.PolyData(np.array(allp), np.array(allf, dtype=np.int64).ravel())
        return mesh_.compute_normals(split_vertices=True, feature_angle=35)

    m_bottom, m_cover, m_pcb = tomesh(bottom), tomesh(cover), tomesh(pcb)
    m_sp = [tomesh(s) for s in spacers]
    m_x = [tomesh(s) for s in xlrs]
    alu = dict(color="#c9ced4", specular=0.4, specular_power=20, smooth_shading=False)
    black = dict(color="#2b2f36", specular=0.3, smooth_shading=False)
    views = [("前面 (閉じた状態)", [(-95, -150, 95)], True),
             ("背面 (閉じた状態)", [(205, 260, 95)], True),
             ("カバーを外した内部", [(-60, -110, 170)], False)]
    imgs = []
    for title, cams, closed in views:
        pl = pv.Plotter(off_screen=True, window_size=(900, 680))
        pl.set_background("white")
        pl.add_mesh(m_bottom, **alu)
        if closed:
            pl.add_mesh(m_cover, **black)
        else:
            pl.add_mesh(m_pcb, color="#1f6f3a", smooth_shading=False)
            for m in m_sp:
                pl.add_mesh(m, color="#9a9a9a")
        for m in m_x:
            pl.add_mesh(m, color="#1d1d1d", specular=0.2)
        pl.camera_position = [cams[0], (X / 2, Y / 2, 15), (0, 0, 1)]
        pl.camera.zoom(1.25)
        pl.enable_anti_aliasing("ssaa")
        imgs.append((title, pl.screenshot(return_img=True)))
        pl.close()
    fig, axs = plt.subplots(1, 3, figsize=(16, 4.6))
    for ax, (title, img) in zip(axs, imgs):
        ax.imshow(img); ax.set_title(title); ax.axis("off")
    fig.suptitle(f"P48 2CH 筐体  外形 {XT1 - XT0:.1f} × {Y:.1f} × {HT:.1f} mm  (A5052 t{T})", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "筐体プレビュー.png"), dpi=120)
    plt.close(fig)
    return report


# ------------------------------------------------------------------ 寸法図 (PDF)
def drawing(feats, flats):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Circle as MCircle, Rectangle as MRect
    from matplotlib import font_manager
    for f in ("Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP"):
        if any(f in x.name for x in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = f
            break
    plt.rcParams.update({"font.size": 7})

    def panel(ax, name, items, mirror):
        ax.add_patch(MRect((0, 0), X, HB, fill=False, lw=1))
        ax.axhline(PCB_TOP, color="g", lw=0.5, ls=":")
        ax.text(X + 1, PCB_TOP, f"PCB top z={PCB_TOP:.1f}", color="g", va="center")
        for f in items:
            u = X - f["x"] if mirror else f["x"]
            ax.add_patch(MCircle((u, f["z"]), f["d"] / 2, fill=False, lw=0.8))
            lab = {"XLR-F": "XLR NC3FAAH2", "XLR-M": "XLR NC3MAAH-1", "SW": "PHANTOM SW MS-500A-B", "LED": "LED 3mm",
                   "DC": "DC jack MJ-179PH"}[f["kind"]]
            ax.annotate(f"{lab}\nØ{f['d']}  ({u:.1f}, {f['z']:.1f})", (u, f["z"]), xytext=(u, f["z"] + f["d"] / 2 + 3),
                        ha="center", fontsize=6)
            for (px, pz) in f.get("screws", []):
                uu = X - px if mirror else px
                ax.add_patch(MCircle((uu, pz), XLR_SCREW / 2, fill=False, lw=0.6))
                ax.text(uu, pz - 3.2, f"Ø{XLR_SCREW}\n({uu:.1f},{pz:.1f})", ha="center", fontsize=5)
        ax.set_xlim(-8, X + 22); ax.set_ylim(-8, HB + 8); ax.set_aspect("equal")
        ax.set_title(f"{name} — viewed from OUTSIDE  (width {X}, height {HB}, origin = lower-left outer corner)")
        ax.axis("off")

    with PdfPages(os.path.join(OUT, "筐体図面.pdf")) as pdf:
        fig, axs = plt.subplots(2, 1, figsize=(11.69, 8.27))
        panel(axs[0], "FRONT PANEL (bottom part)", feats["front"], False)
        panel(axs[1], "REAR PANEL (bottom part)", feats["rear"], True)
        fig.suptitle("P48 2CH enclosure — panel holes", fontsize=10)
        pdf.savefig(fig); plt.close(fig)

        fig, axs = plt.subplots(1, 2, figsize=(11.69, 8.27))
        ax = axs[0]
        ax.add_patch(MRect((0, 0), X, Y, fill=False, lw=1))
        ax.add_patch(MRect((PCB_X[0], PCB_Y[0]), PCB_X[1] - PCB_X[0], PCB_Y[1] - PCB_Y[0], fill=False, lw=0.6,
                           ls="--", ec="g"))
        ax.text(PCB_X[0] + 1, PCB_Y[1] - 4, f"PCB {PCB_X[1]-PCB_X[0]:.0f} x {PCB_Y[1]-PCB_Y[0]:.0f}", color="g")
        for (x, y) in PCB_HOLES:
            ax.add_patch(MCircle((x, y), SCREW_HOLE / 2, fill=False))
            ax.text(x + 2.5, y, f"Ø{SCREW_HOLE} ({x:.0f},{y:.0f})", fontsize=6, va="center")
        for (x, y) in FEET:
            ax.add_patch(MCircle((x, y), 5, fill=False, ls=":", ec="gray"))
        for (y, z) in SIDE_SCREWS:
            for xx, dx in ((0, -1), (X, 1)):
                ax.plot([xx, xx + dx * 6], [y, y], color="r", lw=0.8)
                ax.text(xx + dx * 7, y, f"M3 press nut\ny={y:.0f}, z={z:.0f}", color="r", fontsize=6,
                        ha="left" if dx > 0 else "right", va="center")
        ax.set_xlim(-25, X + 25); ax.set_ylim(-8, Y + 8); ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(f"BOTTOM — top view (base {X} x {Y}). Front panel at y=0. Side lips h={LIP_H}, y={LIP_Y[0]}..{LIP_Y[1]}")
        ax = axs[1]
        ax.axis("off")
        notes = [
            "2CH P48 PHANTOM POWER ENCLOSURE",
            "",
            f"Material: Aluminium 5052, t = {T} mm (both parts)",
            f"Bend inner radius: {R_IN} mm (outer {R_O}), all bends 90°",
            f"Overall: {XT1 - XT0:.1f} (W) x {Y:.1f} (D) x {HT:.1f} (H) mm",
            "",
            "Part 1 BOTTOM: base + front/rear panels + 2 side lips",
            f"  - 4 x M3 self-clinching nuts (PEM CLS-M3-1 type) in side lips,",
            f"    hole Ø{NUT_HOLE}. OUTSIDE face must be FLUSH (cover side wall",
            f"    sits on it) → nut body on the INSIDE of the lip",
            f"    positions: y = {SIDE_SCREWS[0][0]:.0f} / {SIDE_SCREWS[1][0]:.0f} mm, z = {SIDE_SCREWS[0][1]:.0f} mm (both lips)",
            f"  - 4 x Ø{SCREW_HOLE} PCB spacer holes in base",
            "Part 2 COVER: top + left/right sides",
            f"  - 4 x Ø{SCREW_HOLE} screw holes in side walls (match the nuts)",
            "",
            "Finish: anodizing (black recommended), both parts",
            "Silkscreen: white, front & rear panels (silk_front.dxf / silk_rear.dxf)",
            "Tolerance: per JLCCNC standard (±0.2, holes ±0.1)",
            "",
            "注記 (日本語)",
            "・圧入ナットは本体が立ち上がりの内側、外側は平ら (リベットナット不可)",
            "  ※カバー側板が外側から密着するため",
            "・アルマイトは絶縁: シャーシ接地は基板取付ねじ/側面ねじに",
            "  歯付き座金を入れて塗膜を破る",
            "・XLR取付: 3×8 なべ Pタイト (樹脂用タッピンねじ) ×8",
            "・カバー固定: M3×6 なべ小ねじ ×4 (歯付き座金を併用)",
            "・基板: M3×6 六角スペーサー(メス-メス) ×4 + M3×4 なべ小ねじ ×8",
            "",
            "Flat patterns (reference): flat_bottom.dxf ({:.1f} x {:.1f}),".format(*flats["bottom"]),
            "  flat_cover.dxf ({:.1f} x {:.1f}), K = {}".format(*flats["cover"], K),
        ]
        ax.text(0, 1, "\n".join(notes), va="top", family=plt.rcParams["font.family"], fontsize=8)
        fig.suptitle("P48 2CH enclosure — base, hardware and notes", fontsize=10)
        pdf.savefig(fig); plt.close(fig)


def main():
    bottom, feats = make_bottom()
    cover = make_cover()
    export_step(bottom, os.path.join(OUT, PROJECT + "_bottom.step"))
    export_step(cover, os.path.join(OUT, PROJECT + "_cover.step"))
    export_step(Compound([bottom, cover]), os.path.join(OUT, PROJECT + "_enclosure.step"))
    flats = flat_patterns(feats)
    silk_dxf(feats)
    report = preview(bottom, cover, feats)
    drawing(feats, flats)
    cons = dict(
        note="工程4 基板設計用。座標は筐体基準 (原点=ボトム左前下の外角, mm)",
        pcb_outline=dict(x=PCB_X, y=PCB_Y), pcb_top_z=PCB_TOP, standoff=STANDOFF,
        mounting_holes=PCB_HOLES, front_panel_inner_y=T, rear_panel_inner_y=Y - T,
        xlr_center_x=XLR_X, xlr_axis_height_above_pcb=12.5,
        switch=dict(x=SW_POS[0], z=SW_POS[1], keepout_note="SW本体の下 (基板上面から8mm超) に背の高い部品を置かない"),
        led=dict(x=LED_POS[0], z=LED_POS[1]), dc_jack=dict(x=DC_POS[0], z=DC_POS[1],
                                                          note="ジャック前面を後パネル内面に合わせる (基板端から張り出す)"),
        max_component_height_above_pcb=round(HB - PCB_TOP - 1.0, 1),
        side_screw_keepout=[dict(y=y, z=z, note="M3×6 のねじ先が立ち上がり内面から約3mm出る") for (y, z) in SIDE_SCREWS],
    )
    json.dump(cons, open(os.path.join(OUT, "pcb_constraints.json"), "w"), ensure_ascii=False, indent=1)
    print("bottom volume %.0f mm3, cover volume %.0f mm3" % (bottom.volume, cover.volume))
    print("overall %.1f x %.1f x %.1f mm" % (XT1 - XT0, Y, HT))
    print("flat bottom %.1f x %.1f, cover %.1f x %.1f" % (*flats["bottom"], *flats["cover"]))
    for r in report:
        print("  XLR", r)


if __name__ == "__main__":
    main()
