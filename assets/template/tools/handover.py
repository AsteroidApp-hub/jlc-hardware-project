#!/usr/bin/env python3
"""製作者向け資料 (引き継ぎ用) と 製作データ一式の zip を作る。

使い方 (build123d / matplotlib のある Python で):
    <venv>/bin/python tools/handover.py
出力:
    製作者向け資料/製作者向け資料.html (+ 図)
    P48_2CH_製作データ.zip   … 製作者に渡す一式
寸法・部品表は回路定義 (gen_schematic)・基板 (kicad_pcb)・筐体 (gen_enclosure) から自動で引く。
"""
import datetime, json, os, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "enclosure"))
import gen_schematic as sch          # noqa: E402
import gen_enclosure as E            # noqa: E402
import md2html                       # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib import font_manager

for f in ("Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP"):
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break

OUTD = os.path.join(ROOT, "製作者向け資料")
from kicad_env import kicad_python  # noqa: E402
KICAD_PY = kicad_python()
PARTS = {p["ref"]: p for p in sch.PARTS}
CONS = json.load(open(os.path.join(ROOT, "筐体", "pcb_constraints.json")))
BX0, BY1 = CONS["pcb_outline"]["x"][0], CONS["pcb_outline"]["y"][1]   # 基板座標 → 筐体座標の換算用

# 手はんだ部品の向き・高さ (高さは基板上面から、データシート/実寸からの目安)
POLARITY = {
    "Device:C_Polarized": "+ (長い足) をシルクの「+」側 (角の丸い四角パッド) へ",
    "Device:LED": "短い足 (K) を四角パッドへ",
    "Regulator_Controller:UC3842_SOIC8": "切り欠き・1番ピンを四角パッドへ",
    "Transistor_FET:Q_NMOS_GDS": "四角パッド = G。足の並び G-D-S",
    "Device:D_TVS": "なし (双方向)",
}
HEIGHT = {"XLRF": 25.3, "XLRM": 25.3, "CP10": None, "L12": 15.5, "TOROID": 15.5, "DIP8": 4.5, "TO251": 15.0,
          "FILM": 9.5, "DO41": 2.7, "DO15": 3.6, "RAX": 2.5, "PTC": 13.7, "LED": 3.5, "XH3": 9.8, "JACK": 11.0}
CAP_H = {"UFW2A101MPD": 20.0, "UPW2A470MPD": 16.0, "35ZLH470M": 16.0}
# 検査で当てる測定点 (スルーホール部品のパッド)
TPS = [("C13", "1", "VBOOST (約51.5V)", (-4, -6.5)), ("C13", "2", "GND", (3, 4.5)),
       ("C101", "1", "L ch 給電 (約48V)", (3, -3.2)), ("C201", "1", "R ch 給電 (約48V)", (3, -3.2)),
       ("C18", "1", "VBASE (約49.4V)", (2, 8.5)), ("U1", "7", "VCC (入力電圧 −約0.4V)", (3, -3.2))]


def fpkey(fp):
    return next((k for k, v in sch.FP.items() if v == fp), "")


def dump_pcb():
    tmp = os.path.join(OUTD, "_pcb.json")
    r = subprocess.run([KICAD_PY, os.path.join(HERE, "dump_pcb.py"), tmp], capture_output=True, text=True)
    if not os.path.exists(tmp):
        print(r.stdout, r.stderr)
        raise SystemExit("dump_pcb failed")
    d = json.load(open(tmp))
    os.remove(tmp)
    return {f["ref"]: f for f in d}


