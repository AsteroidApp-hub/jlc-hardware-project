#!/usr/bin/env python3
"""原寸チェック用の基板図 (A4・100%) と手順書を作る。依存ライブラリなし (kicad-cli を使う)。

基板を発注する前に、印刷した紙の上に実物の部品を置いて、穴の位置・足の間隔・部品の大きさが合うかを確かめるためのもの。

出力: 原寸チェック/基板_原寸.pdf … A4 に 1:1 (部品の輪郭・パッド・穴・部品番号・50mm の目盛り)
      原寸チェック/基板_原寸.png … 画面確認用
      原寸チェック/原寸チェック.md (+ .html) … 手順と、確かめる部品の一覧
使い方: python3 tools/print_check.py   (tools/export_fab.py からも呼ばれる)
"""
import os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_schematic as sch  # noqa: E402

OUTD = os.path.join(ROOT, "原寸チェック")
PCB = os.path.join(sch.OUT, sch.PROJECT + ".kicad_pcb")

# 実物で特に確かめたい部品 (未確認の寸法・自作フットプリント)。ref: 何を見るか
CHECK = {
    "L1": "**要確認**。トロイダルの足 2 本が長穴 (約4〜10mm) の範囲に入るか。本体 (φ15.5) が輪郭に収まるか",
    "J1": "**要確認**。DC ジャックの 3 本の足が穴に合うか。側面の足が左右どちらに出ているか (穴は両側にある)。前端が基板の端に揃うか",
    "J101": "XLR メス (NC3FAAH2) の足 3 本と固定ピン 2 本が穴に合うか",
    "J102": "XLR オス (NC3MAAH-1) の足 3 本と固定ピン 2 本が穴に合うか",
    "C1": "電解 φ10 が輪郭に収まるか、足の間隔 5mm",
    "C13": "電解 φ10 が輪郭に収まるか、足の間隔 5mm",
    "C18": "MUSE FW φ10 が輪郭に収まるか、足の間隔 5mm",
    "C105": "WIMA MKP4 の足の間隔 7.5mm、本体 10.3×4.5mm",
    "Q1": "TO-251 の足 3 本の間隔 (2.29mm)",
    "U1": "DIP-8 (IC ソケットを使うならソケット) の足",
    "F1": "ポリスイッチの足の間隔 5mm",
    "D2": "P6KE24CA の足の間隔 (曲げ加工の長さ)",
    "D101": "P4KE15CA の足の間隔",
    "R102": "YR1 (6.81kΩ) の足の間隔",
    "J2": "XH コネクター 3P の足",
    "LED1": "LED の足と、先端が基板の前端から少し出る位置",
}


def board_bbox(text):
    xs, ys = [], []
    for m in re.finditer(r'\((?:gr_line|gr_rect|gr_arc)\s(.*?)\(layer "Edge\.Cuts"\)', text, re.S):
        for x, y in re.findall(r'\((?:start|end|mid)\s+([-\d.]+)\s+([-\d.]+)\)', m.group(1)):
            xs.append(float(x))
            ys.append(float(y))
    return min(xs), min(ys), max(xs), max(ys)


def ruler(x0, y0):
    """50mm の目盛り (User.Drawings 層)。印刷後に定規で測って 100% か確かめる"""
    s = []
    L = 50.0
    line = '(gr_line (start {:.2f} {:.2f}) (end {:.2f} {:.2f}) (stroke (width 0.3) (type solid)) (layer "Dwgs.User"))'
    s.append(line.format(x0, y0, x0 + L, y0))
    for i in range(0, 51, 5):
        h = 3.0 if i % 10 == 0 else 1.5
        s.append(line.format(x0 + i, y0, x0 + i, y0 - h))
    txt = ('(gr_text "{}" (at {:.2f} {:.2f} 0) (layer "Dwgs.User") '
           '(effects (font (size 2 2) (thickness 0.3)) (justify left)))')
    s.append(txt.format("50 mm (この線が定規で 50mm なら 100% で印刷できている)", x0, y0 + 4))
    return "\n".join(s)


def note_text(x0, y0, w, h):
    txt = ('(gr_text "{}" (at {:.2f} {:.2f} 0) (layer "Dwgs.User") '
           '(effects (font (size 2.2 2.2) (thickness 0.35)) (justify left)))')
    return "\n".join([
        txt.format(f"{sch.PROJECT} 基板 原寸 (表面から見た図)  外形 {w:.1f} x {h:.1f} mm", x0, y0 - 9),
        txt.format("印刷は「実際のサイズ / 100%」で。「用紙に合わせる」は使わない", x0, y0 - 5),
    ])


