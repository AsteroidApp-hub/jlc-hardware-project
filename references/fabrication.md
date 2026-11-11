# 発注データ (JLCPCB / JLCCNC / 国内通販)

`tools/export_fab.py` が `発注データ/` にまとめる。

## JLCPCB

- ガーバー: `kicad-cli pcb export gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts --subtract-soldermask --check-zones`
- ドリル: `kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-separate-th --excellon-oval-format alternate`
- CPL: `kicad-cli pcb export pos --side front --format csv --units mm --exclude-dnp` を JLC 形式 (Designator, Mid X, Mid Y, Layer, Rotation)
  に変換し、JLC 実装部品だけにする。座標は KiCad の値 (Y が負) のままでよい (ガーバーと同じ座標系)。
- **向きの補正**: kicad-jlcpcb-tools が使う `cpl_rotations_db.csv`
  (https://raw.githubusercontent.com/matthewlai/JLCKicadTools/master/jlc_kicad_tools/cpl_rotations_db.csv) を参照する。
  例: `^SOT-23` は −90°、SMA・SOD-123・チップ抵抗/コンデンサは 0。使うパッケージの行を `ROT_CORR` に書く。
  それでも発注時は配置プレビューで極性部品 (トランジスタ・ダイオード) の向きを確認してもらう。
- BOM: Comment, Designator, Footprint, LCSC Part #。BOM と CPL の部品が 1対1 か確認 (スクリプトが自動で止まる)。
- 書き出した後にガーバーを読み直して外形寸法を確認する (座標は前の行の値を引き継ぐ書式なので、その扱いをしないと誤った寸法になる)。
- 主な設定: 層数、板厚 1.6、表面処理 (ENIG 推奨)、Remove Order Number、PCBA は Economic・Top・Confirm Parts Placement = Yes。

## JLCCNC

- 部品ごとの STEP、図面 PDF (圧入ナット)、シルク DXF、展開図 DXF、発注メモ (設定と備考欄の英文)。
- 雛形の発注メモ: `assets/template/JLCCNC発注メモ.example.md`。

## 国内通販

- `部品購入リスト.md/.html` (gen_schematic が生成)。ショップごとに小計、税込/税抜を明記。
- 手順書 (`発注手順.md`) に「JLCPCB の設定」「手はんだの順番と極性」「組み込み」「通電後の確認 (測定点と期待値)」「使い方」を書く。
  雛形: `assets/template/発注手順.example.md`。

## 費用の伝え方

国内部品は購入リストの確認値、JLCPCB・JLCCNC は推定の幅で示し、「データをアップロードすれば数分で自動見積もりが出る (注文確定まで無料)」と
確認方法を添える。為替の前提を書く。