def assembly_drawing(fps):
    W, D = 96.0, 86.0
    fig, ax = plt.subplots(figsize=(13, 12))
    ax.add_patch(Rectangle((0, 0), W, D, fill=False, lw=1.5))
    colors = {"Device:C_Polarized": "#ffe08a", "Device:R": "#c9e4ff", "Device:C": "#d7f0d0", "Device:D_TVS": "#ffc9a8",
              "Device:LED": "#b8f5b8", "Device:L": "#e3d0ff", "Device:Polyfuse": "#f0d0d0"}
    for ref, f in fps.items():
        p = PARTS.get(ref)
        x1, y1, x2, y2 = f["box"]
        hand = p and p["asm"] == "HAND"
        if not hand:
            ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=True, fc="#f2f2f2", ec="#cfcfcf", lw=0.4))
            if ref.startswith("H"):
                ax.add_patch(Circle((f["x"], f["y"]), 1.6, fill=False, ec="k", lw=0.8))
                ax.text(f["x"], f["y"] + 4.2, "M3 取付穴", ha="center", fontsize=6.5)
            continue
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=True,
                               fc=colors.get(p["sym"], "#dfe6ee"), ec="#333", lw=0.7, alpha=0.9))
        for pd in f["pads"]:
            ax.add_patch(Rectangle((pd["x"] - pd["w"] / 2, pd["y"] - pd["h"] / 2), pd["w"], pd["h"],
                                   fill=True, fc="#b87333" if pd["rect"] else "#d9a066", ec="k", lw=0.3))
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(cx, cy, f"{ref}\n{p['value']}", ha="center", va="center", fontsize=6.3, weight="bold")
        pol = POLARITY.get(p["sym"])
        if pol and p["sym"] != "Device:D_TVS":
            pin1 = next((pd for pd in f["pads"] if pd["num"] == "1"), None)
            mark = {"Device:C_Polarized": "+", "Device:LED": "K", "Transistor_FET:Q_NMOS_GDS": "G",
                    "Regulator_Controller:UC3842_SOIC8": "1"}[p["sym"]]
            if pin1:
                ax.text(pin1["x"], pin1["y"], mark, ha="center", va="center", fontsize=9, color="#c00000",
                        weight="bold")
        if p["sym"] == "Connector_Generic:Conn_01x03":
            for pd in f["pads"]:
                ax.text(pd["x"], pd["y"] - 2.2, pd["num"], ha="center", fontsize=7, color="#c00000", weight="bold")
    for ref, pin, lab, (dx, dy) in TPS:
        pd = next(pd for pd in fps[ref]["pads"] if pd["num"] == pin)
        ax.add_patch(Circle((pd["x"], pd["y"]), 1.9, fill=False, ec="#d00000", lw=1.4))
        ax.annotate(f"TP: {lab}", (pd["x"], pd["y"]), xytext=(pd["x"] + dx, pd["y"] + dy), fontsize=6.3,
                    color="#d00000", arrowprops=dict(arrowstyle="-", color="#d00000", lw=0.6))
    ax.text(W / 2, D + 4.5, "▼ 前面パネル側 (MIC IN / PHANTOM スイッチ / LED)", ha="center", fontsize=10)
    ax.text(W / 2, -2.5, "▲ 後面パネル側 (OUTPUT / DC ジャック)", ha="center", fontsize=10)
    ax.set_xlim(-4, W + 4); ax.set_ylim(D + 7, -6); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("組立図 (部品面から見た図)  色付き = 手はんだ部品、灰色 = JLCPCB 実装済み。赤字 = 極性・ピン番号、赤丸 = 測定点",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTD, "組立図.png"), dpi=160)
    plt.close(fig)


def panel_drawings(feats):
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.properties import LayoutProperties
    fig, axs = plt.subplots(2, 1, figsize=(8, 6.2))
    for ax, name, title in zip(axs, ("front", "rear"), ("前面パネル (外から見た図)", "後面パネル (外から見た図)")):
        doc = ezdxf.readfile(os.path.join(ROOT, "筐体", f"silk_{name}.dxf"))
        lp = LayoutProperties.from_layout(doc.modelspace())
        lp.set_colors("#ffffff")
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(doc.modelspace(), layout_properties=lp)
        ax.set_title(title)
        ax.set_aspect("equal")
        ax.set_xlim(-3, E.X + 3); ax.set_ylim(-3, E.HB + 3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTD, "パネル.png"), dpi=160)
    plt.close(fig)


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def enc(bx, by):
    """基板座標 → 筐体座標 (x, y)"""
    return bx + BX0, BY1 - by


