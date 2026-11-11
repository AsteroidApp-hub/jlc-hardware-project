# 回路図と基板の生成 (KiCad 9/10)

## 回路図: `tools/gen_schematic.py`

構成 (上から順に):

1. ライブラリ読み込み (`lib_block`, `parse_pins`)。`extends` で派生したシンボルは使えないので、派生元を使う
   (例: UC3843 は `Regulator_Controller:UC3842_SOIC8` を使い、値を UC3843AN、フットプリントを DIP-8 にする)。
2. `FP` (フットプリント名の辞書)、`SHOP` / `EXTRA_BUY` / `OTHER_BUY` (購入先)。
3. **`PARTS`** … `P(ref, シンボル, 値, FPキー, {ピン番号: ネット名}, mpn=, lcsc=, note=, asm="JLC"|"HAND"|"DNP"|"-", buy=)`。
   `R()` `C()` `CP()` の短縮形あり。`asm="JLC"` は LCSC 番号必須。ネット名 `GND` は電源記号になる。
4. 描画: `put(ref, アンカーピン, x, y, 回転, mirror, 文字位置)` で配置 (単位 2.54mm グリッド)、`WIRES` に配線 (水平・垂直のみ)、
   `GNDS` / `FLAGS` / `NOCONN` / `LABELS` / `TEXTS`。チャンネルの繰り返しは関数で座標をずらす。
5. `write_outputs()` で BOM・JLC 用 BOM・購入リスト・HTML。`expected_nets.txt` (期待するネット) も出す。

### 照合 (必ずやる)

```sh
python3 tools/gen_schematic.py
sh tools/render_sch.sh <作業dir>  # ネットリスト照合 + ERC (件数と種類を表示) + 回路図.pdf
```

- `check_netlist.py` はピンの組とネット名の両方を比べ、期待に無い余計なネット (`EXTRA`) も問題として数える。`MISMATCH` が出たら配線かラベルの位置ずれ。
- よくある原因: ラベルがピン先端・配線上に無い (`label_dangling`)、向きを反転したコネクタでピン先端が反対側、配線の端点が別の配線の途中に
  乗って意図しない接続、抵抗のピン 1/2 の向きが PARTS と逆。
- `power_pin_not_driven` は電源入力ピン (IC の VCC など) が抵抗経由で給電されていると出る。そのネットの配線端点に `PWR_FLAG` を置く
  (配線の途中に置くと接続されない)。
- 最後に PDF を画像化して目で見る。文字の重なり、ピン番号と配線の重なりを直す。

## 基板: `tools/gen_pcb.py`

- 寸法は筐体側 (`筐体/pcb_constraints.json`) から受け取る: 基板外形、取付穴、パネル内面の位置、コネクタの中心、スイッチ・LED・DC ジャックの位置。
- 基板座標は「画面の下 = 前面パネル」になるよう `by = (前端の筐体y) − y` で反転する。左右を反転させると部品の向きが鏡像になるので注意。
- `POS[ref] = (x, y, 回転)` で配置。回転は KiCad の向き (画面上で反時計回り)。パッドの位置は R(90): (fx,fy)→(fy,−fx)、R(180): (−fx,−fy)、
  R(270): (−fy,fx)。
- `--check` でコートヤード (部品の占有範囲) の重なりと基板外へのはみ出しを先に確認してから配線する。0603 の間隔は約 3.1mm、
  φ10 電解は直径 10.5mm、DO-41 は約 12.9mm の長さ。
- 自作の格子ルーター (A*) で配線。F.Cu / B.Cu、内層 2枚は GND ベタ。細線ネット (`NARROW`) と先に配線するネット (`ORDER_FIRST`) を設定する。
  SMD の GND パッドはビアで内層へ落とす。配線品質 (直角が多い) は実用上問題ないが、電流ループの短さは配置で作る。
- フットプリントのフィールド (MPN, LCSC など) も設定しておくと、DRC の回路図照合が 0 件になる。
- シルク: 値は消し、JLC 実装部品の記号は Fab 層へ移し、手はんだ部品の記号だけ印刷すると見やすい。

```sh
<KiCad python> tools/gen_pcb.py --check      # 配置だけ確認
<KiCad python> tools/gen_pcb.py              # 配置 + 配線
kicad-cli pcb drc --severity-all --schematic-parity --format json -o drc.json kicad/<PROJECT>.kicad_pcb
python3 tools/drc_summary.py drc.json
```

## 自作フットプリント

- `kicad/<LIB>.pretty/` に `.kicad_mod` を書き、`kicad/fp-lib-table` で `${KIPRJMOD}` 相対に登録する。
- データシートでピン位置が確定できない部品は、長穴パッドや両側に穴を開けて吸収する (例: DC ジャックの側面ピンを左右両方、
  トロイダルの足を長穴 4〜10mm)。
- `Datasheet` 欄は回路図側と一致させる (違うと DRC の回路図照合で指摘される)。

## コネクタの位置合わせ (パネル取付品)

- メーカーの STEP を build123d で読み、ピン (Y 方向の円筒) とフットプリントのパッドを照合して、フットプリント座標 ↔ 3D モデル座標の
  変換を求める。パネルに当たる面 (ねじボスの前面など) をモデルの平面から特定する。
- Neutrik AA シリーズ (NC3FAAH2 / NC3MAAH-1) の実測値: 軸は基板上面から 12.5mm、フランジ下端 = 基板上面、メスはピン 1 がパネル面から
  12.7mm 奥 (回転 270)、オスは 17.78mm 奥 (回転 180)、どちらも軸から x+3.81。パネル穴 Φ22 以上 (22.5 推奨)、取付穴 Φ3.2 × 2
  (外から見て左上・右下)。
- KiCad の XLR フットプリントには 3D モデルが付かない (未同梱) ことがある。メーカーの STEP は再配布しない。
