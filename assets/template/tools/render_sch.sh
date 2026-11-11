#!/bin/sh
# 回路図を検証してPDF/PNGに書き出す。
# 使い方: sh tools/render_sch.sh <作業用ディレクトリ>   (無ければ作る。相対パスは実行した場所から)
# 1) ネットリスト照合 (expected_nets.txt)  2) ERC  3) 回路図.pdf (+ macOS なら PNG)
set -e
# Python の呼び名 (Windows では python3 が無く python のことがある。環境変数 PYTHON で指定も可)
PY="${PYTHON:-$(command -v python3 >/dev/null 2>&1 && echo python3 || echo python)}"
mkdir -p "$1"
S="$(cd "$1" && pwd)"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
P="$(cd "$TOOLS" && "$PY" -c 'from project import PROJECT; print(PROJECT)')"
cd "$TOOLS/../kicad"
[ -f "$P.kicad_sch" ] || { echo "kicad/$P.kicad_sch が無い。先に python tools/gen_schematic.py"; exit 1; }
kicad-cli sch export netlist --format kicadsexpr -o "$S/out.net" "$P.kicad_sch" 2>&1 | grep -v -i fontconfig || true
"$PY" "$TOOLS/check_netlist.py" "$S/out.net" expected_nets.txt
kicad-cli sch erc --severity-all --format json -o "$S/erc.json" "$P.kicad_sch" >/dev/null 2>&1 || true
"$PY" - "$S/erc.json" <<'PY'
import json, sys, collections
d = json.load(open(sys.argv[1]))
v = [x for s in d.get("sheets", []) for x in s.get("violations", [])]
print("ERC:", len(v), "件", dict(collections.Counter(x["type"] for x in v)))
for x in v[:20]:
    print("  ", x["type"], "-", x["description"])
PY
kicad-cli sch export pdf -o ../回路図.pdf "$P.kicad_sch" >/dev/null 2>&1
command -v sips >/dev/null && sips -s format png -Z 5600 ../回路図.pdf --out "$S/sch_page.png" >/dev/null 2>&1 || true
echo "回路図.pdf を書き出した (PNG: $S/sch_page.png)"
