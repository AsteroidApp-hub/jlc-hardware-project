#!/usr/bin/env python3
"""2ch P48ファンタム電源 — KiCad回路図ジェネレーター

回路の定義(PARTS)から kicad/P48_2CH.kicad_sch と BOM を生成する。
上段=電源(入力→昇圧→フィルター→+48V)、下段=L/Rチャンネル。配線でつないだ1枚の回路図を描く。
注意: 再実行すると .kicad_sch を上書きする。KiCad側で手編集した後は実行しないこと。
"""
import csv, math, os, re, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicad_env import kicad_share  # noqa: E402
SS = kicad_share()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "kicad")
from project import PROJECT, TITLE  # noqa: E402
try:
    from project import GRADE  # noqa: E402
except ImportError:
    GRADE = "audio"
if GRADE not in ("audio", "standard"):
    raise SystemExit(f'tools/project.py の GRADE は "audio" か "standard" (今: {GRADE!r})')
AUDIO_GRADE = GRADE == "audio"
NS = uuid.UUID("6f1c1e0a-7d1b-4a57-9f55-4b5531303030")


def uid(*key):
    return str(uuid.uuid5(NS, "/".join(str(k) for k in key)))


ROOT_UUID = uid("root")

# ---------------------------------------------------------------- library
_libcache = {}


def lib_block(lib, name):
    if lib not in _libcache:
        _libcache[lib] = open(f"{SS}/symbols/{lib}.kicad_sym").read()
    t = _libcache[lib]
    i = t.find(f'(symbol "{name}"\n')
    if i < 0:
        raise SystemExit(f"symbol {lib}:{name} not found")
    d, j, ins = 0, i, False
    while True:
        c = t[j]
        if c == '"' and t[j - 1] != "\\":
            ins = not ins
        elif not ins:
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    break
        j += 1
    b = t[i : j + 1]
    if "(extends" in b:
        raise SystemExit(f"{lib}:{name} uses extends; pick a base symbol")
    return b.replace(f'(symbol "{name}"\n', f'(symbol "{lib}:{name}"\n', 1)


PIN_RE = re.compile(
    r'\(pin (\w+) \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\(length ([\d.]+)\).*?'
    r'\(name "([^"]*)".*?\(number "([^"]*)"',
    re.S,
)


def parse_pins(block):
    pins = {}
    for typ, x, y, a, ln, name, num in PIN_RE.findall(block):
        pins[num] = dict(x=float(x), y=float(y), a=int(a), name=name)
    return pins


# ---------------------------------------------------------------- footprints
FP = dict(
    R0603="Resistor_SMD:R_0603_1608Metric",
    R0805="Resistor_SMD:R_0805_2012Metric",
    R1206="Resistor_SMD:R_1206_3216Metric",
    RAX="Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
    C0603="Capacitor_SMD:C_0603_1608Metric",
    C0805="Capacitor_SMD:C_0805_2012Metric",
    C1206="Capacitor_SMD:C_1206_3216Metric",
    CP10="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm",
    FILM="Capacitor_THT:C_Rect_L10.3mm_W4.5mm_P7.50mm_MKS4",
    DO15="Diode_THT:D_DO-15_P10.16mm_Horizontal",
    SMA="Diode_SMD:D_SMA",
    SOD123="Diode_SMD:D_SOD-123",
    DO41="Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
    SOT23="Package_TO_SOT_SMD:SOT-23",
    TO251="Package_TO_SOT_THT:TO-251-3_Vertical",
    DIP8="Package_DIP:DIP-8_W7.62mm",
    TOROID="Custom:L_Toroid_TCV-101M-3A",
    JACK="Custom:MJ-179PH",
    PTC="Capacitor_THT:C_Disc_D7.5mm_W2.5mm_P5.00mm",
    LED="LED_THT:LED_D3.0mm_Horizontal_O1.27mm_Z2.0mm",
    XH3="Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical",
    XLRF="Connector_Audio:Jack_XLR_Neutrik_NC3FAAH2_Horizontal",
    XLRM="Connector_Audio:Jack_XLR_Neutrik_NC3MAAH-1_Horizontal",
    HOLE="MountingHole:MountingHole_3.2mm_M3_Pad_Via",
)

