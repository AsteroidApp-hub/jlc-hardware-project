#!/usr/bin/env python3
"""外観とパネル配置の定義 (回路図より先に決める)。依存ライブラリなし。

ここで決めること: 筐体の外形、パネルに出る部品 (コネクター・スイッチ・LED など) の位置と穴、パネルの印刷、
基板の構成 (電源部を音声と同じ基板にするか別基板にするか)。
筐体 (tools/enclosure/gen_enclosure.py) と基板 (gen_pcb.py が読む 筐体/pcb_constraints.json) は、ここの値を使う。
配置を変えたら、このファイルだけを直して「筐体 → 基板 → 組立確認 → 画像」を作り直す。回路図は部品が変わらない限り作り直さない。

実行すると、外から見た前面・後面の配置図と確認用のページを作る (CAD の環境は要らない):
  python3 tools/panel_layout.py   → パネル配置/前面.svg・後面.svg・パネル配置.md (+ .html)

座標: 筐体の 左・前・下 の外側の角が原点。x = 幅 (右が+)、z = 高さ (底面から)。
前面は外から見て x がそのまま左→右。後面は外から見ると左右が逆になる (図とシルクは X − x で描く)。
"""
import os, sys

# ------------------------------------------------------------------ 基板の構成
# "same"     = 電源部 (昇圧など) と音声の回路を 1 枚の基板に載せる (雛形はこちら)
# "separate" = 電源部を別基板にする (2 枚を配線でつなぐ。雛形は 1 枚の構成なので、選んだら基板を 2 つに分けて作る)
POWER_BOARD = "same"

# ------------------------------------------------------------------ 外形と基板の高さ (mm)
T = 1.5                 # 板厚 (A5052)
X = 107.0               # ボトムの外幅
Y = 91.0                # 奥行き (前後パネルの外面間)
H_IN = 36.0             # 内寸の高さ (底板の上面から天板の下面)
STANDOFF = 6.0          # 基板のスペーサーの高さ
PCB_T = 1.6             # 基板の厚さ
PCB_TOP = T + STANDOFF + PCB_T   # 基板の上面の高さ (基板に付く部品の高さの基準)

# ------------------------------------------------------------------ パネルに出る部品
# 基板に付く部品 (XLR・LED・DC ジャック) の高さは「基板の上面からの高さ」で決まる (部品の寸法で決まり、自由には動かせない)。
# パネルに付く部品 (スイッチ) は高さも自由に決められる。
XLR_HOLE = 22.5                       # XLR のパネル穴 (Neutrik AA: 22 以上)
XLR_SCREW = 3.2                       # XLR の取付穴 (Neutrik: 3.2 以上)
XLR_FLANGE = 26.0                     # XLR のフランジ (パネル側の四角) の一辺 (Neutrik AA の目安。データシートで確かめる)
XLR_AXIS_Z = PCB_TOP + 12.5           # Neutrik AA の軸: 基板の上面から 12.5mm
XLR_X = {"L": 21.0, "R": 53.0}        # 各チャンネルの XLR の中心 x (前面の入力と後面の出力で同じ x)
SW_POS = (80.0, 25.0)                 # PHANTOM スイッチ (x, z)。パネル取付 (MS-500A-B、M6 ブッシュ)
SW_HOLE = 6.2
LED_POS = (93.0, PCB_TOP + 2.0)       # 3mm LED (横向き。LED の中心が基板の上面から 2.0mm)
LED_HOLE = 3.2
DC_POS = (90.0, PCB_TOP + 6.5)        # DC ジャック MJ-179PH (中心が基板の上面から 6.5mm)。後面
DC_HOLE = 8.5

# 配置図と確認ページに出す一覧 (パネル, 名前, 種類, x, z, 穴径, 取付, 補足)
PANEL_PARTS = [
    ("front", "MIC IN L", "XLR メス (NC3FAAH2)", XLR_X["L"], XLR_AXIS_Z, XLR_HOLE, "基板", "入力"),
    ("front", "MIC IN R", "XLR メス (NC3FAAH2)", XLR_X["R"], XLR_AXIS_Z, XLR_HOLE, "基板", "入力"),
    ("front", "PHANTOM", "トグルスイッチ (MS-500A-B)", SW_POS[0], SW_POS[1], SW_HOLE, "パネル", "上 = ON / 下 = OFF"),
    ("front", "48V", "LED 3mm 緑", LED_POS[0], LED_POS[1], LED_HOLE, "基板", "ファンタム表示"),
    ("rear", "OUTPUT L", "XLR オス (NC3MAAH-1)", XLR_X["L"], XLR_AXIS_Z, XLR_HOLE, "基板", "出力"),
    ("rear", "OUTPUT R", "XLR オス (NC3MAAH-1)", XLR_X["R"], XLR_AXIS_Z, XLR_HOLE, "基板", "出力"),
    ("rear", "DC IN", "DC ジャック 2.1mm (MJ-179PH)", DC_POS[0], DC_POS[1], DC_HOLE, "基板", "12〜18V センタープラス"),
]