def main():
    if not os.path.exists(PCB):
        raise SystemExit(f"{PCB} が無い。先に gen_pcb.py")
    os.makedirs(OUTD, exist_ok=True)
    t = open(PCB, encoding="utf-8").read()
    x0, y0, x1, y1 = board_bbox(t)
    add = note_text(x0, y0, x1 - x0, y1 - y0) + "\n" + ruler(x0, y1 + 8)
    k = t.rstrip().rfind(")")
    tmpd = tempfile.mkdtemp()
    tmp_pcb = os.path.join(tmpd, sch.PROJECT + ".kicad_pcb")
    with open(tmp_pcb, "w", encoding="utf-8") as f:
        f.write(t[:k] + "\n" + add + "\n)\n")
    pdf = os.path.join(OUTD, "基板_原寸.pdf")
    cmd = ["kicad-cli", "pcb", "export", "pdf", "--mode-single", "--scale", "1",
           "--layers", "Edge.Cuts,F.Fab,F.Courtyard,F.Mask,F.Silkscreen,User.Drawings",
           "--drill-shape-opt", "2", "--exclude-value", "--black-and-white", "--bg-color", "#ffffff",
           "-o", pdf, tmp_pcb]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(pdf):
        raise SystemExit("kicad-cli pcb export pdf に失敗:\n" + r.stdout + r.stderr)
    shutil.rmtree(tmpd, ignore_errors=True)
    png = os.path.join(OUTD, "基板_原寸.png")
    if shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "png", "-Z", "2400", pdf, "--out", png], capture_output=True)
    elif shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-singlefile", "-scale-to", "2400", pdf, png[:-4]], capture_output=True)

    # ---- 手順書
    byref = {p["ref"]: p for p in sch.PARTS}
    rows = []
    for ref, what in CHECK.items():
        p = byref.get(ref)
        if not p:
            continue
        buy = sch.SHOP.get(p["buy"]) if p["buy"] else None
        link = f"[{buy[0]}]({buy[2]})" if buy else "JLCPCB"
        rows.append(f"| {ref} | {p['mpn'] or p['value']} | {p['fp'].split(':')[-1]} | {what} | {link} |")
    md = f"""# 原寸チェック (基板を発注する前に)

基板を作り直すと数千円と 2〜3 週間かかります。発注の前に、**実寸で印刷した基板図の上に実物の部品を置いて**、
穴の位置・足の間隔・部品の大きさが合うかを確かめます。部品が届いてから、基板の発注前に行ってください。

![原寸の基板図](基板_原寸.png)

## 用意するもの

- [基板_原寸.pdf](基板_原寸.pdf) を A4 で印刷したもの (できれば 2 枚)
- 手はんだ部品の実物 (下の表の部品)
- 定規、つまようじ や 細い針 (穴をあける用)、段ボールか発泡スチロールの板 (下に敷く)

## 手順

1. PDF を **「実際のサイズ」「100%」** で印刷する。「用紙に合わせる」「縮小」は使わない
2. 図の下の **50mm の目盛り** を定規で測る。50mm でなければ印刷の設定を直して刷り直す
   (基板の外形 {x1 - x0:.1f} × {y1 - y0:.1f} mm も確認)
3. 紙を段ボールの上に置き、確かめる部品の穴 (白い丸・長丸) に針で穴をあける
4. 部品の足を穴に差し、**足が無理なく入るか**、**部品の本体が輪郭 (細い線) の中に収まるか**、隣の部品とぶつからないかを見る
5. 合わない部品があったら、部品名と「どの足が何 mm ずれているか」をメモして設計者 (Claude) に伝える。直してから発注する

図の見方: 細い線の四角・丸 = 部品の占める範囲 / 塗りつぶし = はんだ付けするパッド / 白い丸 = 穴 / 文字 = 部品番号。
表面 (部品を載せる面) から見た向きです。

## 確かめる部品

**要確認** の部品は、データシートで寸法が確定できなかったものです。必ず実物で確かめてください。

| 部品番号 | 部品 | フットプリント | 確かめること | 購入先 |
|---|---|---|---|---|
""" + "\n".join(rows) + """

同じ部品が複数ある場合 (電解・XLR・抵抗など) は 1 つ確かめれば十分です。

## 基板以外で確かめること

- 前面パネルの PHANTOM スイッチ (MS-500A-B) の奥行きが、パネル内側から約 18mm 以内か
- XLR コネクターのパネル穴 (Φ22.5) と取付ねじの位置は、筐体図面 (`筐体/筐体図面.pdf`) で確認
"""
    with open(os.path.join(OUTD, "原寸チェック.md"), "w", encoding="utf-8") as f:
        f.write(md)
    import md2html
    md2html.refresh()
    print("written:", os.path.relpath(pdf, ROOT), "/ 原寸チェック.md")


if __name__ == "__main__":
    main()