# ---------------------------------------------------------------- purchase sources (国内通販)
# 価格: 秋月・千石=税込 / Digi-Key=税抜(数量1個の単価)。2026-11-11 時点の確認値
AKI = "秋月電子通商"
DK = "Digi-Key Japan"
SEN = "千石電商"
# 送料 (2026-11-11 確認): (送料, 送料無料の条件額, 条件の説明)
SHIPPING = {
    AKI: (550, 11000, "佐川 1個口 ¥550。商品合計 税込¥11,000 以上で無料"),
    DK: (2000, 6000, "商品代金 ¥6,000 未満は ¥2,000、¥6,000 以上で無料 (税込/税抜の記載なし → 税抜で ¥6,000 以上にしておく)"),
    SEN: (350, 10000, "ネコポス/ゆうパケット ¥350 (厚さ3cm・1kg・¥3,000 以内。注文時に選択)。通常便は ¥660、¥10,000 超で無料"),
}
SHOP = {
    "UC3843AN": (DK, "UC3843AN (Texas Instruments)",
                 "https://www.digikey.jp/ja/products/detail/texas-instruments/UC3843AN/382024", 295, 1, "税抜"),
    "IRFU120N": (AKI, "IRFU120NPBF  販売コード106050", "https://akizukidenshi.com/catalog/g/g106050/", 50, 1, "税込"),
    "TCV": (AKI, "TCV-101M-3A-5026 (トロイダル 100uH 3A)  販売コード113380", "https://akizukidenshi.com/catalog/g/g113380/", 50, 1,
            "税込"),
    "UPW47": (DK, "UPW2A470MPD (Nichicon PW 47uF/100V)",
              "https://www.digikey.jp/ja/products/detail/nichicon/UPW2A470MPD/589714", 107, 1, "税抜"),
    "UFW100": (DK, "UFW2A101MPD (Nichicon MUSE FW 100uF/100V)",
               "https://www.digikey.jp/ja/products/detail/nichicon/UFW2A101MPD/1964184", 173, 1, "税抜"),
    "ZLH470": (AKI, "ルビコン ZLH 470uF/35V  販売コード102719", "https://akizukidenshi.com/catalog/g/g102719/", 40, 1,
               "税込"),
    # 汎用グレードの 100uF/100V (MUSE FW と同じ φ10×20 P5。2026-11-11 確認: 1個 ¥180 / 10個 ¥113.4 税抜)
    "ZLH100": (DK, "100ZLH100MEFC10X20 (Rubycon ZLH 低ESR 100uF/100V)",
               "https://www.digikey.jp/ja/products/result?keywords=100ZLH100MEFC10X20", 180, 1, "税抜"),
    "FILM": (DK, "MKP4F031002D00KSSD (WIMA MKP4 ポリプロピレン 0.1uF/250V)",
             "https://www.digikey.jp/ja/products/detail/wima/MKP4F031002D00KSSD/19122665", 137, 1, "税抜"),
    "P6KE24": (DK, "P6KE24CA (Littelfuse 双方向TVS 20.5V)",
               "https://www.digikey.jp/ja/products/detail/littelfuse-inc/P6KE24CA/407707", 127, 1, "税抜"),
    "YR1": (DK, "YR1B6K81CC (TE 6.81k 0.1% 15ppm 1/4W)",
            "https://www.digikey.jp/ja/products/result?keywords=YR1B6K81CC", 160, 1, "税抜"),
    "P4KE": (AKI, "P4KE15CA 10本入り  販売コード129635", "https://akizukidenshi.com/catalog/g/g129635/", 180, 10, "税込"),
    "MFR050": (AKI, "MF-R050 (ポリスイッチ 0.5A)  販売コード112628", "https://akizukidenshi.com/catalog/g/g112628/", 30, 1,
               "税込"),
    "MJ179": (AKI, "MJ-179PH  販売コード106568", "https://akizukidenshi.com/catalog/g/g106568/", 40, 1, "税込"),
    "XH": (AKI, "B3B-XH-A (XHヘッダー 3P)  販売コード112248", "https://akizukidenshi.com/catalog/g/g112248/", 10, 1, "税込"),
    "LED": (AKI, "OSG5TA3Z74A (3mm 緑)  販売コード111635", "https://akizukidenshi.com/catalog/g/g111635/", 20, 1, "税込"),
    "NC3F": (DK, "NC3FAAH2 (Neutrik)",
             "https://www.digikey.jp/ja/products/detail/neutrik-americas-inc/NC3FAAH2/29371214", 335, 1, "税抜"),
    "NC3M": (DK, "NC3MAAH-1 (Neutrik)", "https://www.digikey.jp/ja/products/result?keywords=NC3MAAH-1", 323, 1, "税抜"),
}
# 基板に載らない購入品 (配線・パネル部品)
EXTRA_BUY = [
    (AKI, "MS-500A-B (トグルスイッチ 1回路2接点 ON-ON)  販売コード115737", "https://akizukidenshi.com/catalog/g/g115737/",
     300, 1, "税込", 1, "PHANTOM ON/OFF スイッチ。前面パネルに取付"),
    (SEN, "廣杉計器 ASB-306E 六角黄銅スペーサー メス-メス M3×6 (4個入)", "https://www.sengoku.co.jp/mod/sgk_cart/detail.php?code=EEHD-0RYS",
     230, 4, "税込", 4, "筐体: 基板の固定 (金属なので基板の取付穴とシャーシがつながる)"),
    (SEN, "ナベねじ M3×4 (BSナベ 3×4、真鍮ニッケルメッキ。10個から)", "https://www.sengoku.co.jp/mod/sgk_cart/detail.php?code=EEHD-6DKV",
     330, 10, "税込", 8, "筐体: 基板の固定 (スペーサーの上下から)"),
    (SEN, "鉄菊ワッシャー 内刃 M3 (歯付き座金)", "https://www.sengoku.co.jp/mod/sgk_cart/detail.php?code=EEHD-6NGH",
     25, 1, "税込", 8, "筐体: 底面の基板固定ねじ4本とカバー固定ねじ4本に入れ、アルマイトを破ってシャーシを接地"),
    (SEN, "黒タッピングA1ナベねじ 3×8 (10個から)", "https://www.sengoku.co.jp/mod/sgk_cart/detail.php?code=EEHD-6DGP",
     330, 10, "税込", 8, "XLRのパネル取付 (Neutrik純正ねじ相当)。締めすぎない"),
    (AKI, "XHP-3 (XHハウジング 3P)  販売コード112256", "https://akizukidenshi.com/catalog/g/g112256/", 5, 1, "税込", 1,
     "J2用"),
    (AKI, "SXH-001T-P0.6 (XHコンタクト 10個入)  販売コード112264", "https://akizukidenshi.com/catalog/g/g112264/", 30, 10,
     "税込", 3, "J2用(圧着)"),
    (AKI, "なべ小ねじ M3×6 (10個入)  販売コード110245", "https://akizukidenshi.com/catalog/g/g110245/", 150, 10, "税込", 4,
     "筐体: カバー固定"),
    (AKI, "接着シール付きゴムクッション 10×5 (4個入)  販売コード110080", "https://akizukidenshi.com/catalog/g/g110080/", 60, 4,
     "税込", 4, "筐体: 底面のゴム足"),
    (AKI, "熱収縮チューブ Φ3 黒 1m  販売コード106789", "https://akizukidenshi.com/catalog/g/g106789/", 50, 1, "税込", 1,
     "電源SWの配線"),
    (AKI, "耐熱電子ワイヤー AWG24相当 黒 20m  販売コード111091", "https://akizukidenshi.com/catalog/g/g111091/", 600, 1,
     "税込", 1, "電源SWの配線 (手持ちの線があれば不要)"),
]
# 国内通販で商品ページを確認できなかった組立部品 (ホームセンターやモノタロウ等で購入)。今は無し
OTHER_BUY = []

# ---------------------------------------------------------------- circuit
# assembly: "JLC" = JLCPCBで実装(基本部品のみ) / "HAND" = 国内通販で購入して手はんだ / "DNP" = 未実装 / "-" = 部品なし
PARTS = []


def P(ref, sym, value, fp, pins, mpn="", lcsc="", note="", asm="JLC", buy=None):
    if asm == "JLC" and not lcsc:
        raise SystemExit(f"{ref}: JLC part without LCSC number")
    PARTS.append(dict(ref=ref, sym=sym, value=value, fp=FP[fp], pins=pins, mpn=mpn, lcsc=lcsc,
                      note=note, asm=asm, buy=buy))


def R(ref, value, a, b, fp="R0603", **kw):
    P(ref, "Device:R", value, fp, {"1": a, "2": b}, **kw)


def C(ref, value, a, b, fp="C0603", **kw):
    P(ref, "Device:C", value, fp, {"1": a, "2": b}, **kw)


def CP(ref, value, plus, minus, fp, **kw):
    P(ref, "Device:C_Polarized", value, fp, {"1": plus, "2": minus}, **kw)


if AUDIO_GRADE:
    AUDIO = dict(mpn="Nichicon UFW2A101MPD (MUSE FW)", asm="HAND", buy="UFW100",
                 note="オーディオ用電解 100uF/100V φ10×20 P5")
    FILM_ASM, FILM_NOTE = "HAND", "ポリプロピレン フィルムバイパス 250V P7.5"
else:
    AUDIO = dict(mpn="Rubycon 100ZLH100MEFC10X20", asm="HAND", buy="ZLH100",
                 note="汎用の低ESR電解 100uF/100V φ10×20 P5 (オーディオ用にするなら MUSE FW)")
    FILM_ASM, FILM_NOTE = "DNP", "汎用グレードでは未実装 (オーディオ用にするなら WIMA MKP4 0.1uF を付ける)"
C100N50 = dict(lcsc="C14663", mpn="CC0603KRX7R9BB104")
C100N100 = dict(fp="C0805", lcsc="C28233", mpn="CL21B104KCFNNNE")
C1N2KV = dict(fp="C1206", lcsc="C9196", mpn="1206B102K202NT")

# ---- 1. DC入力
P("J1", "Connector:Barrel_Jack_Switch", "DC12V IN", "JACK", {"1": "VIN_RAW", "2": "GND", "3": "GND"},
  mpn="MJ-179PH", asm="HAND", buy="MJ179", note="2.1mm センタープラス。専用フットプリント (側面ピン穴は左右両側)")
P("F1", "Device:Polyfuse", "0.5A", "PTC", {"1": "VIN_RAW", "2": "VIN_F"}, mpn="Bourns MF-R050", asm="HAND",
  buy="MFR050", note="リセッタブルヒューズ 保持0.5A/トリップ1A/60V")
P("D1", "Device:D_Schottky", "SS34", "SMA", {"2": "VIN_F", "1": "+12V"}, mpn="SS34", lcsc="C8678", note="逆接保護")
P("D2", "Device:D_TVS", "P6KE24CA", "DO15", {"1": "+12V", "2": "GND"}, mpn="P6KE24CA", asm="HAND", buy="P6KE24",
  note="過電圧クランプ (VWM 20.5V)。入力 12〜18V に対応。24V以上の誤接続時はF1が遮断")
