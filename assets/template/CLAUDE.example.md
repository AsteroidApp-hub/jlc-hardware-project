# 2ch P48 ファンタム電源

コンデンサーマイク向けの 2ch 外付けファンタム電源。DC 12〜18V 入力 (外部リニア電源を推奨) → UC3843 昇圧 (51.5V) → RC + リップルフィルター → +48V → 6.81kΩ 0.1% で P48 給電、XLR スルー。基板は JLCPCB (SMD実装)、筐体は JLCCNC の板金。

状況 (2026-11-10): 工程1〜5 (部品確定・シミュレーション・筐体・基板・発注データ) まで完了。次は発注 → 組立 → 実機確認。

## ユーザーの方針 (必ず守る)

- 返答は日本語。
- **資料は HTML で渡す** (Markdown を読まない人向け)。 `.md` を書いたら `python3 tools/md2html.py` で HTML にする (各ジェネレーターは最後に自動で呼ぶ)。入口は `はじめにお読みください.html`。
- JLCPCB で実装する部品は **基本部品 (Basic Parts) のみ**。それ以外は国内通販 (秋月電子通商・Digi-Key Japan) で買って手はんだ。購入先はリンク付きでまとめる。
- **フェライトビーズは使わない。**
- 信号経路にはできるだけ良い部品 (電解: ニチコン MUSE FW 100V、フィルム: WIMA MKP4、給電抵抗: TE YR1 0.1% 15ppm)。コストは抑える。
- 本体に電源スイッチは無し (外部リニア電源側で入切)。前面に **PHANTOM スイッチ (MS-500A-B ON-ON)** を J2 (XH 3P) 経由で付け、リップルフィルターの基準 (VBASE) を R13 側 / R18 側に切り替えて +48V を約2秒でゆっくり上下させる (+48V を直接スイッチしない)。LED はファンタム表示。
- 電源は外部リニア電源 12V または 18V。24V は IRFU120N のゲートが定格 ±20V を超えるため非対応 (使うならゲート保護の追加が必要)。入力TVS は P6KE24CA。
- MUSE ES (秋月の音響用無極性) は最大 50V のため P48 経路には使えない。MUSE KZ・ELNA Silmic II の 63V 品は国内通販で入手できなかった (2026-11)。

## フォルダ

| パス | 内容 |
|---|---|
| `tools/gen_schematic.py` | **回路の唯一の定義 (PARTS)**。回路図 `kicad/P48_2CH.kicad_sch`、`BOM.csv`、`JLCPCB_BOM.csv`、`部品購入リスト.md/.html` を生成 |
| `tools/gen_pcb.py` | 基板 (配置 POS + 自作の格子ルーター) → `kicad/P48_2CH.kicad_pcb`。寸法は `筐体/pcb_constraints.json` から読む |
| `tools/enclosure/gen_enclosure.py` | 板金筐体 (build123d) → `筐体/` の STEP・図面PDF・展開図DXF・シルクDXF・`pcb_constraints.json` |
| `tools/enclosure/fit_check.py` | 基板の STEP を筐体に入れて干渉・高さを確認、`筐体/組立プレビュー.png` |
| `tools/sim/build.py`, `run_all.py` | PARTS から ngspice ネットリストを作り T1〜T4 を実行 → `シミュレーション/` |
| `tools/export_fab.py` | `発注データ/` (JLCPCB ガーバー zip・BOM・CPL、JLCCNC 一式、国内購入リスト) |
| `tools/md2html.py` | Markdown → HTML、入口ページ生成 |
| `tools/handover.py` (+ `dump_pcb.py`) | 製作者向け資料 (`製作者向け資料/`、組立図・パネル図・寸法表を自動生成) と `P48_2CH_製作データ.zip`。実装は別の製作者が行う想定 |
| `kicad/Custom.pretty/` | 自作フットプリント (MJ-179PH、TCV-101M-3A)。`kicad/fp-lib-table` で登録 |
| `発注データ/発注手順.md` | 手書き。発注設定・組立順・動作確認手順 |
| `筐体/JLCCNC発注メモ.md` | 手書き。JLCCNC の設定と備考欄の英文 |

`.kicad_sch` / `.kicad_pcb` はジェネレーターが毎回上書きする。修正はスクリプト側で行う (KiCad で手修正したらスクリプトは再実行しない)。

## 再生成の手順と環境

KiCad 10 (`kicad-cli` は PATH にある)。ngspice-47。システムの python3 (3.14) には numpy が無い。

