#!/usr/bin/env python3
"""プロジェクト内の Markdown 資料を HTML に変換し、入口ページ (はじめにお読みください.html) を作る。

使い方: python3 tools/md2html.py            … すべて変換
        python3 tools/md2html.py a.md b.md  … 指定したファイルだけ変換
依存ライブラリなし (このプロジェクトの資料で使う書式だけに対応: 見出し・段落・箇条書き・表・コード・太字・リンク・区切り線)。
CLAUDE.md は変換しない。
"""
import datetime, glob, html, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import PROJECT, TITLE  # noqa: E402
try:
    from project import DISCLAIMER  # noqa: E402
except ImportError:
    DISCLAIMER = ""

CSS = """
:root { --bg:#ffffff; --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --head:#f6f8fa; --accent:#0969da; --code:#eff1f3; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#3d444d; --head:#151b23; --accent:#4493f8; --code:#262c36; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic", system-ui, sans-serif;
  line-height:1.75; font-size:15px; }
main { max-width: 1040px; margin: 0 auto; padding: 28px 20px 64px; }
h1 { font-size: 1.7em; border-bottom: 2px solid var(--line); padding-bottom: .3em; margin-top: 0; }
h2 { font-size: 1.3em; border-bottom: 1px solid var(--line); padding-bottom: .25em; margin-top: 2em; }
h3 { font-size: 1.1em; margin-top: 1.6em; }
a { color: var(--accent); text-decoration: none; } a:hover { text-decoration: underline; }
table { border-collapse: collapse; margin: 1em 0; display: block; overflow-x: auto; max-width: 100%; }
th, td { border: 1px solid var(--line); padding: 6px 12px; vertical-align: top; }
th { background: var(--head); text-align: left; white-space: nowrap; }
tr:nth-child(even) td { background: color-mix(in srgb, var(--head) 60%, transparent); }
code { background: var(--code); padding: .1em .35em; border-radius: 4px; font-size: .92em;
  font-family: ui-monospace, "SF Mono", Menlo, monospace; }
pre { background: var(--code); padding: 12px 14px; border-radius: 6px; overflow-x: auto; line-height: 1.5; }
pre code { background: none; padding: 0; }
hr { border: none; border-top: 1px solid var(--line); margin: 2em 0; }
p img, td img { max-width: 100%; height: auto; border: 1px solid var(--line); border-radius: 6px; background: #fff; }
ul, ol { padding-left: 1.6em; }
.meta { color: var(--muted); font-size: .85em; margin-bottom: 1.5em; }
blockquote { margin: 1em 0; padding: .6em 1em; border-left: 4px solid var(--muted); background: var(--code); }
.disclaimer { color: var(--muted); font-size: .85em; margin-top: 3em; padding-top: 1em; border-top: 1px solid var(--border, #ccc); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.card { border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; background: var(--bg); }
.card img { width: 100%; border-radius: 4px; border: 1px solid var(--line); background: #fff; }
.card h3 { margin: 0 0 .4em; font-size: 1em; }
.card p { margin: .3em 0 0; color: var(--muted); font-size: .9em; }
"""


def inline(t):
    t = html.escape(t, quote=False)
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"
    t = re.sub(r"`([^`]+)`", keep, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    # 画像 ![説明](パス) … リンクより先に処理する
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)",
               lambda m: f'<a href="{m.group(2)}"><img src="{m.group(2)}" alt="{m.group(1)}"></a>', t)

    def link(m):
        text, url = m.group(1), m.group(2)
        if url.endswith(".md"):
            url = url[:-3] + ".html"
        ext = url.startswith("http")
        return f'<a href="{url}"' + (' target="_blank" rel="noopener"' if ext else "") + f">{text}</a>"
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)
    t = re.sub(r'(?<!href=")(?<![">])(https?://[^\s<>()]+)', r'<a href="\1" target="_blank" rel="noopener">\1</a>', t)
    t = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", t)
    return t