CP("C1", "470uF/35V", "+12V", "GND", "CP10", mpn="Rubycon 35ZLH470M", asm="HAND", buy="ZLH470",
   note="入力バルク 低ESR φ10×16 P5")
C("C2", "10uF/50V", "+12V", "GND", "C1206", lcsc="C13585", mpn="CL31A106KBHNNNE", note="X5R")
C("C3", "100nF/50V", "+12V", "GND", **C100N50)

# ---- 2. 昇圧 (UC3843 電流モードPWM, fsw ≒ 153kHz, 常に電流不連続モード)
P("U1", "Regulator_Controller:UC3842_SOIC8", "UC3843AN", "DIP8",
  {"1": "COMP", "2": "FB", "3": "CS_F", "4": "RC", "5": "GND", "6": "GATE", "7": "VCC", "8": "VREF"},
  mpn="TI UC3843AN (DIP-8)", asm="HAND", buy="UC3843AN", note="UVLO 8.4V/7.6V。DIP-8 (ソケット推奨)")
R("R1", "10R", "+12V", "VCC", fp="R0805", lcsc="C17415", mpn="0805W8F100JT5E", note="VCCフィルター")
C("C4", "10uF/50V", "VCC", "GND", "C1206", lcsc="C13585", mpn="CL31A106KBHNNNE")
C("C5", "100nF/50V", "VCC", "GND", **C100N50)
C("C6", "100nF/50V", "VREF", "GND", **C100N50)
R("R2", "5.1k", "VREF", "RC", lcsc="C23186", mpn="0603WAF5101T5E", note="RT: fsw ≒ 1.72/(RT·CT) ≒ 153kHz")
C("C7", "2.2nF C0G", "RC", "GND", "C0805", lcsc="C28260", mpn="CL21C222JBFNNNE", note="CT")
R("R9", "100k", "FB", "VBOOST", lcsc="C25803", mpn="0603WAF1003T5E", note="VBOOST = 2.5V × (1+100k/5.1k) = 51.5V")
R("R10", "5.1k", "FB", "GND", lcsc="C23186", mpn="0603WAF5101T5E")
C("C10", "47nF", "FB", "COMP_RC", lcsc="C1622", mpn="CL10B473KB8NNNC", note="位相補償(シミュレーションで確認)")
R("R4", "1M", "COMP_RC", "COMP", lcsc="C22935", mpn="0603WAF1004T5E")
C("C11", "100pF C0G", "FB", "COMP", lcsc="C14858", mpn="CL10C101JB8NNNC")
R("R5", "10R", "GATE", "GATE_Q", lcsc="C22859", mpn="0603WAF100JT5E", note="ゲート抵抗")
R("R6", "10k", "GATE_Q", "GND", lcsc="C25804", mpn="0603WAF1002T5E")
P("Q1", "Transistor_FET:Q_NMOS_GDS", "IRFU120N", "TO251", {"1": "GATE_Q", "2": "SW", "3": "CS"},
  mpn="IRFU120NPBF", asm="HAND", buy="IRFU120N", note="100V 9.4A 0.21Ω TO-251")
R("R7", "1R", "CS", "GND", fp="R1206", lcsc="C17928", mpn="1206W4F100KT5E", note="電流検出: ピーク制限 1.0V/1Ω = 1A")
R("R8", "1k", "CS_F", "CS", lcsc="C21190", mpn="0603WAF1001T5E")
C("C12", "470pF", "CS_F", "GND", lcsc="C1620", mpn="0603B471K500NT")
P("L1", "Device:L", "100uH", "TOROID", {"1": "+12V", "2": "SW"}, mpn="TCV-101M-3A-5026", asm="HAND", buy="TCV",
  note="トロイダル(T50-26) 3A 0.25Ω 縦置き φ15.5×8.5。長穴パッドでピン間隔 4〜10mm に対応")
R("R11", "22R", "SW", "SNUB", fp="R1206", lcsc="C17958", mpn="1206W4F220JT5E", asm="DNP", note="スナバ(予備パターン)")
C("C15", "1nF/2kV", "SNUB", "GND", asm="DNP", note="スナバ(予備パターン)", **C1N2KV)
P("D3", "Device:D_Schottky", "SS210", "SMA", {"2": "SW", "1": "VBOOST"}, mpn="SS210", lcsc="C14996",
  note="100V 2A ショットキー")
CP("C13", "47uF/100V", "VBOOST", "GND", "CP10", mpn="Nichicon UPW2A470MPD", asm="HAND", buy="UPW47",
   note="低ESR φ10×16 P5")
C("C14", "100nF/100V", "VBOOST", "GND", **C100N100)

# ---- 3. フィルター + リップルフィルター(48V生成)
R("R12", "22R", "VBOOST", "VFILT", fp="R1206", lcsc="C17958", mpn="1206W4F220JT5E", note="RCフィルター fc ≒ 150Hz")
CP("C16", "47uF/100V", "VFILT", "GND", "CP10", mpn="Nichicon UPW2A470MPD", asm="HAND", buy="UPW47",
   note="低ESR φ10×16 P5")
C("C17", "100nF/100V", "VFILT", "GND", **C100N100)
R("R13", "10k", "VFILT", "PH_FEED", lcsc="C25804", mpn="0603WAF1002T5E", note="R13/R14で出力電圧を設定")
P("J2", "Connector_Generic:Conn_01x03", "PHANTOM SW", "XH3", {"1": "PH_FEED", "2": "VBASE", "3": "PH_OFF"},
  mpn="JST B3B-XH-A", asm="HAND", buy="XH",
  note="前面パネルの PHANTOM スイッチ (MS-500A-B ON-ON) へ配線。2番=共通、1番=ON側、3番=OFF側")
R("R18", "10k", "PH_OFF", "GND", lcsc="C25804", mpn="0603WAF1002T5E", note="PHANTOM OFF 時に C18 を放電 (約1秒)")
R("R14", "330k", "VBASE", "GND", lcsc="C23137", mpn="0603WAF3303T5E")
CP("C18", "100uF/100V", "VBASE", "GND", "CP10", **AUDIO)
R("R15", "1k", "VBASE", "Q_B1", lcsc="C21190", mpn="0603WAF1001T5E")
P("Q2", "Transistor_BJT:Q_NPN_BEC", "MMBT5551", "SOT23", {"1": "Q_B1", "3": "VFILT", "2": "Q_B2"},
  mpn="MMBT5551", lcsc="C2145", note="160V NPN")
P("Q3", "Transistor_BJT:Q_NPN_BEC", "MMBT5551", "SOT23", {"1": "Q_B2", "3": "VFILT", "2": "+48V"},
  mpn="MMBT5551", lcsc="C2145", note="160V NPN")
R("R16", "100k", "Q_B2", "+48V", lcsc="C25803", mpn="0603WAF1003T5E")
P("D4", "Device:D", "1N4148W", "SOD123", {"2": "+48V", "1": "VBASE"}, mpn="1N4148W", lcsc="C81598",
  note="電源OFF時のB-E逆電圧保護")
P("D5", "Device:D", "1N4148W", "SOD123", {"2": "+48V", "1": "VFILT"}, mpn="1N4148W", lcsc="C81598",
  note="電源OFF時の逆流保護")
C("C19", "100nF/100V", "+48V", "GND", **C100N100)
R("R17", "47k", "+48V", "LED_A", fp="R0805", lcsc="C17713", mpn="0805W8F4702T5E", note="LED 約1mA")
P("LED1", "Device:LED", "GREEN", "LED", {"2": "LED_A", "1": "GND"}, mpn="OSG5TA3Z74A", asm="HAND", buy="LED",
  note="48V ON 表示")


