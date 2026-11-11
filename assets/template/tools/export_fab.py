#!/usr/bin/env python3
"""発注データの書き出し (JLCPCB 基板+SMD実装 / JLCCNC 筐体 / 国内購入リスト)

使い方: python3 tools/export_fab.py
出力:   発注データ/
          JLCPCB/<PROJECT>_gerber.zip   ガーバー + ドリル (4層)
          JLCPCB/<PROJECT>_BOM.csv      JLC実装部品 (基本部品のみ)
          JLCPCB/<PROJECT>_CPL.csv      部品座標 (JLCの向きに補正済み)
          JLCCNC/ ...                   筐体の STEP / 図面 / 印刷データ
          国内購入/部品購入リスト.md
"""
import csv, glob, os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_schematic as sch  # noqa: E402

ROOT = sch.ROOT
PCB = os.path.join(sch.OUT, sch.PROJECT + ".kicad_pcb")
OUT = os.path.join(ROOT, "発注データ")
J = os.path.join(OUT, "JLCPCB")
GERB = os.path.join(OUT, "_gerber_work")

# JLCPCB の部品の向きの補正 (kicad-jlcpcb-tools が使う cpl_rotations_db.csv より、この基板に該当するもの)
#   https://raw.githubusercontent.com/matthewlai/JLCKicadTools/master/jlc_kicad_tools/cpl_rotations_db.csv
ROT_CORR = [(r"^SOT-23", -90)]

LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "fontconfig" not in l.lower())
    if r.returncode != 0:
        print(out)
        raise SystemExit("failed: " + " ".join(cmd[:4]))
    return out


def main():
    # 回路図・基板の画像 (基板3D・基板3D_斜め・基板レイアウト・回路図.png) を最新の基板から作り直す
    subprocess.run(["sh", os.path.join(HERE, "render_images.sh")], check=True)
    # 原寸チェック用の基板図 (発注前に実物の部品を置いて確かめる) と、設計の根拠の資料
    subprocess.run([sys.executable, os.path.join(HERE, "print_check.py")], check=True)
    subprocess.run([sys.executable, os.path.join(HERE, "design_notes.py")], check=True)
    for d in (J, GERB):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    # ---- ガーバー + ドリル
    run(["kicad-cli", "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "--check-zones",
         "-o", GERB + "/", PCB])
    run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
         "--excellon-separate-th", "--excellon-oval-format", "alternate", "--drill-origin", "absolute",
         "-o", GERB + "/", PCB])
    files = sorted(glob.glob(os.path.join(GERB, "*")))
    zp = os.path.join(J, sch.PROJECT + "_gerber.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, os.path.basename(f))
    print("gerber zip:", [os.path.basename(f) for f in files])

    # ---- 部品座標 (CPL)
    pos = os.path.join(GERB, "pos.csv")
    run(["kicad-cli", "pcb", "export", "pos", "--side", "front", "--format", "csv", "--units", "mm",
         "--exclude-dnp", "-o", pos, PCB])
    parts = {p["ref"]: p for p in sch.PARTS}
    jlc = {r for r, p in parts.items() if p["asm"] == "JLC"}
    rows, seen = [], set()
    with open(pos, newline="") as f:
        for r in csv.DictReader(f):
            ref = r["Ref"]
            if ref not in jlc:
                continue
            pkg = r["Package"]
            rot = float(r["Rot"])
            corr = next((c for pat, c in ROT_CORR if re.search(pat, pkg)), 0)
            rows.append([ref, f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm", "Top",
                         f"{(rot + corr) % 360:.0f}", pkg, corr])
            seen.add(ref)
    with open(os.path.join(J, sch.PROJECT + "_CPL.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in sorted(rows, key=lambda r: (re.sub(r"\d", "", r[0]), int(re.sub(r"\D", "", r[0])))):
            w.writerow(r[:5])
    # ---- BOM (JLC実装分)
    shutil.copy(os.path.join(ROOT, "JLCPCB_BOM.csv"), os.path.join(J, sch.PROJECT + "_BOM.csv"))
    bom_refs = set()
    with open(os.path.join(J, sch.PROJECT + "_BOM.csv"), newline="") as f:
        for r in csv.DictReader(f):
            bom_refs |= set(r["Designator"].split(","))
    missing_cpl = sorted(bom_refs - seen)
    missing_bom = sorted(seen - bom_refs)
    corrected = sorted(r[0] for r in rows if r[6])
    print(f"CPL {len(rows)} parts / BOM {len(bom_refs)} parts / rotation-corrected: {corrected}")
    if missing_cpl or missing_bom:
        raise SystemExit(f"BOM/CPL mismatch: not in CPL {missing_cpl}, not in BOM {missing_bom}")

    # ---- 筐体 (JLCCNC) と 国内購入リスト
    cnc = os.path.join(OUT, "JLCCNC")
    shutil.rmtree(cnc, ignore_errors=True)
    os.makedirs(cnc)
    enc = os.path.join(ROOT, "筐体")
    for n in (sch.PROJECT + "_bottom.step", sch.PROJECT + "_cover.step", sch.PROJECT + "_enclosure.step", "筐体図面.pdf",
              "silk_front.dxf", "silk_rear.dxf", "flat_bottom.dxf", "flat_cover.dxf", "JLCCNC発注メモ.md"):
        shutil.copy(os.path.join(enc, n), os.path.join(cnc, n))
    dom = os.path.join(OUT, "国内購入")
    os.makedirs(dom, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "部品購入リスト.md"), os.path.join(dom, "部品購入リスト.md"))
    shutil.rmtree(GERB, ignore_errors=True)
    import md2html          # 発注データ内の資料も HTML にする
    md2html.refresh()
    print("done:", OUT)


if __name__ == "__main__":
    main()
