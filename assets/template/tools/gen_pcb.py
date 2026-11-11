#!/usr/bin/env python3
"""2ch P48ファンタム電源 — 基板(配置+配線)ジェネレーター

KiCad同梱のPythonで実行する:
  $(python3 tools/kicad_env.py | sed -n 's/KICAD_PYTHON = //p') tools/gen_pcb.py   # KiCad 同梱 Python
gen_schematic.py の PARTS(回路定義) を読み、kicad/P48_2CH.kicad_pcb を生成する。
4層: F.Cu=部品+配線 / In1.Cu=GND / In2.Cu=GND / B.Cu=配線
注意: 再実行すると .kicad_pcb を上書きする。
"""
import heapq, json, math, os, sys
from array import array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_schematic as sch
import pcbnew

SS = sch.SS
OUT = os.path.join(sch.OUT, sch.PROJECT + ".kicad_pcb")
LIBDIR = {"Custom": os.path.join(sch.OUT, "Custom.pretty")}
OX, OY = 100.0, 80.0         # KiCadシート上の原点オフセット

# ---- 筐体から基板寸法を受け取る (筐体/pcb_constraints.json)
#  基板座標: bx = 筐体x − 基板左端, by = 基板前端(筐体y) から 後ろ向きに測った値を反転 → 画面の下 = 前面パネル側
_C = json.load(open(os.path.join(sch.ROOT, "筐体", "pcb_constraints.json")))
EX0, EX1 = _C["pcb_outline"]["x"]
EY0, EY1 = _C["pcb_outline"]["y"]
W, D = EX1 - EX0, EY1 - EY0          # 96 x 86


def from_enc(x, y):
    """筐体座標 (x 右, y 前→後) → 基板座標 (bx 右, by 下=前)"""
    return x - EX0, EY1 - y


FRONT_PANEL_BY = from_enc(0, _C["front_panel_inner_y"])[1]     # 87.0 (基板前端より 1mm 外)
REAR_PANEL_BY = from_enc(0, _C["rear_panel_inner_y"])[1]       # -1.0
XC = {k: from_enc(v, 0)[0] for k, v in _C["xlr_center_x"].items()}    # L 15.5 / R 47.5
HOLES = [from_enc(x, y) for x, y in _C["mounting_holes"]]
SW_BX = from_enc(_C["switch"]["x"], 0)[0]
LED_BX = from_enc(_C["led"]["x"], 0)[0]
DC_BX = from_enc(_C["dc_jack"]["x"], 0)[0]


def mm(v):
    return pcbnew.FromMM(float(v))


def V(x, y):
    return pcbnew.VECTOR2I(mm(x + OX), mm(y + OY))


# ---------------------------------------------------------------- placement
# POS[ref] = (x, y, 回転)  … フットプリント原点の位置。回転は KiCad の向き (画面上で反時計回り)
POS = {}

# Neutrik XLR: STEPモデルとフットプリントの対応から求めた配置
#   メス NC3FAAH2: 回転270, 原点(ピン1)はパネル面から 12.7 奥, 軸から x+3.81
#   オス NC3MAAH-1: 回転180, 原点(ピン1)はパネル面から 17.78 奥, 軸から x+3.81


