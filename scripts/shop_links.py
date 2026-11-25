#!/usr/bin/env python3
"""国内通販の検索ページのリンクを作る (依存ライブラリなし。ネットにはアクセスしない)。

使い方:
  python3 shop_links.py "六角スペーサー M3 6mm"          # 全店のリンク
  python3 shop_links.py --shop monotaro,marutsu "UC3843"   # 店を選ぶ
  python3 shop_links.py --md "UC3843AN"                    # Markdown のリンクで出す

モノタロウとマルツは、自動のアクセスでは検索ページも商品ページも読めない (403)。
Claude が調べるときは検索エンジン (WebSearch の allowed_domains) を使い、ここで作るリンクは
ユーザーがブラウザで開いて価格と在庫を確かめるためのもの。ボット対策をすり抜ける道具は使わない。
"""
import argparse
import urllib.parse

SHOPS = {
    "akizuki": ("秋月電子通商", "https://akizukidenshi.com/catalog/goods/search.aspx?search=x&keyword={q}"),
    "sengoku": ("千石電商", "https://www.sengoku.co.jp/mod/sgk_cart/search.php?multi={q}"),
    "digikey": ("Digi-Key Japan", "https://www.digikey.jp/ja/products/result?keywords={q}"),
    "monotaro": ("モノタロウ", "https://www.monotaro.com/s/q-{p}/"),
    "marutsu": ("マルツ", "https://www.marutsu.co.jp/GoodsListNavi.jsp?q={q}"),
}


def link(shop, keyword):
    name, tmpl = SHOPS[shop]
    return name, tmpl.format(q=urllib.parse.quote_plus(keyword), p=urllib.parse.quote(keyword))


def main():
    ap = argparse.ArgumentParser(description="国内通販の検索リンクを作る")
    ap.add_argument("keyword")
    ap.add_argument("--shop", default=",".join(SHOPS), help="カンマ区切り: " + ", ".join(SHOPS))
    ap.add_argument("--md", action="store_true", help="Markdown のリンクで出す")
    a = ap.parse_args()
    for s in [x.strip() for x in a.shop.split(",") if x.strip()]:
        if s not in SHOPS:
            raise SystemExit(f"知らない店: {s} (使えるのは {', '.join(SHOPS)})")
        name, url = link(s, a.keyword)
        print(f"- [{name}で「{a.keyword}」を検索]({url})" if a.md else f"{name}\t{url}")


if __name__ == "__main__":
    main()
