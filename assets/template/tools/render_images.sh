#!/bin/sh
# 回路図・基板の画像を書き出す (資料の入口ページ・製作者向け資料で使う)。
# 使い方: sh tools/render_images.sh            (プロジェクト直下に書き出す)
#         OUT=<フォルダ> sh tools/render_images.sh  (別の場所に書き出して確認)
#   回路図.png        … 回路図.pdf (tools/render_sch.sh が作る) を画像に
#   基板3D.png        … KiCad の 3D 表示 (真上から)
#   基板3D_斜め.png   … KiCad の 3D 表示 (斜め上から。部品の高さが分かる)
#   基板レイアウト.png … 配線 (赤 = 表面、青 = 裏面) とシルク
set -e
# Python の呼び名 (Windows では python3 が無く python のことがある。環境変数 PYTHON で指定も可)
PY="${PYTHON:-$(command -v python3 >/dev/null 2>&1 && echo python3 || echo python)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT}"
mkdir -p "$OUT"
P="$(cd "$ROOT/tools" && "$PY" -c 'from project import PROJECT; print(PROJECT)' 2>/dev/null || echo P48_2CH)"
PCB="$ROOT/kicad/$P.kicad_pcb"
TMP="$(mktemp -d)"

topng() {   # PDF -> PNG (macOS は sips、それ以外は pdftoppm)
  if command -v sips >/dev/null; then sips -s format png -Z "$3" "$1" --out "$2" >/dev/null
  else pdftoppm -png -singlefile -scale-to "$3" "$1" "${2%.png}"; fi
}
q() { grep -v -i fontconfig || true; }

[ -f "$ROOT/回路図.pdf" ] && topng "$ROOT/回路図.pdf" "$OUT/回路図.png" 4000 && echo "回路図.png"

kicad-cli pcb render --side top --width 1800 --height 1600 --quality high \
  -o "$OUT/基板3D.png" "$PCB" 2>&1 | q >/dev/null
echo "基板3D.png"
kicad-cli pcb render --side top --width 1800 --height 1400 --quality high --perspective \
  --rotate '-40,0,-25' --zoom 0.9 -o "$OUT/基板3D_斜め.png" "$PCB" 2>&1 | q >/dev/null
echo "基板3D_斜め.png"

kicad-cli pcb export pdf --mode-single --layers B.Cu,F.Cu,F.Silkscreen,Edge.Cuts --exclude-value \
  --bg-color '#ffffff' --drill-shape-opt 2 -o "$TMP/layout.pdf" "$PCB" 2>&1 | q >/dev/null
# ページ (A4 横、1:1) から基板の外形 (Edge.Cuts) の範囲だけ切り抜く
PX=8000   # A4 の長辺 297mm を何ピクセルにするか
topng "$TMP/layout.pdf" "$TMP/page.png" $PX
CROP="$("$PY" - "$PCB" $PX <<'PY'
import re, sys
t = open(sys.argv[1]).read()
xs, ys = [], []
for m in re.finditer(r'\((?:gr_line|gr_rect|gr_arc)\s(.*?)\(layer "Edge\.Cuts"\)', t, re.S):
    for x, y in re.findall(r'\((?:start|end|mid)\s+([-\d.]+)\s+([-\d.]+)\)', m.group(1)):
        xs.append(float(x)); ys.append(float(y))
k = int(sys.argv[2]) / 297.0          # px / mm
m = 2.0                               # 余白 mm
x0, y0 = (min(xs) - m) * k, (min(ys) - m) * k
w, h = (max(xs) - min(xs) + 2 * m) * k, (max(ys) - min(ys) + 2 * m) * k
print(int(h), int(w), int(y0), int(x0))
PY
)"
set -- $CROP
if command -v sips >/dev/null; then
  sips -c "$1" "$2" --cropOffset "$3" "$4" "$TMP/page.png" --out "$TMP/crop.png" >/dev/null
  sips -Z 2200 "$TMP/crop.png" --out "$OUT/基板レイアウト.png" >/dev/null
else
  cp "$TMP/page.png" "$OUT/基板レイアウト.png"   # 切り抜きは sips (macOS) がある場合のみ
fi
echo "基板レイアウト.png"
rm -rf "$TMP"
