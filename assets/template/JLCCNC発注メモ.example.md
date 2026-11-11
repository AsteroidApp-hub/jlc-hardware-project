# JLCCNC 板金 発注メモ (P48 2CH 筐体)

注文ページ: https://jlccnc.com/sheet-metal-quote (板金 / Sheet Metal Fabrication)

## 部品は2つ

| 部品 | STEPファイル | 内容 |
|---|---|---|
| ボトム | `P48_2CH_bottom.step` | 底板 + 前後パネル + 左右の立ち上がり。XLR・SW・LED・DCジャックの穴、基板スペーサー穴、M3圧入ナット ×4 |
| カバー | `P48_2CH_cover.step` | 天板 + 左右側板。固定ねじ穴 ×4 |

`P48_2CH_enclosure.step` は2部品を組立位置に並べたもの (確認用)。注文は部品ごとに上の2ファイルで行う。

## 共通の設定

- Material: **Aluminum 5052**
- Thickness: **1.5 mm**
- Surface finish: **Anodizing — Black** (黒アルマイト。色は好みで変更可)
- Quantity: 1 (予備が欲しければ 2)

## ボトムだけの追加設定

- **Thread or Riveting File** に `筐体図面.pdf` を添付 (M3圧入ナットの位置と向き)
- **Surface Treatment → Silkscreen (白)** に `silk_front.dxf` と `silk_rear.dxf` を添付
  - どちらも「曲げた後のパネルを外から見た形」で描いてある (JLCCNC の指定どおり)

## 備考欄に貼る文章 (英語)

```
Bottom part:
- Please install 4 x M3 self-clinching nuts (PEM CLS-M3-1 type) in the Ø4.2 holes of the two side lips
  (y = 20 / 71 mm, z = 8.5 mm). The OUTSIDE face of each lip must stay FLUSH because the cover side wall
  sits on it, so the nut body must be on the INSIDE of the lip. Rivet nuts with a flange are not acceptable.
- White silkscreen on the front and rear panels: see silk_front.dxf / silk_rear.dxf
  (drawn as the bent panel viewed from outside).
- Bend inner radius 1.25 mm (outer 2.75 mm). Flat patterns flat_bottom.dxf / flat_cover.dxf are for reference only.
Both parts: black anodizing.
```

## 注意

- 自動見積は参考値で、JLCCNC側の手動レビュー後に価格が確定する (支払いはレビュー後)。
- 3D STEPから展開してくれるかは公式ページに明記がない。展開図 `flat_bottom.dxf` / `flat_cover.dxf` を参考として同梱してよい (Kファクター 0.44 で計算)。
- 曲げの最小フランジ長・穴と曲げの距離は公式ページでは画像のみで数値が読めなかった。レビューで指摘があれば、立ち上がりの高さ (14mm) やナット位置を調整する。
- アルマイトは絶縁なので、シャーシの接地は基板取付ねじとカバー固定ねじに入れる歯付き座金で取る。