# ---- 4/5. チャンネル
def channel(ch):
    b = 100 if ch == "L" else 200
    r = lambda i: f"R{b + i}"
    c = lambda i: f"C{b + i}"
    N = lambda s: f"{ch}_{s}"
    P(f"J{b + 1}", "Connector_Audio:XLR3_Ground", f"MIC IN {ch}", "XLRF",
      {"1": "CHASSIS", "2": N("IN_H"), "3": N("IN_C"), "G": "CHASSIS"}, mpn="Neutrik NC3FAAH2", asm="HAND",
      buy="NC3F")
    R(r(1), "100R", "+48V", N("P48"), fp="R1206", lcsc="C17901", mpn="1206W4F1000T5E", note="チャンネル別デカップリング")
    CP(c(1), "100uF/100V", N("P48"), "GND", "CP10", **AUDIO)
    R(r(2), "6.81k 0.1%", N("P48"), N("IN_H"), fp="RAX", mpn="TE YR1B6K81CC", asm="HAND", buy="YR1",
      note="P48給電抵抗 0.1% 15ppm 1/4W")
    R(r(3), "6.81k 0.1%", N("P48"), N("IN_C"), fp="RAX", mpn="TE YR1B6K81CC", asm="HAND", buy="YR1",
      note="P48給電抵抗 0.1% 15ppm 1/4W")
    C(c(2), "1nF/2kV", N("IN_H"), "CHASSIS", note="RFI対策", **C1N2KV)
    C(c(3), "1nF/2kV", N("IN_C"), "CHASSIS", note="RFI対策", **C1N2KV)
    for i, hc in enumerate("HC"):
        CP(c(4 + 2 * i), "100uF/100V", N(f"IN_{hc}"), N(f"CC_{hc}"), "CP10", **AUDIO)
        C(c(5 + 2 * i), "0.1uF PP", N(f"IN_{hc}"), N(f"CC_{hc}"), "FILM", mpn="WIMA MKP4F031002D00KSSD", asm=FILM_ASM,
          buy="FILM" if AUDIO_GRADE else None, note=FILM_NOTE)
        R(r(4 + i), "10R", N(f"CC_{hc}"), N(f"OUT_{hc}"), fp="R1206", lcsc="C17903", mpn="1206W4F100JT5E",
          note="出力保護用の直列抵抗")
        R(r(6 + i), "10k", N(f"OUT_{hc}"), "GND", lcsc="C25804", mpn="0603WAF1002T5E",
          note="ブリーダー(出力側DC電位を0Vに固定)")
        P(f"D{b + 1 + i}", "Device:D_TVS", "P4KE15CA", "DO41", {"1": N(f"OUT_{hc}"), "2": "GND"}, mpn="P4KE15CA",
          asm="HAND", buy="P4KE", note="出力クランプ(接続機器の保護)")
    P(f"J{b + 2}", "Connector_Audio:XLR3", f"OUT {ch}", "XLRM",
      {"1": "CHASSIS", "2": N("OUT_H"), "3": N("OUT_C")}, mpn="Neutrik NC3MAAH-1", asm="HAND", buy="NC3M")


channel("L")
channel("R")

# ---- 6. グラウンド
R("R20", "0R", "CHASSIS", "GND", fp="R1206", lcsc="C17888", mpn="1206W4F0000T5E", note="回路GND-シャーシ 1点接続")
C("C20", "1nF/2kV", "CHASSIS", "GND", **C1N2KV)
for _i in range(1, 5):
    P(f"H{_i}", "Mechanical:MountingHole_Pad", "M3", "HOLE", {"1": "CHASSIS"}, asm="-")

# ---------------------------------------------------------------- drawing
G = 2.54          # 回路図グリッド。以下の座標はすべてこの単位
PAGE = (480, 297)
CH_Y = {"L": 56, "R": 86}   # 各チャンネルの基準Y

# 配置: ref -> (アンカーピン, x, y, 回転, ミラー, 文字位置)
#   文字位置: "r"=右 / "a"=上 / "b"=下 / (dx_ref, dy_ref, dx_val, dy_val)
PLACE = {}


def put(ref, pin, x, y, rot=0, mirror=False, text="r"):
    PLACE[ref] = (pin, x, y, rot, mirror, text)


# -- 入力
put("J1", "1", 12, 20, text=(-6, -3.2, -6, 3.4))
put("F1", "1", 14, 20, 90, text="a")
put("D1", "2", 23, 20, 180, text="a")
put("D2", "1", 29, 20, 270)
put("C1", "1", 34, 20)
put("C2", "1", 38, 20)
put("C3", "1", 42, 20)
# -- 昇圧 (U1中心 = (72,34))
put("U1", "7", 72, 30, text=(-7.4, -1.6, -7.4, -0.6))
put("R1", "1", 72, 20)
put("C4", "1", 75, 24)
put("C5", "1", 79, 24)
put("C10", "1", 58, 24, 90, text="a")
put("R4", "1", 61, 24, 90, text="a")
put("C11", "1", 58, 28, 90, text="b")
put("R10", "1", 54, 30)
put("R9", "1", 50, 30)
put("R2", "1", 60, 35)
put("C6", "1", 56, 35)
put("C7", "1", 63, 40)
put("R5", "1", 79, 32, 90, text="a")
put("R6", "1", 83, 32)
put("Q1", "1", 84, 32, text=(4.6, -0.6, 4.6, 0.6))
put("R8", "1", 80, 39, 90, text="b")
put("C12", "1", 78, 39, text=(-3.6, -0.4, -3.6, 0.6))
put("R7", "1", 87, 39)
put("L1", "1", 84, 20, 90, text="a")
put("R11", "1", 87, 25, 90, text="a")
put("C15", "1", 90, 25)
put("D3", "2", 89, 20, 180, text="a")
put("C13", "1", 95, 20)
put("C14", "1", 99, 20)
# -- フィルター / 48V
put("R12", "1", 116, 20, 90, text="a")
put("C16", "1", 125, 20)
put("C17", "1", 130, 20)
put("R13", "1", 135, 20)
put("J2", "1", 124, 28, text=(0.6, -2.4, 0.6, -1.4))
put("R18", "1", 129, 26)
put("R14", "1", 135, 33)
put("C18", "1", 130, 31)
put("R15", "1", 138, 31, 90, text="b")
put("Q2", "1", 141, 29, 90, text=(0.5, 3.2, 0.5, 4.1))
put("Q3", "1", 145, 23, 90, text=(-2.8, -6.2, -2.8, -5.2))
put("R16", "1", 146, 26, 90, text="b")
put("D4", "1", 141, 35, text="b")
put("D5", "1", 142, 15, text="a")
put("C19", "1", 153, 20)
put("R17", "1", 158, 20)
put("LED1", "2", 158, 23, 90, text=(2.6, -0.5, 2.6, 0.6))
# -- グラウンド
put("R20", "1", 96, 64, 90, text="a")
put("C20", "1", 96, 67, 90, text="b")
for _i in range(4):
    put("H%d" % (_i + 1), "1", 106 + 4 * _i, 69, text=(0, -3.6, 0, -2.6))