def chan(ch, b):
    o = XC[ch] - XC["L"]          # L を基準にしたずらし量 (R は +32)
    r = lambda i: "R%d" % (b + i)
    c = lambda i: "C%d" % (b + i)
    POS["J%d" % (b + 1)] = (XC[ch] + 3.81, FRONT_PANEL_BY - 12.7, 270)
    POS["J%d" % (b + 2)] = (XC[ch] + 3.81, REAR_PANEL_BY + 17.78, 180)
    POS[c(2)] = (7.0 + o, 65.4, 0)            # RFI 1nF (HOT)
    POS[c(3)] = (21.0 + o, 65.4, 0)           # RFI 1nF (COLD)
    POS[r(2)] = (2.6 + o, 61.8, 0)            # 6.81k HOT (軸方向, ピン1=P48 側)
    POS[r(3)] = (15.3 + o, 61.8, 0)           # 6.81k COLD
    POS[c(4)] = (6.4 + o, 55.0, 90)           # DCカット HOT (+ = 入力側)
    POS[c(6)] = (18.4 + o, 55.0, 90)          # DCカット COLD
    POS[c(5)] = (1.8 + o, 43.6, 0)            # フィルム HOT (WIMA MKP4 P7.5)
    POS[c(7)] = (13.4 + o, 43.6, 0)           # フィルム COLD
    POS[c(1)] = (25.0 + o, 33.0, 0)           # ch別デカップリング電解
    POS[r(1)] = (27.5 + o, 41.6, 90)          # 100Ω
    POS[r(4)] = (6.0 + o, 35.0, 90)           # 直列 10Ω HOT
    POS[r(5)] = (18.0 + o, 35.0, 90)          # 直列 10Ω COLD
    POS[r(6)] = (9.5 + o, 29.0, 0)            # ブリーダー HOT
    POS[r(7)] = (20.5 + o, 29.0, 0)           # ブリーダー COLD
    POS["D%d" % (b + 1)] = (1.4 + o, 24.0, 0)     # TVS HOT
    POS["D%d" % (b + 2)] = (14.4 + o, 24.0, 0)    # TVS COLD


chan("L", 100)
chan("R", 200)
POS.update({
    # --- 後ろ側 (上): DCジャック・入力保護
    "J1": (DC_BX, REAR_PANEL_BY + 13.7, 270),     # 前面 (13.7 前) を後パネル内面に合わせる
    "F1": (66.0, 4.0, 0),
    "C1": (66.5, 13.0, 0),
    "D1": (68.5, 20.3, 0),
    "C2": (76.0, 20.0, 90),
    "C3": (78.2, 20.0, 90),
    "D2": (65.0, 25.5, 0),
    # --- 昇圧
    "L1": (87.5, 30.0, 0),
    "D3": (89.0, 36.7, 0),
    "Q1": (84.6, 40.6, 0),
    "R7": (93.0, 43.2, 90),
    "C14": (84.6, 45.2, 0),
    "C13": (86.8, 52.0, 0),
    "U1": (66.5, 36.0, 0),
    "R1": (76.6, 32.8, 90),
    "C4": (78.6, 37.6, 90),
    "C5": (76.6, 37.6, 90),
    "C6": (73.6, 33.4, 0),
    "R2": (70.0, 33.0, 0),
    "C7": (67.0, 31.2, 0),
    "R5": (77.6, 41.6, 0),
    "R6": (81.2, 42.6, 90),
    "R10": (65.4, 46.8, 0),
    "C11": (68.5, 46.8, 0),
    "R8": (71.6, 46.8, 0),
    "C10": (65.4, 48.8, 0),
    "R4": (68.5, 48.8, 0),
    "C12": (71.6, 48.8, 0),
    "R9": (66.8, 50.4, 0),
    "R11": (81.15, 22.7, 0),
    "C15": (85.9, 22.7, 0),
    # --- RCフィルター + リップルフィルター
    "R12": (80.0, 59.6, 0),
    "C16": (64.0, 57.0, 0),
    "C17": (66.0, 64.2, 0),
    "C18": (76.05, 52.8, 0),
    "R13": (69.9, 65.6, 0),
    "R14": (73.0, 65.6, 0),
    "R15": (76.1, 65.6, 0),
    "Q2": (70.5, 70.0, 0),
    "Q3": (75.5, 70.0, 0),
    "R16": (79.0, 70.0, 90),
    "D4": (70.5, 74.6, 0),
    "D5": (75.5, 74.6, 0),
    "C19": (79.0, 75.2, 90),
    # --- 前側 (下): SW配線・LED
    "J2": (87.3, 72.0, 0),           # PHANTOM スイッチ配線 (XH 3P)
    "R18": (88.0, 67.6, 0),
    "LED1": (LED_BX - 1.27, FRONT_PANEL_BY - 5.4, 0),
    "R17": (83.6, 79.0, 90),
    # --- グラウンド
    "R20": (31.5, 70.0, 90),
    "C20": (31.5, 65.2, 90),
})
for _i, (hx, hy) in enumerate(HOLES):
    POS["H%d" % (_i + 1)] = (hx, hy, 0)

