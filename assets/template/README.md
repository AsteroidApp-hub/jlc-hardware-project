# 雛形 (2ch P48 ファンタム電源 で動作確認済み)

新しいプロジェクトフォルダにこの中身をコピーして書き換える (`cp -R <skill>/assets/template/. <新フォルダ>/`)。

## 最初に書き換える

1. **`tools/project.py`** の `PROJECT` (ファイル名) と `TITLE` (資料のタイトル)。全スクリプトがここを読む。
2. 雛形を一度そのまま実行して環境を確かめた後に `PROJECT` を変えたら、古い `kicad/P48_2CH.*` や生成物は消してよい (ジェネレーターは毎回作り直す)。
3. 自作フットプリントのライブラリ名 `Custom` (`kicad/Custom.pretty`、`fp-lib-table`、`gen_schematic.py` の `FP` の `Custom:`、`gen_pcb.py` の `LIBDIR`) は、そのままでよい。変えるなら 4か所を揃える。
4. `README.md` と `*.example.md` は HTML 化の対象外。参考にしたら消してよい。

## ファイルと書き換える場所

| ファイル | 役割 | プロジェクトごとに書き換える部分 | そのまま使える部分 |
|---|---|---|---|
| `tools/project.py` | プロジェクト名・タイトル | 全部 | — |
| `tools/kicad_env.py` | KiCad の場所の検出 (`python3 tools/kicad_env.py` で表示) | なし (環境変数 `KICAD_SHARE` / `KICAD_PYTHON` で上書き可) | 全部 |
| `tools/gen_schematic.py` | 回路の定義 → 回路図・BOM・購入リスト | `PROJECT`、`FP`、`SHOP` / `EXTRA_BUY` / `OTHER_BUY`、**`PARTS`**、描画の `put` / `WIRES` / `GNDS` / `LABELS` / `TEXTS`、タイトル | ライブラリ読み込み、描画エンジン (`main`)、`write_outputs` |
| `tools/render_sch.sh` / `check_netlist.py` | ネットリスト照合 (不足・余計・名前違い) + ERC + PDF | なし | 全部 |
| `tools/sim/build.py` | PARTS → ngspice | `MODELS` (部品モデル)、`ESR` / `DERATE`、シンボル対応の追加、試験用に置き換えるコネクタ | 枠組み |
| `tools/sim/run_all.py` | 試験 T1〜T6 とグラフ・結果 | 試験の中身 (測るノード名・期待値) | `run` / `note` / `write_md` |
| `tools/enclosure/gen_enclosure.py` | 板金筐体 → STEP・図面・DXF・制約 JSON | 寸法定数 (`X`, `Y`, `H_IN`, `STANDOFF` …)、パネル部品の位置、`SILK`、メーカー STEP の置き方 | 曲げ・穴・展開図・図面・プレビューの関数 |
| `tools/enclosure/fit_check.py` | 基板 STEP を筐体に入れて干渉確認 | なし (XLR の配置関数は gen_enclosure) | 全部 |
| `tools/gen_pcb.py` | 配置 + 配線 → kicad_pcb | `POS` (配置)、`NARROW` / `ORDER_*`、シルク文字、許容するコートヤード重なり | 格子ルーター、配置チェック、ゾーン |
| `tools/print_check.py` | 原寸チェック用の基板図 (A4・1:1・50mm 目盛り) と手順書 | `CHECK` (実物で確かめる部品と見る点)、基板以外の確認事項 | PDF 出力・目盛り・手順の枠組み |
| `tools/design_notes.py` | 設計の根拠 (計算式・計算値・シミュレーション結果の対比、定格の余裕) | 各節の中身 (回路ごとに計算式を書き直す) | `val()` (PARTS の値を数値に)・`sim()` (結果.md から値を引く)・表の書き方 |
| `tools/drc_summary.py` | DRC 結果の要約 | なし | 全部 |
| `tools/render_images.sh` | 回路図.png・基板3D.png・基板3D_斜め.png・基板レイアウト.png (必須の画像) | 斜めの角度 (`--rotate`) くらい | 全部 |
| `tools/export_fab.py` | 発注データ一式 | `ROT_CORR`、コピーする筐体ファイル名 | 全部 |
| `tools/md2html.py` | Markdown → HTML、入口ページ | `CARDS` / `DOCS` / タイトル文 | 変換器 |
| `tools/handover.py` / `dump_pcb.py` | 製作者向け資料・組立図・zip | 仕様表・注意・`POLARITY` / `HEIGHT` / `TPS` (測定点)、検査表、確認事項 | 図の描画、寸法表の自動生成、zip |
| `kicad/Custom.pretty/` / `fp-lib-table` | 自作フットプリント | ライブラリ名・中身 | 書式の例 |
| `*.example.md` | CLAUDE.md・発注手順・JLCCNC メモの例 | 全部 (例として参考に) | — |

## 実行順

```sh
python3 tools/gen_schematic.py && sh tools/render_sch.sh <work>    # 回路図 + 照合 + ERC (problems 0 / ERC 0 件が目標)
<venv>/bin/python tools/enclosure/gen_enclosure.py                 # 筐体 (先に) → pcb_constraints.json
<KiCad python> tools/gen_pcb.py --check && <KiCad python> tools/gen_pcb.py   # 基板
kicad-cli pcb drc --severity-all --schematic-parity --format json -o drc.json kicad/<P>.kicad_pcb && python3 tools/drc_summary.py drc.json
<venv>/bin/python tools/sim/run_all.py                             # シミュレーション
python3 tools/export_fab.py                                        # 発注データ (最初に render_images.sh で画像も更新)
<venv>/bin/python tools/handover.py                                # 製作者向け資料 + zip
```

雛形のスクリプトは 実例の値のまま動く。最初にそのまま実行して環境が整っているか確かめてから書き換えるとよい。

## チャンネル数などを変えるとき

回路の繰り返し (雛形では CH L / CH R) は `gen_schematic.py` の `channel()` (部品)、`place_channel()` (配置)、`channel_wires()` (配線) を
チャンネルごとに呼んでいる。数を変えるときは、呼び出しのほかに次も直す: 電源ラインの配線の終点 (例: `R201.1`)、`TEXTS` の見出しと注記、
`OTHER_BUY` の個数 (XLR の取付ねじなど)、`gen_pcb.py` の `POS`、筐体のパネル穴。直したら必ず照合と ERC を通す。

`<KiCad python>` は `python3 tools/kicad_env.py` で表示される `KICAD_PYTHON`。