def place_channel(ch, b):
    y = CH_Y[ch]
    r = lambda i: "R%d" % (b + i)
    c = lambda i: "C%d" % (b + i)
    put(r(1), "1", 10, y + 2, 90, text="a")
    put(c(1), "1", 19, y + 2)
    put(r(2), "1", 26, y + 2)
    put(r(3), "1", 33, y + 2)
    put("J%d" % (b + 1), "2", 20, y + 10, text=(-5.2, -3.6, -5.2, -2.5))
    put(c(2), "1", 23, y + 10)
    put(c(3), "1", 29, y + 16)
    put(c(4), "1", 44, y + 10, 90, text="b")
    put(c(5), "1", 44, y + 7, 90, text="a")
    put(c(6), "1", 44, y + 16, 90, text="a")
    put(c(7), "1", 44, y + 19, 90, text="b")
    put(r(4), "1", 51, y + 10, 90, text="a")
    put(r(5), "1", 51, y + 16, 90, text="a")
    put(r(6), "1", 59, y + 10)
    put(r(7), "1", 59, y + 16)
    put("D%d" % (b + 1), "1", 64, y + 10, 270)
    put("D%d" % (b + 2), "1", 64, y + 16, 270)
    put("J%d" % (b + 2), "2", 70, y + 10, mirror=True, text=(3, -3.6, 3, -2.5))


place_channel("L", 100)
place_channel("R", 200)

# 配線: 点の列。 "REF.pin" または (x, y)。連続する2点は水平か垂直であること
WIRES = [
    # 入力
    ["J1.1", "F1.1"], ["F1.2", "D1.2"],
    ["J1.3", (13, 21)], ["J1.2", (13, 22)], [(13, 21), (13, 24), (15, 24)],
    # +12Vレール
    ["D1.1", "L1.1"],
    # U1 電源
    ["R1.2", "U1.7"], [(72, 24), "C5.1"],
    # U1 左側: 位相補償 / 帰還 / 発振
    ["U1.1", (64, 32), (64, 24), "R4.2"], ["R4.1", "C10.2"], ["C11.2", (64, 28)],
    ["U1.2", (58, 33), "C10.1"], [(58, 30), "R9.1"],
    ["R9.2", (50, 46), (102, 46), (102, 20)],
    ["U1.8", "C6.1"], ["U1.4", (63, 36), "C7.1"], ["R2.2", (60, 40), "C7.1"],
    # U1 右側: ゲート / 電流検出
    ["U1.6", "R5.1"], ["R5.2", "Q1.1"], ["U1.3", (78, 36), "C12.1"], ["C12.1", "R8.1"], ["R8.2", "R7.1"],
    ["Q1.3", "R7.1"], ["Q1.2", (87, 20)], ["C15.1", "R11.2"],
    ["L1.2", "D3.2"],
    # フィルター / 48V
    ["D3.1", "R12.1"], ["R12.2", "Q3.3"], ["R14.1", (135, 26)], ["C18.1", (135, 31)], [(135, 31), "R15.1"],
    ["R15.2", "Q2.1"], ["Q2.3", (138, 26), (138, 20)], ["Q2.2", (145, 26), "Q3.1"], [(145, 26), "R16.1"],
    ["R16.2", (149, 26)], [(137, 31), (137, 35), "D4.1"], ["D4.2", (149, 35), (149, 20)],
    ["D5.1", (140, 15), (140, 20)], ["D5.2", (148, 15), (148, 20)],
    ["Q3.2", (166, 20), (166, 52), (8, 52), (8, CH_Y["R"] + 2), "R201.1"], [(8, CH_Y["L"] + 2), "R101.1"],
    # グラウンド
    [(93, 64), "R20.1"], [(95, 64), (95, 67), "C20.1"], ["C20.2", (100, 67), (100, 64)], ["R20.2", (101, 64), (101, 65)],
    [(94, 64), (94, 71), (118, 71), "H4.1"], ["H1.1", (106, 71)], ["H2.1", (110, 71)], ["H3.1", (114, 71)],
]
GNDS = ["R18.2", "C1.2", "C2.2", "C3.2", "D2.2", "C4.2", "C5.2", "C6.2", "C7.2", "R10.2", "R6.2", "C12.2", "R7.2", "C15.2",
        "U1.5", "C13.2", "C14.2", "C16.2", "C17.2", "R14.2", "C18.2", "C19.2", "LED1.1", (13, 24), (101, 65)]
FLAGS = [(15, 24), (79, 24)]
NOCONN = []
# ラベル: (ネット, x, y, 左向き)
LABELS = [
    ("VIN_RAW", 12, 20, 0), ("VIN_F", 18, 20, 0), ("+12V", 44, 20, 0),
    ("VCC", 73, 24, 0), ("COMP", 65, 32, 0), ("COMP_RC", 61, 24, 1), ("FB", 59, 33, 0), ("VREF", 64, 35, 0),
    ("RC", 64, 36, 0), ("GATE", 77, 32, 0), ("GATE_Q", 82, 32, 0), ("CS_F", 77, 36, 0), ("CS", 84, 39, 0),
    ("SW", 88, 20, 0), ("SNUB", 90, 25, 0), ("VBOOST", 100, 20, 0),
    ("VFILT", 121, 20, 0), ("VBASE", 135, 26, 0), ("PH_FEED", 135, 23, 0),
    ("PH_FEED", 124, 28, 1), ("VBASE", 124, 29, 1), ("PH_OFF", 124, 30, 1), ("PH_OFF", 129, 26, 0), ("Q_B1", 141, 30, 0), ("Q_B2", 145, 25, 0),
    ("+48V", 160, 20, 0), ("LED_A", 158, 23, 1), ("CHASSIS", 93, 64, 1),
]
TEXTS = [
    (10, 8, 2.0, "1. DC12V入力  逆接保護・過電圧保護"),
    (48, 8, 2.0, "2. 昇圧コンバーター  12V → 51.5V  (UC3843 電流モードPWM, fsw ≒ 153kHz)"),
    (114, 8, 2.0, "3. RCフィルター ＋ リップルフィルター  → +48V"),
    (8, CH_Y["L"] - 1.5, 2.0, "4. CH L   P48給電 6.81kΩ 0.1% → DCカット → 出力保護"),
    (8, CH_Y["R"] - 1.5, 2.0, "5. CH R   (CH Lと同一回路)"),
    (93, 60, 2.0, "6. GND – シャーシ 1点接続 / 取付穴"),
    (10, 28.5, 1.3, "DCジャック 2.1mm センタープラス\n入力 12〜18V (リニア電源推奨)"),
    (103.5, 32.5, 1.3, "PHANTOM スイッチ (前面パネル MS-500A-B, ON-ON)\n"
                     "ON : 2-1 接続 → R13 から C18 を充電、+48V が約2秒で立ち上がる\n"
                     "OFF: 2-3 接続 → R18 で C18 を放電、約1秒で下がる\n"
                     "配線が外れていると OFF (安全側)"),
    (46, 47.5, 1.3, "VBOOST = 2.5V × (1 + R9/R10) = 2.5 × (1 + 100k/5.1k) ≒ 51.5V\n"
                    "fsw ≒ 1.72 / (R2 × C7) ≒ 153kHz    ピーク電流制限 = 1.0V / R7 = 1A\n"
                    "負荷30mA以下では常に電流不連続モード (境界 約70mA)"),
    (92.5, 26.5, 1.3, "R11, C15: スナバ\n(未実装・予備パターン)"),
    (116, 40.0, 1.3, "+48V ≒ VFILT × 330k/(10k+330k) − 2×VBE ≒ 48.2V\n"
                     "C18 × (R13//R14) ≒ 1秒 の時定数でゆっくり立ち上がる\nD4, D5: 電源OFF時のQ2/Q3保護"),
    (152, 28.5, 1.3, "LED 約1mA"),
    (93, 76, 1.5,
     "【注記】\n"
     + ("1. オーディオ用電解コンデンサ (ニチコン MUSE FW 100µF/100V):  C18, C101, C104, C106, C201, C204, C206\n"
        "2. ポリプロピレンフィルム WIMA MKP4 0.1µF/250V: C105, C107, C205, C207\n" if AUDIO_GRADE else
        "1. 電解コンデンサ (汎用の低ESR品 100µF/100V):  C18, C101, C104, C106, C201, C204, C206\n"
        "2. フィルム C105, C107, C205, C207 は未実装 (オーディオ用にするときに付ける)\n") +
     "3. P48給電抵抗 6.81kΩ 0.1% 15ppm (R102, R103, R202, R203)\n"
     "4. XLR: 1番ピン = CHASSIS、2番 = HOT、3番 = COLD。  入力 = メス (NC3FAAH2)、出力 = オス (NC3MAAH-1)\n"
     "5. 出力TVS (P4KE15CA) は接続機器の保護用。電源投入後の数秒間、出力に最大約15Vの同相電圧が出る\n"
     "6. SMD部品はJLCPCB実装 (基本部品のみ)。THT部品とU1は国内通販で購入し手はんだ"),
]