# 配線幅クラス: 細線(0.2mm)にするネット。それ以外は0.4mm
NARROW = {"FB", "COMP", "COMP_RC", "RC", "VREF", "GATE", "GATE_Q", "CS_F", "LED_A", "Q_B1", "Q_B2", "VBASE", "SNUB",
          "PH_FEED", "PH_OFF"}
ORDER_FIRST = ["SW", "CS", "CS_F", "GATE", "GATE_Q", "VBOOST", "VCC", "VREF", "RC", "COMP", "COMP_RC", "FB"]
ORDER_LAST = ["+48V", "L_P48", "R_P48", "VIN_RAW", "VIN_F", "+12V", "CHASSIS"]

# ---------------------------------------------------------------- routing grid
G = 0.25
GX0, GY0 = 0.0, 0.0
NX, NY = int(round((W - GX0) / G)) + 1, int(round((D - GY0) / G)) + 1
R_INFL = (0.29, 0.45)   # 0.2mm線 / 0.4mm線・ビア の中心が他ネット銅箔から離れるべき距離
TW = (0.2, 0.4)
VIA_D, VIA_DRILL = 0.5, 0.3
own = [[array("h", [0]) * (NX * NY) for _ in range(2)] for _ in range(2)]   # own[map][layer]
keepout = bytearray(NX * NY)   # ビア禁止 (パッド上)
EPS = 1e-6


def gi(x):
    return (x - GX0) / G


def gj(y):
    return (y - GY0) / G


def mark(layer, x1, y1, x2, y2, net):
    for m in (0, 1):
        r = R_INFL[m]
        a = own[m][layer]
        i1, i2 = max(0, int(math.ceil(gi(x1 - r) - EPS))), min(NX - 1, int(math.floor(gi(x2 + r) + EPS)))
        j1, j2 = max(0, int(math.ceil(gj(y1 - r) - EPS))), min(NY - 1, int(math.floor(gj(y2 + r) + EPS)))
        for j in range(j1, j2 + 1):
            base = j * NX
            for i in range(i1, i2 + 1):
                v = a[base + i]
                if v == 0:
                    a[base + i] = net
                elif v != net:
                    a[base + i] = -1


def cells_in(x1, y1, x2, y2):
    i1, i2 = int(math.ceil(gi(x1) - EPS)), int(math.floor(gi(x2) + EPS))
    j1, j2 = int(math.ceil(gj(y1) - EPS)), int(math.floor(gj(y2) + EPS))
    return [(i, j) for j in range(max(0, j1), min(NY - 1, j2) + 1) for i in range(max(0, i1), min(NX - 1, i2) + 1)]