# パネルの印刷 (シルク)。パネルを外から見た座標 (u: 左→右, w: 下→上)。前面は u = x、後面は u = X − x
SILK = {
    "front": [("MIC IN", 37.0, 35.3, 2.5), ("L", XLR_X["L"], 6.0, 3.5), ("R", XLR_X["R"], 6.0, 3.5),
              ("PHANTOM", SW_POS[0], 34.3, 2.4), ("ON", SW_POS[0], 31.4, 1.8), ("OFF", SW_POS[0], 18.4, 1.8),
              ("48V", LED_POS[0], LED_POS[1] + 4.0, 2.6), ("P48 2CH", 98.0, 33.6, 2.0)],
    "rear": [("OUTPUT", X - 37.0, 35.3, 2.5), ("L", X - XLR_X["L"], 6.0, 3.5), ("R", X - XLR_X["R"], 6.0, 3.5),
             ("DC 12-18V", X - DC_POS[0], DC_POS[1] + 7.5, 2.4), ("+  (o-  -", X - DC_POS[0], DC_POS[1] - 8.0, 2.2)],
}


# ------------------------------------------------------------------ 配置図 (SVG) と確認ページ
def check():
    """穴がパネルからはみ出していないか、穴どうしが近すぎないかを調べる"""
    msgs = []
    hb = T + H_IN
    for side in ("front", "rear"):
        items = [p for p in PANEL_PARTS if p[0] == side]
        for _, name, _, x, z, d, _, _ in items:
            r = XLR_FLANGE / 2 if d >= XLR_HOLE else d / 2 + 1.0   # XLR はフランジ (取付の四角) の大きさで見る
            if x - r < T + 2 or x + r > X - T - 2 or z - r < T + 1 or z + r > hb - 1:
                msgs.append(f"{side}: {name} がパネルの端に近すぎるか、はみ出している (x={x}, z={z:.1f})")
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                gap = ((a[3] - b[3]) ** 2 + (a[4] - b[4]) ** 2) ** 0.5 - (a[5] + b[5]) / 2
                need = 6.0 if max(a[5], b[5]) >= XLR_HOLE else 3.0
                if gap < need:
                    msgs.append(f"{side}: {a[1]} と {b[1]} の穴の間が {gap:.1f}mm (目安 {need}mm 以上)")
    return msgs