def channel_wires(ch, b):
    y = CH_Y[ch]
    r = lambda i: "R%d.%%s" % (b + i)
    c = lambda i: "C%d.%%s" % (b + i)
    ji, jo = "J%d." % (b + 1), "J%d." % (b + 2)
    d1, d2 = "D%d." % (b + 1), "D%d." % (b + 2)
    hot, cold, chs = y + 10, y + 16, y + 21
    WIRES.extend([
        [r(1) % 2, r(3) % 1],                                      # P48レール
        [r(2) % 2, (26, hot)], [r(3) % 2, (33, cold)],             # 給電抵抗 → HOT / COLD
        [ji + "2", c(4) % 1],                                      # HOT 入力側
        [(43, hot), (43, y + 7), c(5) % 1], [c(5) % 2, (48, y + 7), (48, hot)],
        [c(4) % 2, r(4) % 1], [r(4) % 2, jo + "2"],
        [ji + "3", (17, cold), c(6) % 1],                          # COLD 入力側
        [(43, cold), (43, y + 19), c(7) % 1], [c(7) % 2, (48, y + 19), (48, cold)],
        [c(6) % 2, r(5) % 1], [r(5) % 2, (73, cold), jo + "3"],
        [ji + "1", (12, hot), (12, chs), (29, chs), c(3) % 2],     # CHASSIS
        [ji + "G", (16, chs)], [c(2) % 2, (23, chs)],
        [jo + "1", (78, hot)],
    ])
    GNDS.extend([c(1) % 2, r(6) % 2, r(7) % 2, d1 + "2", d2 + "2"])
    N = lambda s: "%s_%s" % (ch, s)
    LABELS.extend([
        (N("P48"), 14, y + 2, 0),
        (N("IN_H"), 36, hot, 0), (N("IN_C"), 36, cold, 0), (N("CC_H"), 48, hot, 0), (N("CC_C"), 48, cold, 0),
        (N("OUT_H"), 55, hot, 0), (N("OUT_C"), 55, cold, 0), ("CHASSIS", 13, chs, 0), ("CHASSIS", 78, hot, 0),
    ])


channel_wires("L", 100)
channel_wires("R", 200)


# ---------------------------------------------------------------- BOM / 購入リスト
def check_buy_links():
    """購入する部品には必ず購入先の商品ページへのリンクを付ける (ユーザーの必須条件)。無ければ止める"""
    bad = []
    for p in PARTS:
        if p["asm"] == "HAND" and (not p["buy"] or p["buy"] not in SHOP):
            bad.append(f"{p['ref']}: 手はんだ部品なのに購入先 (buy=) が無い")
    for k, v in SHOP.items():
        if not str(v[2]).startswith("https://"):
            bad.append(f"SHOP[{k}]: リンクが無い")
    for e in EXTRA_BUY:
        if not str(e[2]).startswith("https://"):
            bad.append(f"EXTRA_BUY {e[1]}: リンクが無い")
    for n, *_ in OTHER_BUY:
        bad.append(f"OTHER_BUY {n}: リンクの無い購入品は不可。購入先を調べて EXTRA_BUY にリンク付きで書く")
    if bad:
        raise SystemExit("購入リンクの不足:\n  " + "\n  ".join(bad))


