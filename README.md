# jlc-hardware-project

小型の電子機器を **要件 → 部品選定 → KiCad 回路図 → ngspice シミュレーション → 板金筐体 → 基板 → 発注データ → 資料** まで
一貫して設計するための [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) 用 Skill です。

- 基板は JLCPCB (SMD 実装は基本部品のみ)、筐体は JLCCNC の板金で作る前提
- 手はんだ部品は国内通販 (秋月電子通商・千石電商・Digi-Key Japan など) で、購入リンク付きのリストを作る
- 2ch P48 ファンタム電源の実例で一通り動いた雛形スクリプト一式 (`assets/template/`) を同梱

A Claude Code skill for end-to-end small hardware projects: KiCad schematic and PCB generated from a Python part list,
ngspice verification, sheet-metal enclosure (build123d), JLCPCB/JLCCNC fabrication files, and HTML documentation.
Documentation and comments are in Japanese.

## 必ず作るもの

1. KiCad の回路図 (1 枚にすべてつながった形、PDF/PNG 付き)
2. 基板の 3D 画像 (真上・斜め)
3. ngspice のシミュレーション (起動・リップル・周波数特性・電源 ON/OFF、定格の確認)
4. 購入リンク付きの部品リスト (送料を抑えるよう店をまとめる)
5. 原寸チェック用の基板図 (A4・1:1) と、設計の根拠 (計算とシミュレーションの対比)

## 導入

```sh
git clone <このリポジトリ> ~/.claude/skills/jlc-hardware-project
```

Claude Code を起動して「基板を作って箱に入れたい」などと話しかけると使われます。

## 必要なソフト

| ソフト | 用途 |
|---|---|
| KiCad 9 以降 (`kicad-cli`、同梱の Python) | 回路図・基板・DRC・3D 画像・ガーバー |
| ngspice | シミュレーション |
| Python 3 | ジェネレーター (回路図・購入リスト・資料は標準ライブラリのみ) |
| Python 3.12 の仮想環境 (`build123d ezdxf matplotlib numpy pyvista`) | 筐体の 3D・図面、シミュレーションのグラフ、製作者向け資料 |

macOS で動作確認しています。Linux / Windows では `tools/kicad_env.py` の KiCad の場所を環境変数 `KICAD_SHARE` / `KICAD_PYTHON` で指定してください。
画像の変換に macOS の `sips` を使う箇所があり、無い環境では `pdftoppm` (poppler) を使います。

## 構成

| パス | 内容 |
|---|---|
| `SKILL.md` | Skill 本体 (進め方・必須の成果物・工程・完了の目安) |
| `references/` | 工程ごとの詳しい手順と落とし穴 (部品選定、KiCad 生成、シミュレーション、筐体、発注、資料、実例) |
| `scripts/jlc_basic_parts.py` | JLCPCB 基本部品の検索・BOM のチェック |
| `assets/template/` | 雛形 (2ch P48 ファンタム電源)。`assets/template/README.md` に書き換える場所の説明 |

## 注意

- 価格・在庫・送料・JLCPCB/JLCCNC の条件は 2026 年 11 月時点の調査に基づきます。使う時点で確認してください。
- メーカーの 3D モデル (Neutrik の STEP など) は再配布できないため含めていません。ダウンロード先の URL のみ記載しています。
- 雛形の回路は実例であり、実機での動作を保証するものではありません。高電圧 (48V 級) を扱うので、組立・試験は注意して行ってください。
- JLCPCB、JLCCNC、KiCad、Digi-Key、各部品メーカー名は各社の商標です。この Skill は各社と関係ありません。

## ライセンス

MIT License (`LICENSE`)