```sh
# 1) 回路図・BOM・購入リスト (依存なし)
python3 tools/gen_schematic.py
tools/render_sch.sh <作業dir>      # ネットリスト照合 (expected_nets.txt) + 回路図.pdf

# 2) 筐体 (要 build123d)。CAD 用の venv はなければ作る:
#    uv venv -p 3.12 <venv> && uv pip install --python <venv>/bin/python build123d ezdxf matplotlib numpy pyvista
NEUTRIK_STEP_DIR=<Neutrik STEP フォルダ> <venv>/bin/python tools/enclosure/gen_enclosure.py

# 3) 基板 (KiCad 同梱 Python)
<KiCad python (python3 tools/kicad_env.py で確認)> tools/gen_pcb.py [--check]
kicad-cli pcb drc --severity-all --schematic-parity --format json -o drc.json kicad/P48_2CH.kicad_pcb
python3 tools/drc_summary.py drc.json

# 4) 筐体との組立確認
kicad-cli pcb export step --subst-models -o board.step kicad/P48_2CH.kicad_pcb
<venv>/bin/python tools/enclosure/fit_check.py board.step <Neutrik STEP フォルダ>

# 5) シミュレーション (numpy/matplotlib が要るので venv の python で。REUSE=1 で既存結果を再利用)
<venv>/bin/python tools/sim/run_all.py [T1 T2 T3 T4]

# 6) 発注データ
python3 tools/export_fab.py

# 7) 製作者向け資料と製作データ zip (要 build123d・matplotlib・ezdxf。最後に実行)
<venv>/bin/python tools/handover.py
```

Neutrik STEP (干渉チェック用、再配布しない): `https://www.neutrik.com/media/12461/download/nc3faah2.stp`、`https://www.neutrik.com/media/13363/download/3-D%20NC3MAAH-1.stp`

## 確認済みの設計事実 (再調査しなくてよい)

- JLC 基本部品の確認は JLCPCB の API (`selectSmtComponentList`、`componentLibraryType: "base"`)。基本部品に昇圧IC・100V MOSFET・電解・0.1%抵抗・フェライト以外のTVSは無い。
- Neutrik AA シリーズ: 軸は基板上面から 12.5mm、フランジ下端 = 基板上面。メス NC3FAAH2 はパネル当たり面 (ねじボス前面) がモデル z=5.5、オス NC3MAAH-1 は z=0。フットプリント配置: メス回転270・ピン1はパネル面から 12.7mm 奥、オス回転180・17.78mm 奥、どちらも軸から x+3.81。パネル穴 Φ22.5、取付穴 Φ3.2 は外から見て左上/右下 (後面はグローバル座標で右上/左下)。
- 基板座標: bx = 筐体x − 5.5、by = 88.5 − 筐体y (画面の下が前面)。基板 96×86mm、上面は筐体底面から 9.1mm。
- MJ-179PH: ピンは前面から 7.7 / 10.75 / 13.7mm、側面ピン横 4.9mm (左右どちらか未確定 → 両側に穴)。ジャック中心は基板上面から 6.5mm。
- TCV-101M-3A: ピン間隔の記載なし → 長穴 (約4〜10mm)。LED フットプリントは LED 中心が基板上面から 2.0mm。
- JLC CPL 補正: SOT-23 は −90° (`cpl_rotations_db.csv`)。SMA・SOD-123・チップ部品は 0。
- JLCCNC: STEP 必須、A5052 0.5〜6mm、圧入ナット M2.5〜M10 可、シルクは曲げ後の形の DXF (二重線フォント)。曲げ制約の数値は公式ページで読めなかった。

## シミュレーションの注意 (ngspice の収束)

- 電解モデルに ESL を入れない。ESR はコンデンサの P 側に置く。
- UC3843 モデルのラッチは XSPICE ではなくアナログ等価 (G + C)。比較器・UVLO は tanh で滑らかに。
- T1 は `method=gear` を使わない (極端に遅くなる)。マイクモデルの電流は電圧に応じて頭打ち (`tanh`) にする。

## 未確定・実物で確認すること

- トロイダルの足の間隔、電源スイッチ MS-500K-B の奥行き (前パネルから約18mm以内)。
- JLCPCB の配置プレビューで Q2/Q3・D1/D3/D4/D5 の向き。JLCCNC のレビュー指摘。
- 外観 (黒アルマイト・白文字・パネルの文字・背面の L/R の向き) は仮決め。
- 価格・在庫は 2026-11-10 時点。