def astar(net, sources, targets, m, via_goal=False, allow_via=True, limit=600000):
    """sources: [(l,i,j)], targets: set of (l,i,j). Returns path [(l,i,j)...] or None."""
    a0, a1 = own[m]
    w0, w1 = own[1]
    if via_goal:
        ti1 = tj1 = 0
        ti2, tj2 = NX, NY
    else:
        ti1 = min(t[1] for t in targets); ti2 = max(t[1] for t in targets)
        tj1 = min(t[2] for t in targets); tj2 = max(t[2] for t in targets)
    si1 = min(s[1] for s in sources); si2 = max(s[1] for s in sources)
    sj1 = min(s[2] for s in sources); sj2 = max(s[2] for s in sources)
    mg = int(18 / G)
    wi1, wi2 = max(0, min(si1, ti1) - mg), min(NX - 1, max(si2, ti2) + mg)
    wj1, wj2 = max(0, min(sj1, tj1) - mg), min(NY - 1, max(sj2, tj2) + mg)
    if via_goal:
        mg = int(6 / G)
        wi1, wi2, wj1, wj2 = max(0, si1 - mg), min(NX - 1, si2 + mg), max(0, sj1 - mg), min(NY - 1, sj2 + mg)

    def h(i, j):
        if via_goal:
            return 0
        dx = ti1 - i if i < ti1 else (i - ti2 if i > ti2 else 0)
        dy = tj1 - j if j < tj1 else (j - tj2 if j > tj2 else 0)
        return dx + dy

    def via_ok(idx):
        return (w0[idx] in (0, net)) and (w1[idx] in (0, net)) and not keepout[idx]

    src = set(sources)
    best, prev, heap = {}, {}, []
    for s in sources:
        st = (s[0], s[1], s[2], 4)
        best[st] = 0.0
        heapq.heappush(heap, (h(s[1], s[2]), 0.0, st))
    DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
    n = 0
    while heap:
        f, g, st = heapq.heappop(heap)
        if g > best.get(st, 1e18):
            continue
        l, i, j, d = st
        idx = j * NX + i
        if via_goal:
            if (l, i, j) not in src and via_ok(idx):
                break
        elif (l, i, j) in targets:
            break
        n += 1
        if n > limit:
            return None
        arr = a0 if l == 0 else a1
        for nd, (dx, dy) in enumerate(DIRS):
            ni, nj = i + dx, j + dy
            if ni < wi1 or ni > wi2 or nj < wj1 or nj > wj2:
                continue
            v = arr[nj * NX + ni]
            if v != 0 and v != net:
                continue
            ng = g + 1.0 + (0.0 if (d == nd or d == 4) else 0.7) + (0.15 if l == 1 else 0.0)
            ns = (l, ni, nj, nd)
            if ng < best.get(ns, 1e18):
                best[ns] = ng
                prev[ns] = st
                heapq.heappush(heap, (ng + h(ni, nj), ng, ns))
        if allow_via and not via_goal and via_ok(idx):
            other = (a1 if l == 0 else a0)[idx]
            if other == 0 or other == net:
                ns = (1 - l, i, j, 4)
                ng = g + 14.0
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    prev[ns] = st
                    heapq.heappush(heap, (ng + h(i, j), ng, ns))
    else:
        return None
    path = []
    while st is not None:
        path.append(st[:3])
        st = prev.get(st)
    path.reverse()
    return path