def write_outputs():
    import datetime
    check_buy_links()
    order = {"JLC": 0, "HAND": 1, "DNP": 2}
    groups = {}
    for p in PARTS:
        if p["asm"] == "-":
            continue
        k = (p["asm"], p["value"], p["fp"], p["mpn"], p["lcsc"], p["buy"])
        groups.setdefault(k, []).append(p)
    rows = sorted(groups.items(), key=lambda kv: (order[kv[0][0]], kv[1][0]["ref"]))
    with open(os.path.join(ROOT, "BOM.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["実装", "数量", "リファレンス", "値", "フットプリント", "型番", "LCSC", "購入先", "購入リンク", "備考"])
        for (asm, val, fp, mpn, lcsc, buy), ps in rows:
            note = next((p["note"] for p in ps if p["note"]), "")
            w.writerow([asm, len(ps), " ".join(p["ref"] for p in ps), val, fp.split(":")[-1], mpn, lcsc,
                        SHOP[buy][0] if buy else ("JLCPCB" if asm == "JLC" else ""),
                        SHOP[buy][2] if buy else (f"https://jlcpcb.com/partdetail/{lcsc}" if asm == "JLC" else ""), note])
    # JLCPCB実装用BOM (基本部品のみ)
    with open(os.path.join(ROOT, "JLCPCB_BOM.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (asm, val, fp, mpn, lcsc, buy), ps in rows:
            if asm == "JLC":
                w.writerow([val, ",".join(p["ref"] for p in ps), fp.split(":")[-1], lcsc])
    # 国内通販 購入リスト
    need = {}
    for p in PARTS:
        if p["buy"] and p["asm"] == "HAND":
            need.setdefault(p["buy"], []).append(p["ref"])
    # 予備: Digi-Key の送料無料 (¥6,000) に届かせる分を、10個単価が使える数と予備に回す
    #   YR1 は10本から2本ずつ値の近い組を選ぶ (ホット/コールドの差を小さく → ノイズ除去が良くなる)
    #   汎用グレードはフィルムを買わない分だけ小計が減るので、電解の予備を増やして ¥6,000 に届かせる
    spare = {"UC3843AN": 1, "UPW47": 8, "UFW100": 6, "ZLH100": 6 if AUDIO_GRADE else 13, "FILM": 6, "YR1": 6, "P6KE24": 1}
    tier10 = {"UFW100": 110.1, "ZLH100": 113.4, "UPW47": 67.3, "FILM": 86.2, "YR1": 104.0, "P6KE24": 78.1,
              "UC3843AN": 216.1}   # 10個以上の単価 (Digi-Key, 税抜)
    lines = ["# 部品購入リスト (国内通販)", "",
             TITLE + " / 基板1台分。価格は %s 時点の確認値。" % datetime.date.today().isoformat(),
             "", "- 秋月電子通商・千石電商の価格は税込、Digi-Key Japanの価格は税抜",
             "- **「購入数」で注文してください。** 必要数より多いのは、まとめ買いの単価・送料無料の条件・予備のため",
             ("- 部品のグレード: オーディオ用 (信号の通り道の電解は MUSE FW、フィルムは WIMA MKP4)" if AUDIO_GRADE else
              "- 部品のグレード: 汎用 (電解は低 ESR の一般品、フィルムは付けない)。給電抵抗の 0.1% は規格のため汎用でも変えない"),
             "- 購入先は 3 店にまとめた (Digi-Key でしか買えない部品 / 秋月でしか買えない部品 / ねじ類)。理由は最後の「送料」を参照",
             "- 在庫・価格は注文時に各ショップで確認してください", ""]
    total = {}
    for shop in (DK, AKI, SEN):
        lines += ["## " + shop, "", "| 品名・型番 | 用途 (リファレンス) | 必要数 | 購入数 | 単価 | 小計 |",
                  "|---|---|---:|---:|---:|---:|"]
        sub = 0
        for key, (s, name, url, price, pack, tax) in SHOP.items():
            if s != shop or key not in need:
                continue
            refs = need[key]
            n = len(refs)
            buyn = n + spare.get(key, 0)
            packs = -(-buyn // pack)
            unit = tier10[key] if (key in tier10 and buyn >= 10) else price
            cost = round(packs * unit)
            sub += cost
            qty = f"{packs}パック ({packs * pack}個)" if pack > 1 else f"{buyn}"
            utxt = f"¥{unit:,}{'/パック' if pack > 1 else ''}" + (" (10個以上の単価)" if unit != price else "")
            lines.append(f"| [{name}]({url}) | {', '.join(refs)} | {n} | {qty} | {utxt} | ¥{cost:,} |")
        for (s, name, url, price, pack, tax, n, use) in EXTRA_BUY:
            if s != shop:
                continue
            packs = -(-n // pack)
            cost = packs * price
            sub += cost
            qty = f"{packs}パック ({packs * pack}個)" if pack > 1 else f"{n}"
            lines.append(f"| [{name}]({url}) | {use} | {n} | {qty} | ¥{price:,}{'/パック' if pack > 1 else ''} | ¥{cost:,} |")
        total[shop] = sub
        lines += ["", f"**小計: ¥{sub:,}** ({'税抜' if shop == DK else '税込'})", ""]
        if shop == DK:
            lines += ["- UC3843AN は 1 個予備 (DIP なので差し替えられる)。電解・フィルム・TVS は 10 個単価が使える数",
                      "- **YR1 (6.81kΩ) は 10 本買い、テスターで測って値の近い 2 本ずつを各チャンネルの R102/R103、R202/R203 に使う**", ""]
    if OTHER_BUY:
        lines += ["## その他 (ホームセンター・モノタロウ等)", "", "| 品名 | 数量 | 用途 |", "|---|---:|---|"]
        lines += [f"| {n} | {q} | {u} |" for n, q, u in OTHER_BUY] + [""]
    need_dk = sum(SHOP[k][3] * len(v) for k, v in need.items() if SHOP[k][0] == DK)
    ship = {k: (0 if total[k] >= v[1] else v[0]) for k, v in SHIPPING.items()}
    if ship[DK]:
        short = SHIPPING[DK][1] - total[DK]
        print(f"注意: Digi-Key の小計 ¥{total[DK]:,} が送料無料の ¥{SHIPPING[DK][1]:,} に ¥{short:,} 足りない "
              f"(送料 ¥{SHIPPING[DK][0]:,})。足りない額が送料より小さければ、spare を増やすと得")
    taxin = {AKI: total[AKI], SEN: total[SEN], DK: round(total[DK] * 1.1)}
    lines += ["## 送料と合計", "",
              "| ショップ | 商品 (税込) | 送料 | 合計 | 送料の条件 |", "|---|---:|---:|---:|---|"]
    lines += [f"| {k} | ¥{taxin[k]:,} | ¥{ship[k]:,} | ¥{taxin[k] + ship[k]:,} | {SHIPPING[k][2]} |" for k in (DK, AKI, SEN)]
    lines += [f"| **計** | ¥{sum(taxin.values()):,} | ¥{sum(ship.values()):,} | **¥{sum(taxin.values()) + sum(ship.values()):,}** | |", "",
              "### 店のまとめ方", "",
              "- **Digi-Key Japan**: Neutrik の基板用 XLR、"
              + ("MUSE FW 100V、WIMA MKP4、" if AUDIO_GRADE else "100V の電解 (Rubycon ZLH)、")
              + "TE YR1 0.1%、P6KE24CA、DIP の UC3843 は秋月電子・千石電商に無い (2026-11 に検索して確認)。"
              "¥6,000 未満だと送料 ¥2,000 かかる。"
              + (f"必要数だけだと ¥{need_dk:,} (税抜) なので、予備と 10 個単価の数量に回して ¥6,000 以上にした"
                 " (予備は修理や2台目に使える。YR1 は値の近い組を選べる)" if not ship[DK] else
                 f"今の数量では ¥{SHIPPING[DK][1] - total[DK]:,} 足りず、送料がかかる。"
                 "足りない額が送料より小さければ、予備を足して ¥6,000 以上にするほうが得"),
              "- **秋月電子通商**: トロイダル・DC ジャック・MOSFET・TVS (P4KE15CA)・スイッチ・LED などは秋月の品で基板を設計している。"
              "送料無料 (¥11,000) までは遠いので、必要な分だけ買う",
              "- **千石電商**: メス-メスの金属スペーサー M3×6・歯付き座金・M3×4 ねじ・タッピンねじ 3×8 は秋月に無い。"
              "小物だけなのでネコポス (¥350) で送れる。近くのホームセンターで同じ規格が買えるならそれでもよい",
              "- マルツは自動では価格を確認できなかった (サイトが自動取得を拒否)",
              "- 千石電商でも買える品: MS-500A-B (¥380、秋月は ¥300)。0.1% の 6.8kΩ はタクマン RN14C2B (¥420/本) があるが YR1 より高い", "",
              "## JLCPCBで実装する部品", "",
              "SMD部品はすべてJLCPCBの基本部品 (Basic Parts) です。一覧は `JLCPCB_BOM.csv` を参照。", ""]
    with open(os.path.join(ROOT, "部品購入リスト.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    import md2html          # 同じ内容の HTML 版を作る
    md2html.refresh()


# ---------------------------------------------------------------- emit
def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def xform(px, py, rot, mirror):
    """Library pin offset (y up) -> sheet offset (y down) for a placed symbol."""
    dx, dy = px, -py
    if mirror:
        dx = -dx
    if rot == 90:
        dx, dy = dy, -dx
    elif rot == 180:
        dx, dy = -dx, -dy
    elif rot == 270:
        dx, dy = -dy, dx
    return dx, dy


def main():
    os.makedirs(OUT, exist_ok=True)
    libs = {"power:GND": lib_block("power", "GND"),
            "power:PWR_FLAG": lib_block("power", "PWR_FLAG")}
    for p in PARTS:
        if p["sym"] not in libs:
            lib, name = p["sym"].split(":")
            libs[p["sym"]] = lib_block(lib, name)
    pins_of = {k: parse_pins(v) for k, v in libs.items()}
    byref = {p["ref"]: p for p in PARTS}
    missing = [p["ref"] for p in PARTS if p["ref"] not in PLACE]
    if missing:
        raise SystemExit("not placed: %s" % missing)

    out, origin, pinpos = [], {}, {}
    for ref, (apin, x, y, rot, mirror, text) in PLACE.items():
        p = byref[ref]
        pins = pins_of[p["sym"]]
        ax, ay = xform(pins[apin]["x"], pins[apin]["y"], rot, mirror)
        ox, oy = x * G - ax, y * G - ay
        origin[ref] = (ox, oy)
        for num, q in pins.items():
            dx, dy = xform(q["x"], q["y"], rot, mirror)
            pinpos[f"{ref}.{num}"] = (round(ox + dx, 4), round(oy + dy, 4))

    def pt(s):
        if isinstance(s, str):
            return pinpos[s]
        return (round(s[0] * G, 4), round(s[1] * G, 4))

    segs = []
    for chain in WIRES:
        pts = [pt(s) for s in chain]
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6:
                raise SystemExit(f"wire not orthogonal: {chain} {a}->{b}")
            segs.append((a, b))
    for a, b in segs:
        out.append(f'(wire (pts (xy {fmt(a[0])} {fmt(a[1])}) (xy {fmt(b[0])} {fmt(b[1])})) '
                   f'(stroke (width 0) (type default)) (uuid "{uid("w", a, b)}"))')

    # junctions: a wire end / pin on the interior of another wire, or 3+ ends meeting
    def interior(p, a, b):
        if abs(a[0] - b[0]) < 1e-6:
            return abs(p[0] - a[0]) < 1e-6 and min(a[1], b[1]) + 1e-6 < p[1] < max(a[1], b[1]) - 1e-6
        return abs(p[1] - a[1]) < 1e-6 and min(a[0], b[0]) + 1e-6 < p[0] < max(a[0], b[0]) - 1e-6

    gnd_pts = [pt(s) for s in GNDS]
    ends = [e for s in segs for e in s]
    cand = set(ends) | set(pinpos.values()) | set(gnd_pts)
    count = {}
    for e in ends:
        count[e] = count.get(e, 0) + 1
    for e in set(pinpos.values()) | set(gnd_pts):
        if e in count:
            count[e] += 1
    for c in sorted(cand):
        if any(interior(c, a, b) for a, b in segs) or count.get(c, 0) >= 3:
            out.append(f'(junction (at {fmt(c[0])} {fmt(c[1])}) (diameter 0) (color 0 0 0 0) (uuid "{uid("j", c)}"))')

    n = [0]

    def power(sym, x, y):
        n[0] += 1
        ref = f"#PWR{n[0]:03d}" if sym == "GND" else f"#FLG{n[0]:03d}"
        out.append(
            f'(symbol (lib_id "power:{sym}") (at {fmt(x)} {fmt(y)} 0) (unit 1) (exclude_from_sim no) (in_bom yes) '
            f'(on_board yes) (dnp no) (uuid "{uid("pwr", ref)}") '
            f'(property "Reference" "{ref}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(property "Value" "{sym}" (at {fmt(x)} {fmt(y + 3.6)} 0) (effects (font (size 1.0 1.0))'
            + (" (hide yes)" if sym != "GND" else "") + ')) '
            f'(property "Footprint" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(property "Datasheet" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(pin "1" (uuid "{uid("pwrpin", ref)}")) '
            f'(instances (project "{PROJECT}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1)))))')

    for g in gnd_pts:
        power("GND", *g)
    for f in FLAGS:
        power("PWR_FLAG", *pt(f))
    for s in NOCONN:
        x, y = pt(s)
        out.append(f'(no_connect (at {fmt(x)} {fmt(y)}) (uuid "{uid("nc", s)}"))')
    for net, x, y, left in LABELS:
        ang, just = (180, "right bottom") if left else (0, "left bottom")
        out.append(f'(label "{net}" (at {fmt(x * G)} {fmt(y * G)} {ang}) (effects (font (size 1.0 1.0)) '
                   f'(justify {just})) (uuid "{uid("l", net, x, y)}"))')
    for x, y, size, txt in TEXTS:
        t = txt.replace("\n", "\\n")
        out.append(f'(text "{t}" (exclude_from_sim no) (at {fmt(x * G)} {fmt(y * G)} 0) '
                   f'(effects (font (size {size} {size})' + (" (bold yes)" if size >= 2 else "") +
                   f') (justify left top)) (uuid "{uid("t", x, y)}"))')

    CW = 0.84   # 文字幅の見積り (mm/文字, size 1.0)
    for ref, (apin, x, y, rot, mirror, text) in PLACE.items():
        p = byref[ref]
        pins = pins_of[p["sym"]]
        ox, oy = origin[ref]
        fa = 90 if rot in (90, 270) else 0   # フィールド角度(シンボル回転と合成されて水平に表示される)
        plain = rot == 0 and not mirror
        if text == "r":
            w = lambda s: 0 if plain else len(s) * CW / 2
            rp = (ox + 1.9 + w(p["ref"]), oy - 1.0, "left" if plain else "")
            vp = (ox + 1.9 + w(p["value"]), oy + 1.1, "left" if plain else "")
        elif text == "a":
            rp, vp = (ox, oy - 4.9, ""), (ox, oy - 3.2, "")
        elif text == "b":
            rp, vp = (ox, oy + 3.4, ""), (ox, oy + 5.1, "")
        else:
            w = lambda s: 0 if plain else len(s) * CW / 2
            rp = (pinpos[f"{ref}.{apin}"][0] + text[0] * G + w(p["ref"]), pinpos[f"{ref}.{apin}"][1] + text[1] * G,
                  "left" if plain else "")
            vp = (pinpos[f"{ref}.{apin}"][0] + text[2] * G + w(p["value"]), pinpos[f"{ref}.{apin}"][1] + text[3] * G,
                  "left" if plain else "")
        dnp = "yes" if p["asm"] == "DNP" else "no"
        s = [f'(symbol (lib_id "{p["sym"]}") (at {fmt(ox)} {fmt(oy)} {rot})' + (" (mirror y)" if mirror else "") +
             f' (unit 1) (exclude_from_sim no) (in_bom {"no" if p["asm"] == "-" else "yes"}) (on_board yes) (dnp {dnp}) '
             f'(uuid "{uid("sym", ref)}")']
        for name, val, (fx, fy, just) in (("Reference", ref, rp), ("Value", p["value"], vp)):
            s.append(f'(property "{name}" "{val}" (at {fmt(fx)} {fmt(fy)} {fa}) (effects (font (size 1.0 1.0))'
                     + (f" (justify {just})" if just else "") + "))")
        for name, val in (("Footprint", p["fp"]), ("Datasheet", ""), ("MPN", p["mpn"]), ("LCSC", p["lcsc"]),
                          ("Assembly", p["asm"]), ("Note", p["note"])):
            s.append(f'(property "{name}" "{val}" (at {fmt(ox)} {fmt(oy)} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        for num in pins:
            s.append(f'(pin "{num}" (uuid "{uid("pin", ref, num)}"))')
        s.append(f'(instances (project "{PROJECT}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1)))))')
        out.append(" ".join(s))

    sch = [f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid "{ROOT_UUID}") '
           f'(paper "User" {PAGE[0]} {PAGE[1]})',
           f'(title_block (title "{TITLE}") ' '(rev "C") '
           '(comment 1 "DC12〜18V入力 / UC3843昇圧 + リップルフィルター / 2ch XLR スルー"))',
           "(lib_symbols", *libs.values(), ")", *out,
           '(sheet_instances (path "/" (page "1")))', "(embedded_fonts no))"]
    with open(os.path.join(OUT, PROJECT + ".kicad_sch"), "w") as f:
        f.write("\n".join(sch) + "\n")
    pro = os.path.join(OUT, PROJECT + ".kicad_pro")
    if not os.path.exists(pro):
        with open(pro, "w") as f:
            f.write('{\n  "meta": {\n    "filename": "%s.kicad_pro",\n    "version": 1\n  }\n}\n' % PROJECT)

    write_outputs()

    # expected netlist for verification
    nets = {}
    for p in PARTS:
        for num, net in p["pins"].items():
            if net:
                nets.setdefault(net, set()).add(f'{p["ref"]}.{num}')
    with open(os.path.join(OUT, "expected_nets.txt"), "w") as f:
        for n_ in sorted(nets):
            f.write(n_ + ": " + " ".join(sorted(nets[n_])) + "\n")
    print(f"{len(PARTS)} parts, {len(nets)} nets")


if __name__ == "__main__":
    main()
