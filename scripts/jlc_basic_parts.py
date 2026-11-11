#!/usr/bin/env python3
"""JLCPCB の基本部品 (Basic Parts) を一覧・検索する。依存ライブラリなし。

JLCPCB の部品検索 API (componentLibraryType = "base") を使う。基本部品は数百点しかないので、
まず全件を取ってキャッシュし、種類・値・パッケージで絞り込むのが速くて確実。

使い方:
  python3 jlc_basic_parts.py update                 # 全件を取得して ~/.cache/jlc_basic_parts.json に保存
  python3 jlc_basic_parts.py types                  # 種類ごとの件数
  python3 jlc_basic_parts.py find MOSFET            # 種類名・型番・説明に文字列を含むもの (説明・パッケージも表示)
  python3 jlc_basic_parts.py res 0603 10k           # 基本部品の抵抗 (パッケージ, 値)
  python3 jlc_basic_parts.py cap 0805 100n 50       # 基本部品のコンデンサ (パッケージ, 値, 最低耐圧V)
  python3 jlc_basic_parts.py diode schottky 40      # ダイオード (種類の文字列, 最低耐圧V)。zener / tvs / switching なども可
  python3 jlc_basic_parts.py check C25804 C2145     # LCSC 番号が基本部品か確認

注意: 基本部品の顔ぶれは時々変わる。発注前に `update` してから `check` で BOM 全体を確かめる。
"""
import json, os, re, sys, time, urllib.request

URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
CACHE = os.path.expanduser("~/.cache/jlc_basic_parts.json")
UA = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
PFX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "R": 1, "": 1}


def fetch_all(keyword=""):
    out, page = [], 1
    while True:
        body = json.dumps({"currentPage": page, "pageSize": 100, "keyword": keyword, "componentLibraryType": "base",
                           "searchSource": "search", "stockFlag": None}).encode()
        for _ in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=UA), timeout=60) as r:
                    d = json.load(r)
                break
            except Exception:
                time.sleep(2)
                d = None
        if not d:
            break
        info = (d.get("data") or {}).get("componentPageInfo") or {}
        lst = info.get("list") or []
        out += lst
        if len(out) >= info.get("total", 0) or not lst:
            break
        page += 1
    return out


def load():
    if not os.path.exists(CACHE):
        raise SystemExit("キャッシュがない。先に `update` を実行")
    age = (time.time() - os.path.getmtime(CACHE)) / 86400
    if age > 7:
        print(f"(キャッシュは {age:.0f} 日前のもの。`update` で最新にできる)", file=sys.stderr)
    return json.load(open(CACHE))


def row(r):
    return "%-9s %-22s %-8s stock=%-10s %s" % (r["componentCode"], (r.get("componentModelEn") or r["erpComponentName"])[:22],
                                              (r.get("componentSpecificationEn") or "")[:8], r.get("stockCount"),
                                              (r.get("describe") or r.get("componentTypeEn") or "")[:90])


def num(desc, unit):
    """説明欄から単位つきの値を読む (例: unit='F' → '100nF' を 1e-7)。最初に見つかったもの"""
    m = re.search(r"(?<![\w.])([0-9.]+)\s*([pnuµmkM]?)" + unit + r"(?![a-zA-Z])", desc or "")
    return float(m.group(1)) * PFX[m.group(2)] if m else None


def volts(desc):
    """説明欄の耐圧 (例 '50V', '100V')。'550mV@1A' のような順電圧は除く"""
    vs = [float(x) for x in re.findall(r"(?<![\w.@~])([0-9.]+)V(?![a-zA-Z@])", desc or "")]
    return max(vs) if vs else None


def value(s):
    m = re.match(r"^([0-9.]+)\s*([pnuµmkKMR]?)", s)
    return float(m.group(1)) * PFX[m.group(2)] if m else None


def resistor_value(mpn):
    """UNI-ROYAL 型番 (0603WAF1002T5E 等) から (パッケージ, 抵抗値) を読む"""
    g = re.match(r"^(0402|0603|0805|1206|2010|2512)W\w([FJ])(\d{3})([0-9JKL])", mpn)
    if not g:
        return None
    size, _, d, e = g.groups()
    v = {"J": int(d) / 10, "K": int(d) / 100, "L": int(d) / 1000}.get(e)
    return size, (v if v is not None else int(d) * 10 ** int(e))


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd = a[0]
    if cmd == "update":
        rows = fetch_all()
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(rows, open(CACHE, "w"), ensure_ascii=False)
        print(f"{len(rows)} basic parts saved to {CACHE}")
    elif cmd == "types":
        import collections
        for k, v in collections.Counter(r.get("componentTypeEn") for r in load()).most_common():
            print(v, k)
    elif cmd == "find":
        q = " ".join(a[1:]).lower()
        for r in load():
            if q in (r.get("componentTypeEn") or "").lower() or q in r["erpComponentName"].lower() or \
                    q in (r.get("componentModelEn") or "").lower():
                print(row(r))
    elif cmd == "res":
        pkg, val = a[1], value(a[2])
        for r in load():
            if "Resistor" not in (r.get("secondSortName") or "") + (r.get("componentTypeEn") or ""):
                continue
            rv = resistor_value(r.get("componentModelEn") or "")
            ohm = rv[1] if rv else num((r.get("describe") or "").replace("kΩ", "kO").replace("MΩ", "MO").replace("Ω", "O"), "O")
            if r.get("componentSpecificationEn") == pkg and ohm is not None and abs(ohm - val) < 1e-6 * max(1, val):
                print(row(r))
    elif cmd == "cap":
        pkg, val = a[1], value(a[2])
        vmin = float(a[3]) if len(a) > 3 else 0
        for r in load():
            d = r.get("describe") or ""
            if "Capacitor" not in d + (r.get("secondSortName") or ""):
                continue
            c, v = num(d, "F"), volts(d)
            if r.get("componentSpecificationEn") == pkg and c and abs(c - val) < val * 1e-3 and (v or 0) >= vmin:
                print(row(r))
    elif cmd == "diode":
        kind = a[1].lower() if len(a) > 1 else "diode"
        vmin = float(a[2]) if len(a) > 2 else 0
        for r in load():
            t = ((r.get("componentTypeEn") or "") + " " + (r.get("firstSortName") or "") + " " + (r.get("describe") or "")).lower()
            if ("diode" in t or "tvs" in t) and kind in t and (volts(r.get("describe")) or 0) >= vmin:
                print(row(r))
    elif cmd == "check":
        base = {r["componentCode"]: r for r in load()}
        for code in a[1:]:
            print(("BASIC     " if code in base else "NOT BASIC ") + code, base[code]["erpComponentName"] if code in base else "")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