# ---------------------------------------------------------------- build
def main():
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    bds = board.GetDesignSettings()
    try:
        nc = bds.m_NetSettings.GetDefaultNetclass()
        nc.SetClearance(mm(0.15)); nc.SetTrackWidth(mm(0.2)); nc.SetViaDiameter(mm(VIA_D)); nc.SetViaDrill(mm(VIA_DRILL))
    except Exception as e:
        print("netclass:", e)
    bds.m_MinClearance = mm(0.15)
    bds.m_TrackMinWidth = mm(0.15)
    bds.m_ViasMinSize = mm(0.45)
    bds.m_MinThroughDrill = mm(0.3)
    bds.m_CopperEdgeClearance = mm(0.3)
    bds.m_HoleToHoleMin = mm(0.25)

    # outline
    pts = [(0, 0), (W, 0), (W, D), (0, D), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)

    # nets
    nets, netid = {}, {}
    for p in sch.PARTS:
        for net in p["pins"].values():
            if net and net not in nets:
                ni = pcbnew.NETINFO_ITEM(board, net if net == "GND" else "/" + net)   # 回路図のラベル名と同じ表記
                board.Add(ni)
                nets[net] = ni
                netid[net] = len(nets)
    idname = {v: k for k, v in netid.items()}

    # footprints
    fps = {}
    for p in sch.PARTS:
        if not p["fp"]:
            raise SystemExit("no footprint: " + p["ref"])
        lib, name = p["fp"].split(":")
        fp = pcbnew.FootprintLoad(LIBDIR.get(lib, "%s/footprints/%s.pretty" % (SS, lib)), name)
        if fp is None:
            raise SystemExit("footprint not found: " + p["fp"])
        x, y, rot = POS[p["ref"]]
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(rot)
        try:
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
        except Exception:
            pass
        if p["asm"] == "DNP":
            try:
                fp.SetDNP(True)
            except Exception:
                pass
        # 回路図と同じ部品情報 (型番など) を持たせる
        for fname, fval in (("MPN", p["mpn"]), ("LCSC", p["lcsc"]), ("Assembly", p["asm"]), ("Note", p["note"])):
            fp.SetField(fname, fval)
            try:
                fp.GetField(fname).SetVisible(False)
            except Exception:
                pass
        # シルク: 値は印刷しない。JLC実装のチップ部品は記号もFab層へ (手はんだ部品だけ記号を印刷)
        fp.Value().SetVisible(False)
        ref_t = fp.Reference()
        if p["asm"] in ("JLC", "DNP") or p["ref"].startswith("H"):
            ref_t.SetLayer(pcbnew.F_Fab)
        else:
            ref_t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
            ref_t.SetTextThickness(mm(0.15))
        for pad in fp.Pads():
            num = pad.GetNumber()
            net = p["pins"].get(num)
            if net:
                pad.SetNet(nets[net])
        board.Add(fp)
        fps[p["ref"]] = fp

    # ------------------------------------------------ 配置チェック (コートヤードの重なり・基板外へのはみ出し)
    boxes = {}
    for ref, fp in fps.items():
        try:
            cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            if cy.GetWidth() == 0:
                raise ValueError
        except Exception:
            cy = fp.GetBoundingBox(False, False)
        boxes[ref] = (pcbnew.ToMM(cy.GetLeft()) - OX, pcbnew.ToMM(cy.GetTop()) - OY,
                      pcbnew.ToMM(cy.GetRight()) - OX, pcbnew.ToMM(cy.GetBottom()) - OY)
    over = []
    refs = sorted(boxes)
    # 取付穴とXLRのコートヤード: 穴の位置ではXLRの胴体はフランジより細く、ねじ頭との間にすき間がある (Neutrik STEPで確認)
    allowed = {("H1", "J101"), ("H1", "J201"), ("H2", "J102"), ("H2", "J202")}
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            A, B = boxes[a], boxes[b]
            dx = min(A[2], B[2]) - max(A[0], B[0])
            dy = min(A[3], B[3]) - max(A[1], B[1])
            if dx > 0.01 and dy > 0.01 and (a, b) not in allowed and (b, a) not in allowed:
                over.append((a, b, round(dx, 2), round(dy, 2)))
    print("courtyard overlaps:", len(over))
    for o in over:
        print("   ", o)
    for ref, (x1_, y1_, x2_, y2_) in boxes.items():
        if ref.startswith(("J1", "J2", "LED", "H")) or (ref.startswith("J") and len(ref) == 4):
            continue
        if x1_ < 0 or y1_ < 0 or x2_ > W or y2_ > D:
            print("    outside board:", ref, [round(v, 2) for v in (x1_, y1_, x2_, y2_)])
    if "--check" in sys.argv:
        for ref in ("J101", "J102", "J1", "LED1", "L1", "Q1", "U1"):
            print("   ", ref, [round(v, 2) for v in boxes[ref]])
        board.SetFileName(OUT)
        pcbnew.SaveBoard(OUT, board)      # 配置だけの基板 (確認用)
        return

    # ------------------------------------------------ grid init
    for m in (0, 1):
        for l in (0, 1):
            a = own[m][l]
            for j in range(NY):
                y = GY0 + j * G
                for i in range(NX):
                    x = GX0 + i * G
                    inside = 0.6 <= x <= W - 0.6 and 0.6 <= y <= D - 0.6
                    if not inside:
                        a[j * NX + i] = -1

    pads = {}      # net -> list of dict(cells={layer:[(i,j)]}, c=(x,y), smd, ref)
    uniq = [2000]
    for ref, fp in fps.items():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            bx1, by1 = pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY
            bx2, by2 = pcbnew.ToMM(bb.GetRight()) - OX, pcbnew.ToMM(bb.GetBottom()) - OY
            attr = pad.GetAttribute()
            if attr == pcbnew.PAD_ATTRIB_NPTH:
                for l in (0, 1):
                    mark(l, bx1 - 0.25, by1 - 0.25, bx2 + 0.25, by2 + 0.25, -1)
                continue
            name = pad.GetNetname().lstrip("/")
            if name:
                nid = netid[name]
            else:
                uniq[0] += 1
                nid = uniq[0]
            tht = attr == pcbnew.PAD_ATTRIB_PTH
            layers = (0, 1) if tht else (0,)
            for l in layers:
                mark(l, bx1, by1, bx2, by2, nid)
            for (i, j) in cells_in(bx1 - 0.35, by1 - 0.35, bx2 + 0.35, by2 + 0.35):
                keepout[j * NX + i] = 1
            if not name:
                continue
            cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
            try:
                shape = pad.GetShape(pcbnew.F_Cu)
            except TypeError:
                shape = pad.GetShape()
            k = 0.35 if shape in (pcbnew.PAD_SHAPE_CIRCLE, pcbnew.PAD_SHAPE_OVAL) else None
            if k:
                hx, hy = (bx2 - bx1) * k, (by2 - by1) * k
            else:
                hx, hy = max(0.0, (bx2 - bx1) / 2 - 0.12), max(0.0, (by2 - by1) / 2 - 0.12)
            cs = cells_in(cx - hx, cy - hy, cx + hx, cy + hy)
            stub = None
            if not cs:
                i, j = int(round(gi(cx))), int(round(gj(cy)))
                cs = [(i, j)]
                stub = (cx, cy)
            pads.setdefault(name, []).append(dict(cells={l: cs for l in layers}, c=(cx, cy), smd=not tht, ref=ref,
                                                  num=pad.GetNumber(), stub=stub, box=(bx1, by1, bx2, by2)))

    # ------------------------------------------------ emit helpers
    LAYER = (pcbnew.F_Cu, pcbnew.B_Cu)
    stats = dict(tracks=0, vias=0)

    def add_track(net, l, xa, ya, xb, yb, w):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(xa, ya)); t.SetEnd(V(xb, yb)); t.SetWidth(mm(w)); t.SetLayer(LAYER[l]); t.SetNet(nets[net])
        board.Add(t)
        stats["tracks"] += 1
        mark(l, min(xa, xb) - w / 2, min(ya, yb) - w / 2, max(xa, xb) + w / 2, max(ya, yb) + w / 2, netid[net])

    def add_via(net, x, y):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x, y))
        v.SetDrill(mm(VIA_DRILL))
        try:
            v.SetWidth(pcbnew.F_Cu, mm(VIA_D))
        except TypeError:
            v.SetWidth(mm(VIA_D))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nets[net])
        board.Add(v)
        stats["vias"] += 1
        for l in (0, 1):
            mark(l, x - VIA_D / 2, y - VIA_D / 2, x + VIA_D / 2, y + VIA_D / 2, netid[net])
        for (i, j) in cells_in(x - 0.6, y - 0.6, x + 0.6, y + 0.6):
            keepout[j * NX + i] = 1

    def emit(net, path, w, end_via=False):
        pt = lambda c: (GX0 + c[1] * G, GY0 + c[2] * G)
        k = 0
        while k < len(path) - 1:
            a = path[k]
            b = path[k + 1]
            if a[0] != b[0]:
                add_via(net, *pt(a))
                k += 1
                continue
            d = (b[1] - a[1], b[2] - a[2])
            e = k + 1
            while e + 1 < len(path) and path[e + 1][0] == a[0] and \
                    (path[e + 1][1] - path[e][1], path[e + 1][2] - path[e][2]) == d:
                e += 1
            add_track(net, a[0], *pt(a), *pt(path[e]), w)
            k = e
        if end_via:
            add_via(net, *pt(path[-1]))

    def stub(net, pad, cell, w):
        if pad["stub"]:
            x, y = GX0 + cell[1] * G, GY0 + cell[2] * G
            if abs(x - pad["stub"][0]) + abs(y - pad["stub"][1]) > 1e-4:
                add_track(net, cell[0], pad["stub"][0], pad["stub"][1], x, y, min(w, 0.2))

    failed = []

    def route_net(net):
        nid = netid[net]
        pl = pads.get(net, [])
        if len(pl) < 2:
            return
        m0 = 0 if net in NARROW else 1
        done = [pl[0]]
        todo = pl[1:]
        tree = set((l, i, j) for l, cs in pl[0]["cells"].items() for (i, j) in cs)
        while todo:
            todo.sort(key=lambda p: min(abs(p["c"][0] - q["c"][0]) + abs(p["c"][1] - q["c"][1]) for q in done))
            p = todo.pop(0)
            src = [(l, i, j) for l, cs in p["cells"].items() for (i, j) in cs]
            path, mused = None, m0
            for m in ([1, 0] if m0 == 1 else [0]):
                path = astar(nid, src, tree, m)
                mused = m
                if path:
                    break
            if not path:
                failed.append("%s: %s.%s" % (net, p["ref"], p["num"]))
                continue
            w = TW[mused]
            emit(net, path, w)
            stub(net, p, path[0], w)
            for q in done:   # target pad stub if the path ended on a stub-type pad cell
                if q["stub"] and any(path[-1][1:] == c for cs in q["cells"].values() for c in cs):
                    stub(net, q, path[-1], w)
            for c in path:
                tree.add(c)
            for k in range(len(path) - 1):
                if path[k][0] != path[k + 1][0]:
                    tree.add((0,) + path[k][1:]); tree.add((1,) + path[k][1:])
            tree.update(src)
            done.append(p)

    def route_gnd():
        nid = netid["GND"]
        for p in pads.get("GND", []):
            if not p["smd"]:
                continue   # スルーホールは内層GNDプレーンに直接つながる
            if p["ref"] == "U1":   # IC: 放熱パッドにビア2個、GNDピンは放熱パッドへ直結
                ep = [q for q in pads["GND"] if q["ref"] == "U1" and q["num"] == "13"][0]
                ex = round(ep["c"][0] / G) * G
                if p["num"] == "13":
                    for dy in (-0.75, 0.75):
                        add_via("GND", ex, round((ep["c"][1] + dy) / G) * G)
                else:
                    add_track("GND", 0, p["c"][0], p["c"][1], ex, p["c"][1], 0.2)
                continue
            src = [(0, i, j) for (i, j) in p["cells"][0]]
            path = astar(nid, src, set(), 0, via_goal=True)
            if not path:
                failed.append("GND via: %s.%s" % (p["ref"], p["num"]))
                continue
            emit("GND", path, 0.3 if len(path) < 3 else 0.25, end_via=True)
            stub("GND", p, path[0], 0.2)

    order = [n for n in ORDER_FIRST if n in pads]
    rest = sorted((n for n in pads if n not in ORDER_FIRST and n not in ORDER_LAST and n != "GND"),
                  key=lambda n: len(pads[n]))
    for n in order:
        route_net(n)
    route_gnd()
    for n in rest + [n for n in ORDER_LAST if n in pads]:
        route_net(n)

    # 基板上の文字 (シルク)
    def silk(txt, x, y, size=1.2, rot=0):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetPosition(V(x, y))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(size * 0.15))
        t.SetTextAngleDegrees(rot)
        board.Add(t)
    silk("P48 2CH  rev C", 28.3, 52.0, 1.2, 90)
    silk("L", XC["L"] - 5.0, 39.0, 2.0)
    silk("R", XC["R"] - 5.0, 39.0, 2.0)
    silk("OUT", 31.5, 3.0, 1.0)
    silk("IN", 31.5, 83.0, 1.0)
    silk("+48V", 80.6, 67.0, 0.9)
    silk("! 52V", 95.1, 40.5, 1.0, 90)

    # GND planes on inner layers
    for layer in (pcbnew.In1_Cu, pcbnew.In2_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(nets["GND"])
        z.SetZoneName("GND")
        ol = z.Outline()
        ol.NewOutline()
        for (x, y) in ((-1, -3), (W + 1, -3), (W + 1, D + 1), (-1, D + 1)):
            ol.Append(mm(x + OX), mm(y + OY))
        z.SetLocalClearance(mm(0.25))
        z.SetMinThickness(mm(0.2))
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    board.SetFileName(OUT)
    pcbnew.SaveBoard(OUT, board)
    print("saved", OUT, stats)
    print("FAILED %d:" % len(failed))
    for f in failed:
        print("  ", f)


if __name__ == "__main__":
    main()