def convert(md):
    lines = md.splitlines()
    out, i, para = [], 0, []
    title = None

    def flush():
        if para:
            out.append("<p>" + "".join(inline(x.strip()) for x in para) + "</p>")
            para.clear()
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            flush()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j]); j += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            i = j + 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            flush()
            lvl = len(m.group(1))
            if lvl == 1 and title is None:
                title = m.group(2)
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.match(r"^\s*---+\s*$", ln) and not (i + 1 < len(lines) and lines[i + 1].startswith("|")):
            flush(); out.append("<hr>"); i += 1
            continue
        if ln.lstrip().startswith(">"):
            # 引用 (> で始まる行が続く範囲を 1 つの引用にする)
            flush()
            q = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                q.append(lines[i].lstrip()[1:].strip()); i += 1
            out.append("<blockquote>" + "<br>".join(inline(x) for x in q if x) + "</blockquote>")
            continue
        if ln.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i].strip()); i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            align = []
            if len(cells) > 1 and all(re.match(r"^:?-+:?$", c) for c in cells[1]):
                align = ["right" if c.endswith(":") and not c.startswith(":") else
                         "center" if c.startswith(":") and c.endswith(":") else "" for c in cells[1]]
                head, body = cells[0], cells[2:]
            else:
                head, body = None, cells
            t = ["<table>"]
            if head:
                t.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead>")
            t.append("<tbody>")
            for r in body:
                tds = []
                for k, c in enumerate(r):
                    style = f' style="text-align:{align[k]}"' if k < len(align) and align[k] else ""
                    tds.append(f"<td{style}>{inline(c)}</td>")
                t.append("<tr>" + "".join(tds) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", ln)
        if m:
            flush()
            stack = []          # (indent, tag)
            while i < len(lines):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if not m:
                    # 継続行 (インデントされた続き)
                    if lines[i].startswith("   ") and lines[i].strip() and stack:
                        out[-1] = out[-1][:-5] + inline(lines[i].strip()) + "</li>"
                        i += 1
                        continue
                    break
                ind, tag = len(m.group(1)), "ol" if m.group(2)[0].isdigit() else "ul"
                while stack and stack[-1][0] > ind:
                    out.append(f"</{stack.pop()[1]}>")
                if not stack or stack[-1][0] < ind:
                    stack.append((ind, tag)); out.append(f"<{tag}>")
                out.append(f"<li>{inline(m.group(3))}</li>")
                i += 1
            while stack:
                out.append(f"</{stack.pop()[1]}>")
            continue
        if not ln.strip():
            flush(); i += 1
            continue
        para.append(ln)
        i += 1
    flush()
    return title, "\n".join(out)


def page(title, body, rel_root=""):
    stamp = datetime.date.today().isoformat()
    back = f'<a href="{rel_root}はじめにお読みください.html">← 資料一覧へ</a>　|　' if rel_root is not None else ""
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><main>
<div class="meta">{back}{TITLE}　|　{stamp} 生成</div>
{body}
{f'<p class="disclaimer">{html.escape(DISCLAIMER)}</p>' if DISCLAIMER else ''}
</main></body></html>
"""


def convert_file(path):
    md = open(path, encoding="utf-8").read()
    title, body = convert(md)
    title = title or os.path.splitext(os.path.basename(path))[0]
    rel = os.path.relpath(ROOT, os.path.dirname(path))
    rel = "" if rel == "." else rel + "/"
    out = os.path.splitext(path)[0] + ".html"
    open(out, "w", encoding="utf-8").write(page(title, body, rel))
    return out


def all_md():
    res = []
    for p in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True):
        rel = os.path.relpath(p, ROOT)
        b = os.path.basename(p)
        if rel.startswith(("tools", "kicad", ".")) or b.upper() in ("CLAUDE.MD", "README.MD") or b.endswith(".example.md"):
            continue
        res.append(p)
    return sorted(res)


CARDS = [
    ("回路図", "回路図.png", "回路図.pdf", "1枚にまとめた回路図 (PDFは拡大できる)"),
    ("基板レイアウト", "基板レイアウト.png", "基板レイアウト.png", "赤 = 表面の配線、青 = 裏面の配線"),
    ("基板 3D (斜め)", "基板3D_斜め.png", "基板3D_斜め.png", "部品を載せた状態のイメージ (KiCad の 3D 表示)"),
    ("基板 3D (真上)", "基板3D.png", "基板3D.png", "部品の配置を真上から"),
    ("筐体", "筐体/筐体プレビュー.png", "筐体/筐体プレビュー.png", "外形 110.4 × 91.0 × 39.0 mm、A5052 黒アルマイト"),
    ("組立確認", "筐体/組立プレビュー.png", "筐体/組立プレビュー.png", "基板と XLR を筐体に入れた状態 (干渉チェック済み)"),
    ("シミュレーション", "シミュレーション/T3_周波数特性.png", "シミュレーション/結果.html", "電源ノイズの伝達とマイク信号の通過特性"),
]
DOCS = [
    ("原寸チェック/原寸チェック.html", "原寸チェック (基板の発注前に)", "原寸で印刷した基板図に実物の部品を置いて、穴・足の間隔・大きさを確かめる"),
    ("設計根拠/設計根拠.html", "設計の根拠 (レビュー用)", "各部品の値をなぜそうしたか。計算とシミュレーション結果。設計者に回路図と一緒に渡す"),
    ("製作者向け資料/製作者向け資料.html", "製作者向け資料 (実装を担当する方へ)", "仕様・部品表・組立図・寸法・配線・検査・要確認事項をまとめた引き継ぎ資料"),
    ("発注データ/発注手順.html", "発注・組立・動作確認の手順", "JLCPCB の設定、手はんだの順番、通電後のチェック"),
    ("部品購入リスト.html", "部品購入リスト (国内通販)", "秋月電子通商・Digi-Key Japan の商品ページへのリンク"),
    ("筐体/JLCCNC発注メモ.html", "JLCCNC 発注メモ (筐体)", "板金の設定と備考欄に貼る英文"),
    ("シミュレーション/結果.html", "シミュレーション結果", "起動・リップル・周波数特性・電源ON/OFF"),
    ("筐体/筐体図面.pdf", "筐体図面 (PDF)", "パネル穴の寸法、圧入ナットの指示"),
    ("BOM.csv", "部品表 (BOM.csv)", "全部品。表計算ソフトで開ける"),
]


def index():
    cards = "".join(
        f'<div class="card"><h3><a href="{link}">{t}</a></h3><a href="{link}"><img src="{img}" alt="{t}"></a><p>{d}</p></div>'
        for t, img, link, d in CARDS if os.path.exists(os.path.join(ROOT, img)))
    docs = "".join(f'<tr><td><a href="{p}">{t}</a></td><td>{d}</td></tr>' for p, t, d in DOCS
                   if os.path.exists(os.path.join(ROOT, p)))
    body = f"""<h1>{TITLE}</h1>
<p>DC12〜18V 入力 / UC3843 昇圧 + リップルフィルター / 2ch XLR スルー。基板は JLCPCB (SMD実装は基本部品のみ)、筐体は JLCCNC の板金。</p>
<h2>資料</h2>
<table><thead><tr><th>資料</th><th>内容</th></tr></thead><tbody>{docs}</tbody></table>
<h2>図面・イメージ</h2>
<div class="grid">{cards}</div>
<h2>フォルダ</h2>
<table><thead><tr><th>フォルダ</th><th>内容</th></tr></thead><tbody>
<tr><td><code>{PROJECT}_製作データ.zip</code></td><td>製作者に渡す一式 (製作者向け資料・発注データ・KiCad・筐体・回路図)</td></tr>
<tr><td><code>製作者向け資料/</code></td><td>実装担当者向けの引き継ぎ資料と図</td></tr>
<tr><td><code>発注データ/</code></td><td>そのままアップロードする発注用ファイル (JLCPCB / JLCCNC / 国内購入)</td></tr>
<tr><td><code>kicad/</code></td><td>KiCad プロジェクト (回路図・基板・専用フットプリント)</td></tr>
<tr><td><code>筐体/</code></td><td>筐体の 3D モデル (STEP)、図面、展開図、印刷データ</td></tr>
<tr><td><code>シミュレーション/</code></td><td>ngspice の結果とグラフ</td></tr>
<tr><td><code>tools/</code></td><td>回路図・基板・筐体・資料を生成するスクリプト</td></tr>
</tbody></table>"""
    open(os.path.join(ROOT, "はじめにお読みください.html"), "w", encoding="utf-8").write(
        page("2ch P48 ファンタム電源 — 資料一覧", body, None))


def refresh():
    """すべての Markdown 資料を HTML にし、入口ページを作り直す (各ジェネレーターの最後に呼ぶ)"""
    for p in all_md():
        convert_file(p)
    index()


def main():
    targets = sys.argv[1:] or all_md()
    for p in targets:
        print("html:", os.path.relpath(convert_file(os.path.abspath(p)), ROOT))
    index()
    print("html: はじめにお読みください.html")


if __name__ == "__main__":
    main()