def svg(side):
    hb = T + H_IN + T
    sc, m, below = 5.0, 12.0, 27.0          # 1mm = 5px、余白、パネルの下の説明欄 (mm)
    W, H = X * sc + 2 * m * sc, (hb + m + below) * sc
    u = (lambda x: x) if side == "front" else (lambda x: X - x)
    px = lambda uu: (m + uu) * sc
    pz = lambda z: (m + hb - z) * sc
    pcb_u0 = 5.5 if side == "front" else X - 101.5
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" '
         'font-family="sans-serif">',
         f'<rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" fill="#ffffff"/>',
         f'<text x="{px(0):.1f}" y="{pz(hb) - 14:.1f}" fill="#333" font-size="20">'
         f'{"前面" if side == "front" else "後面"} (外から見た図)  幅 {X:.0f} × 高さ {hb:.1f} mm</text>',
         f'<rect x="{px(0):.1f}" y="{pz(hb):.1f}" width="{X * sc:.1f}" height="{hb * sc:.1f}" fill="#2b2b2b" rx="8"/>',
         # 基板の位置 (緑の破線)
         f'<rect x="{px(pcb_u0):.1f}" y="{pz(PCB_TOP):.1f}" width="{96 * sc:.1f}" '
         f'height="{PCB_T * sc:.1f}" fill="none" stroke="#3fae5a" stroke-dasharray="6 4" stroke-width="2"/>']
    parts = sorted([p for p in PANEL_PARTS if p[0] == side], key=lambda p: u(p[3]))
    for k, (_, name, kind, x, z, d, mount, note) in enumerate(parts):
        cx, cz = px(u(x)), pz(z)
        if d >= XLR_HOLE:   # XLR: フランジ (点線) と取付穴 (外から見て左上と右下)
            f = XLR_FLANGE * sc
            o.append(f'<rect x="{cx - f / 2:.1f}" y="{cz - f / 2:.1f}" width="{f:.1f}" height="{f:.1f}" fill="none" '
                     'stroke="#8a8a8a" stroke-dasharray="4 3" stroke-width="1.5"/>')
            for dx, dz in ((-9.9, 9.9), (9.9, -9.9)):
                o.append(f'<circle cx="{px(u(x) + dx):.1f}" cy="{pz(z + dz):.1f}" r="{XLR_SCREW / 2 * sc:.1f}" fill="#d9d9d9"/>')
        o.append(f'<circle cx="{cx:.1f}" cy="{cz:.1f}" r="{d / 2 * sc:.1f}" fill="#d9d9d9" stroke="#ffffff" stroke-width="2"/>')
        # 部品名はパネルの下に出し、引き出し線でつなぐ (印刷の文字と重ねない)
        ly = pz(0) + (8 + 7 * (k % 2)) * sc
        o.append(f'<line x1="{cx:.1f}" y1="{cz:.1f}" x2="{cx:.1f}" y2="{ly - 16:.1f}" stroke="#e0a800" stroke-width="1.5"/>')
        o.append(f'<circle cx="{cx:.1f}" cy="{cz:.1f}" r="3" fill="#e0a800"/>')
        o.append(f'<text x="{cx:.1f}" y="{ly:.1f}" fill="#8a6100" font-size="16" text-anchor="middle">{name}</text>')
    for text, uu, w, h in SILK[side]:
        o.append(f'<text x="{px(uu):.1f}" y="{pz(w):.1f}" fill="#ffffff" font-size="{h * sc * 0.9:.1f}" '
                 f'text-anchor="middle" dominant-baseline="middle">{text}</text>')
    o.append(f'<text x="{px(0):.1f}" y="{H - 32:.1f}" fill="#3fae5a" font-size="15">'
             f'緑の破線 = 基板 (上面は底から {PCB_TOP:.1f}mm)。基板に付く部品は、高さが部品の寸法で決まる</text>')
    o.append(f'<text x="{px(0):.1f}" y="{H - 10:.1f}" fill="#555" font-size="15">'
             '白い文字 = パネルの印刷。点線の四角 = XLR のフランジ (取付の四角い部分)</text>')
    o.append("</svg>")
    return "\n".join(o)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "パネル配置")
    os.makedirs(out, exist_ok=True)
    for side, fn in (("front", "前面.svg"), ("rear", "後面.svg")):
        with open(os.path.join(out, fn), "w", encoding="utf-8") as f:
            f.write(svg(side))
    issues = check()
    rows = "\n".join(f"| {'前面' if s == 'front' else '後面'} | {n} | {k} | {x:.1f} | {z:.1f} | Φ{d} | {mnt} | {note} |"
                     for s, n, k, x, z, d, mnt, note in PANEL_PARTS)
    md = f"""# パネル配置 (仮決め)

回路図を作る前に、ボタン・コネクター・LED の位置と、パネルの印刷を決めます。
位置を変えたいときは、この図を見ながら「スイッチをもう少し右へ」「LED を左側へ」のように伝えてください。

![前面](前面.svg)

![後面](後面.svg)

## 部品と位置

x は外から見た前面の左端からの距離 (後面も前面と同じ基準で、図では左右が逆に見えます)。z は底面からの高さ。単位は mm。
「基板」と書いた部品は基板に付くので、高さは部品の寸法で決まります (自由に動かせるのは横方向だけです)。

| 面 | 名前 | 部品 | x | z | 穴 | 取付 | 補足 |
|---|---|---|---:|---:|---:|---|---|
{rows}

## 基板の構成

{"電源部 (昇圧など) と音声の回路を 1 枚の基板に載せます。" if POWER_BOARD == "same" else "電源部を別基板にします (2 枚を配線でつなぎます)。"}

## 自動チェック

{chr(10).join("- " + m for m in issues) if issues else "穴がパネルからはみ出す所や、穴どうしが近すぎる所はありません。"}

筐体の大きさ: 幅 {X:.0f} × 奥行き {Y:.0f} × 高さ 約 {T * 2 + H_IN:.0f} mm (内寸の高さ {H_IN:.0f} mm)。
"""
    with open(os.path.join(out, "パネル配置.md"), "w", encoding="utf-8") as f:
        f.write(md)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import md2html
        md2html.refresh()
    except Exception as e:  # noqa: BLE001
        print("HTML にできなかった:", e)
    print("written: パネル配置/前面.svg・後面.svg・パネル配置.md")
    for m in issues:
        print("注意:", m)


if __name__ == "__main__":
    main()