def main():
    os.makedirs(OUTD, exist_ok=True)
    fps = dump_pcb()
    bottom, feats = E.make_bottom()
    assembly_drawing(fps)
    panel_drawings(feats)
    for src in ("基板3D.png", "基板3D_斜め.png", "回路図.png", "筐体/筐体プレビュー.png", "筐体/組立プレビュー.png"):
        shutil.copy(os.path.join(ROOT, src), os.path.join(OUTD, os.path.basename(src)))

    # ---- 手はんだ部品表
    groups = {}
    for p in sch.PARTS:
        if p["asm"] != "HAND":
            continue
        k = (p["value"], p["mpn"], p["sym"], p["fp"])
        groups.setdefault(k, []).append(p)
    hand_rows = []
    for (val, mpn, sym, fp), ps in sorted(groups.items(), key=lambda kv: kv[1][0]["ref"]):
        key = fpkey(fp)
        h = HEIGHT.get(key)
        if key == "CP10":
            h = next((v for k, v in CAP_H.items() if k in mpn), 16.0)
        sh = sch.SHOP.get(ps[0]["buy"]) if ps[0]["buy"] else None
        shop = f"[{sh[0]}]({sh[2]})" if sh else ""
        hand_rows.append([", ".join(p["ref"] for p in ps), val, mpn, len(ps), POLARITY.get(sym, "なし"),
                          f"{h:.1f}" if h else "-", shop])
    jlc_n = sum(1 for p in sch.PARTS if p["asm"] == "JLC")
    jlc_kinds = len({(p["value"], p["fp"], p["lcsc"]) for p in sch.PARTS if p["asm"] == "JLC"})

    # ---- 寸法
    holes = [(f"{x:.1f}", f"{y:.1f}") for x, y in E.PCB_HOLES]
    holes_b = [(f"{fps[h]['x']:.1f}", f"{fps[h]['y']:.1f}") for h in ("H1", "H2", "H3", "H4")]
    panel_rows = []
    for side, label in (("front", "前面"), ("rear", "後面")):
        for f in feats[side]:
            u = f["x"] if side == "front" else E.X - f["x"]
            kind = {"XLR-F": "XLR メス NC3FAAH2", "XLR-M": "XLR オス NC3MAAH-1", "SW": "PHANTOM スイッチ MS-500A-B",
                    "LED": "LED 3mm", "DC": "DC ジャック MJ-179PH"}[f["kind"]]
            if "ch" in f:
                kind += f" ({f['ch']})"
            scr = ", ".join(f"Ø{E.XLR_SCREW} ({(px if side == 'front' else E.X - px):.1f}, {pz:.1f})"
                            for px, pz in f.get("screws", []))
            panel_rows.append([label, kind, f"Ø{f['d']}", f"{u:.1f}", f"{f['z']:.1f}", scr or "-"])
    # PHANTOM スイッチの配線長 (J2 → パネルのスイッチ)
    j2 = fps["J2"]
    jx, jy = enc(j2["x"] + 2.5, j2["y"])
    dist = ((jx - E.SW_POS[0]) ** 2 + (jy - (E.T + 12)) ** 2 + (E.PCB_TOP + 9.8 - E.SW_POS[1]) ** 2) ** 0.5

    hw = [("M3 圧入ナット (JLCCNC が取付)", "4", "ボトム左右の立ち上がり", "JLCCNC")]
    hw += [(e[1].split("  ")[0], e[6], e[7], f"[{e[0]}]({e[2]})") for e in sch.EXTRA_BUY]

    today = datetime.date.today().isoformat()
    md = f"""# 2ch P48 ファンタム電源 — 製作者向け資料

{today} 版。この資料と同じフォルダの図、および `発注データ/` のファイルで製作できるようにまとめています。
不明点は依頼者に確認してください。

## 1. 製作物の概要

コンデンサーマイク用の 2ch ファンタム電源 (P48)。外部リニア電源から DC 12〜18V を受け、
基板上で約 51.5V に昇圧 → リップルフィルターで +48V を作り、6.81kΩ (0.1%) 経由で 2ch の XLR に供給する。
マイク信号は MIC IN (前面 XLR メス) から DC カットを経て OUTPUT (後面 XLR オス) へそのまま通る。

{table(["項目", "仕様"], [
    ["入力", "DC 12〜18V (外部リニア電源推奨)、2.1mm センタープラス、0.5A 以上の電源"],
    ["出力", "P48 × 2ch (約 48.2V、給電抵抗 6.81kΩ 0.1%)、1ch あたり最大 10mA"],
    ["消費電流", "約 60〜80mA (マイク 2 本接続時、入力 12〜18V)"],
    ["操作", "前面 PHANTOM スイッチ (ON で約2秒かけて +48V が上がる / OFF で約2.5秒で下がる)。電源スイッチは無し"],
    ["表示", "前面 LED = +48V 出力中"],
    ["外形", f"{E.XT1 - E.XT0:.1f} (幅) × {E.Y:.1f} (奥行) × {E.HT:.1f} (高さ) mm、アルミ A5052 t{E.T}、黒アルマイト"],
])}

![組立後のイメージ](組立プレビュー.png)

![基板 (部品を載せた状態)](基板3D_斜め.png)

## 2. 発注・調達

発注用ファイルはすべて `発注データ/` にあります。設定値は `発注データ/発注手順.html` を参照。

{table(["発注先", "内容", "ファイル"], [
    ["JLCPCB", f"4層基板 96×86mm t1.6 + 表面の SMD 実装 ({jlc_kinds}種類 {jlc_n}点、すべて基本部品)", "発注データ/JLCPCB/ (ガーバー zip・BOM・CPL)"],
    ["JLCCNC", "板金筐体 2部品 (ボトム・カバー)、A5052 t1.5、黒アルマイト、白シルク、M3 圧入ナット ×4", "発注データ/JLCCNC/ (STEP・図面・シルク DXF)"],
    ["Digi-Key Japan", "XLR・オーディオ用コンデンサー・0.1% 抵抗・UC3843 など (¥6,000 以上で送料無料になる数量にしてある)", "部品購入リスト.html (リンク付き)"],
    ["秋月電子通商", "トロイダル・DC ジャック・MOSFET・TVS・スイッチ・LED・配線材", "部品購入リスト.html (リンク付き)"],
    ["千石電商", "M3 スペーサー・ねじ・歯付き座金・XLR 取付ねじ (ネコポス ¥350)", "部品購入リスト.html (リンク付き)"],
])}

JLCPCB の配置プレビューでは Q2, Q3 (SOT-23) と D1, D3, D4, D5 (ダイオード) の向きを必ず確認してください。

## 3. 手はんだ部品

JLCPCB から届く基板には表面のチップ部品だけが実装済み。以下を手はんだで付ける。**背の低い順** に付けるとよい。

{table(["リファレンス", "値", "型番", "数", "向き・極性", "基板からの高さ mm (目安)", "購入先"], hand_rows)}

- R102/R103・R202/R203 (6.81kΩ 0.1%) は 10 本買ってある。テスターで全部測り、**値の近い 2 本ずつ** を同じチャンネルの組 (R102 と R103、R202 と R203) に使う。ホットとコールドの差が小さいほど電源ノイズが打ち消される
- U1 は IC ソケット (DIP-8) を使ってもよい (高さ約 8.5mm になるが問題なし)
- Q1 (TO-251) は基板から約 15mm 以内の高さで垂直に
- LED1 は基板と平行 (横向き) に付け、先端が基板の前端から約 0.7mm 出る位置。前面パネルの穴に入る
- D2 (P6KE24CA) と D101〜D202 (P4KE15CA) は形が似ているので取り違えに注意
- J1 (DC ジャック) の側面ピン用の穴は左右両側にある。部品に合う方を使い、もう一方は空きのまま

### 組立図

![組立図](組立図.png)

## 4. 寸法

### 基板

{table(["項目", "値"], [
    ["外形", "96.0 × 86.0 mm、角は直角"],
    ["板厚・層", "1.6 mm、4層 (内層2枚は GND)"],
    ["取付穴", "Ø3.2 × 4 (M3)。基板座標 (左上 = 後面側の左端を原点、右 +x、前面へ +y): " + ", ".join(f"({x}, {y})" for x, y in holes_b)],
    ["取付", f"M3 × {E.STANDOFF:.0f}mm 六角スペーサー (メス-メス) で底板から浮かせる。基板上面は筐体底面 (外側) から {E.PCB_TOP:.1f} mm"],
    ["部品の高さ制限", f"基板上面から天板の内面まで {E.HB - E.PCB_TOP:.1f} mm。PHANTOM スイッチの真下 (前面から約 20mm) は 9mm 以下"],
    ["基板と前後パネルのすき間", "前後とも 1.0 mm (XLR・DC ジャック・LED は基板の端から張り出してパネルに当たる)"],
])}

### 筐体

座標の原点はボトムの左・前・下の外側の角 (x = 幅方向・右が +、y = 奥行き・前→後、z = 高さ)。

{table(["項目", "値"], [
    ["外形", f"{E.XT1 - E.XT0:.1f} × {E.Y:.1f} × {E.HT:.1f} mm"],
    ["内寸", f"幅 {E.X - 2 * E.T:.1f} (左右の立ち上がり間) × 奥行 {E.Y - 2 * E.T:.1f} × 高さ {E.H_IN:.1f} mm"],
    ["材料・板厚", f"A5052、{E.T} mm、曲げ内R {E.R_IN} mm"],
    ["構成", f"ボトム = 底板 + 前後パネル + 左右の立ち上がり (高さ {E.LIP_H:.0f} mm)。カバー = 天板 + 左右側板"],
    ["カバー固定", "側面から M3 ねじ × 4 → 立ち上がりの圧入ナット。位置 y = " + " / ".join(f"{y:.0f}" for y, z in E.SIDE_SCREWS) + f" mm、z = {E.SIDE_SCREWS[0][1]:.1f} mm"],
    ["基板スペーサー穴 (底板)", "Ø3.4 × 4: " + ", ".join(f"({x}, {y})" for x, y in holes)],
    ["XLR の中心高さ", f"底面 (外側) から {E.XLR_AXIS_Z:.1f} mm (基板上面 + 12.5 mm)"],
    ["XLR の取付", "パネルの内側からタッピンねじ (3×8 樹脂用) で固定。パネル穴 Ø22.5 + 取付穴 Ø3.2 × 2"],
])}

### パネル穴 (外から見て左下の角が原点、単位 mm)

{table(["パネル", "部品", "穴径", "横 (左から)", "高さ (下から)", "XLR 取付穴"], panel_rows)}

![パネル](パネル.png)

詳しい寸法図は `発注データ/JLCCNC/筐体図面.pdf`。

## 5. 配線 (PHANTOM スイッチ)

前面パネルのトグルスイッチ MS-500A-B (1回路2接点 ON-ON) と基板の J2 (XH 3P) を 3本の線でつなぐ。
線の長さは直線距離が約 {dist:.0f} mm なので、**60〜80 mm** 程度 (AWG24 程度)。

{table(["スイッチの端子", "J2", "信号"], [
    ["中央 (共通)", "2番", "VBASE"],
    ["レバーを上 (ON) にしたとき中央とつながる外側の端子", "1番", "PH_FEED (ON)"],
    ["もう一方の外側の端子", "3番", "PH_OFF (OFF)"],
])}

- 一般的なトグルスイッチはレバーと**反対側**の端子が中央とつながる。**テスターで確認してから配線**する
- 端子は熱収縮チューブで保護。配線が外れるとファンタムは OFF になる (安全側)
- J2 の 1番は基板上の四角パッド側

## 6. 組み込み

1. 底板の 4か所に M3 × 6mm 六角スペーサーを M3 × 4 なべねじで固定 (ねじの下に歯付き座金)
2. 基板を載せ、M3 × 4 なべねじで固定 (同じく歯付き座金)。取付穴はシャーシ接地を兼ねる
3. XLR 4個を前後パネルの内側からタッピンねじで固定 (基板の XLR は**はんだ付け前にパネルへ仮組み**して位置を合わせると確実)
4. PHANTOM スイッチを前面パネルに取り付け、J2 へ配線
5. カバーを被せ、側面から M3 × 6 なべねじ × 4 で固定 (歯付き座金つき)
6. 底面の 4隅にゴム足

アルマイトは電気を通さないため、シャーシ (XLR 1番ピン・取付穴) の接地は**歯付き座金で塗膜を破って**取る。

### ねじ・小物

{table(["品名", "数", "用途", "購入先 (リンク)"], hw)}

## 7. 検査 (マイクを接続する前に)

**基板上には最大約 52V がかかる。通電中は基板に触れない。** 測定点は組立図の赤丸 (TP)。

{table(["順", "操作・測定", "期待値"], [
    ["1", "通電前: DC ジャックの + と − の間の抵抗", "短絡していない (数 kΩ 以上)"],
    ["2", "PHANTOM を OFF にして、12〜18V の電源を接続・ON", "消費電流 約 20〜50mA (マイクなし)"],
    ["3", "C13 の + (VBOOST) と − (GND)", "約 51.5V (50〜53V)"],
    ["4", "U1 の 7番 (VCC) と GND", "入力電圧 − 約 0.4V"],
    ["5", "C101 / C201 の + と GND (PHANTOM OFF のまま)", "0V 付近、LED 消灯"],
    ["6", "PHANTOM を ON、約 3秒待って C101 / C201 の + と GND", "約 48V (46.5〜49.5V)、LED がゆっくり点灯"],
    ["7", "C18 の + (VBASE) と GND", "約 49.4V"],
    ["8", "MIC IN の 2番・3番ピンと 1番ピンの間 (マイクなし)", "それぞれ 約 48V"],
    ["9", "MIC IN の 2番と 1番の間に電流計 (短絡電流)", "約 7mA (48V ÷ 6.81kΩ)。3番も同様"],
    ["10", "10秒以上待って OUTPUT の 2番・3番ピンと 1番ピンの間", "0V 付近 (±1V 以内)"],
    ["11", "PHANTOM を OFF", "+48V が約 3秒で 0V 付近へ、LED 消灯"],
    ["12", "外装: XLR 1番ピンと筐体 (塗装のないねじ頭など) の導通", "導通あり"],
])}

すべて OK ならマイクと録音機をつないで試聴。録音機側のファンタム電源は **OFF**。

## 8. 実物で確認が必要な項目 (設計時に確定できなかった点)

基板を発注する前に、`原寸チェック/基板_原寸.pdf` を 100% で印刷し、実物の部品を置いて確かめるのが確実です (手順は `原寸チェック/原寸チェック.html`)。

{table(["項目", "内容", "合わない場合"], [
    ["トロイダル L1 (TCV-101M-3A) の足の間隔", "データシートに記載なし。基板は長穴で約 4〜10mm に対応", "依頼者に連絡"],
    ["PHANTOM スイッチの奥行き", "MS-500A-B の本体が前パネルから約 18mm 以内に収まるか", "依頼者に連絡"],
    ["スイッチのレバーと端子の対応", "レバー上 = ON になるよう、テスターで確認して配線", "配線の入れ替えで対応"],
    ["DC ジャックの側面ピン", "左右どちらに出ているか未確定のため穴は両側", "対応済み"],
    ["JLCPCB の部品の向き", "配置プレビューで Q2, Q3, D1, D3, D4, D5 を確認", "画面上で回転して修正"],
    ["JLCCNC の曲げ制約", "公式の数値を確認できなかったため一般的な目安で設計", "レビュー指摘を依頼者に連絡"],
    ["MUSE FW 100µF/100V の在庫", "Digi-Key で在庫表示が不明瞭", "代替: MUSE KW 100µF/100V (UKW2A101MPD)。サイズ要確認"],
])}

## 9. 使い方 (完成後の取り扱い)

1. PHANTOM を OFF にして電源を入れる
2. マイクと録音機をつなぎ、録音機をミュート
3. PHANTOM を ON → LED が点いてから約 10秒待ってミュート解除
4. 終了時: ミュート → PHANTOM OFF → LED が消えるのを待つ (約 3秒) → 外す・電源を切る

## 10. 同梱ファイル

{table(["ファイル", "内容"], [
    ["製作者向け資料/ (このフォルダ)", "この資料、組立図、パネル図、イメージ"],
    ["発注データ/", "JLCPCB・JLCCNC の発注ファイル、発注手順、国内購入リスト"],
    ["回路図.pdf", "回路図 (拡大可能)"],
    ["BOM.csv", "全部品表"],
    ["kicad/", "KiCad 10 プロジェクト (回路図・基板・専用フットプリント)"],
    ["筐体/", "筐体の STEP・図面・展開図・シルク DXF"],
    ["シミュレーション/結果.html", "回路シミュレーションの結果 (参考)"],
])}
"""
    mdp = os.path.join(OUTD, "製作者向け資料.md")
    open(mdp, "w", encoding="utf-8").write(md)
    md2html.refresh()

    # ---- 製作データ一式 (zip)
    zp = os.path.join(ROOT, sch.PROJECT + "_製作データ.zip")
    items = ["製作者向け資料", "発注データ", "kicad", "筐体", "シミュレーション", "回路図.pdf", "回路図.png", "基板3D.png", "基板3D_斜め.png", "原寸チェック", "設計根拠",
             "基板レイアウト.png", "BOM.csv", "部品購入リスト.html", "はじめにお読みください.html"]
    skip_ext = (".md", ".kicad_prl", ".lck", ".bak")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for it in items:
            p = os.path.join(ROOT, it)
            if os.path.isfile(p):
                z.write(p, it)
                continue
            for dp, dn, fn in os.walk(p):
                dn[:] = [d for d in dn if not d.startswith((".", "_")) and d not in ("out",)]
                for f in fn:
                    if f.endswith(skip_ext) or f.startswith("."):
                        continue
                    full = os.path.join(dp, f)
                    z.write(full, os.path.relpath(full, ROOT))
    print("written:", os.path.relpath(mdp, ROOT).replace(".md", ".html"), "/", os.path.basename(zp),
          f"({os.path.getsize(zp) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
