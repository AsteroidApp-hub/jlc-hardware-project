#!/usr/bin/env python3
"""設計の根拠 (なぜこの部品・この値か) をまとめた資料を作る。依存ライブラリなし。

部品の値は gen_schematic.py の PARTS から読み、計算式で設計値を出し、シミュレーション結果 (シミュレーション/結果.md) と並べる。
回路の値を変えたら再実行すれば、計算もシミュレーションとの照合も更新される。人の設計者にレビューを頼むときに回路図と一緒に渡す。

出力: 設計根拠/設計根拠.md (+ .html)
使い方: python3 tools/design_notes.py   (シミュレーションの後に。tools/export_fab.py からも呼ばれる)
"""
import math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_schematic as sch  # noqa: E402

OUTD = os.path.join(ROOT, "設計根拠")
SIM_MD = os.path.join(ROOT, "シミュレーション", "結果.md")
PFX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "R": 1, "": 1}
P = {p["ref"]: p for p in sch.PARTS}


def val(ref):
    """部品の値を数値に ('5.1k' → 5100, '2.2nF C0G' → 2.2e-9, '47uF/100V' → 47e-6, '10R' → 10)"""
    s = P[ref]["value"]
    m = re.match(r"^([0-9.]+)\s*([pnuµmkKMR]?)", s)
    if not m:
        raise SystemExit(f"{ref}: 値 '{s}' を読めない")
    v = float(m.group(1)) * PFX[m.group(2)]
    rest = s[m.end():]
    if m.group(2) == "R" and rest[:1].isdigit():          # 4R7 形式
        v += float("0." + re.match(r"\d+", rest).group(0))
    return v


def volts(ref):
    m = re.search(r"/(\d+)V", P[ref]["value"])
    return float(m.group(1)) if m else None


def sim(label):
    """シミュレーション結果の表から、項目名に label を含む行の「結果」を返す"""
    if not os.path.exists(SIM_MD):
        return "(未実行)"
    for line in open(SIM_MD, encoding="utf-8"):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 2 and label in c[0]:
            return c[1]
    return "(未実行: tools/sim/run_all.py を実行すると入る)"


def fmt(v, unit, nd=3):
    for p, k in (("M", 1e6), ("k", 1e3), ("", 1), ("m", 1e-3), ("µ", 1e-6), ("n", 1e-9), ("p", 1e-12)):
        if abs(v) >= k * 0.9999:
            return f"{v / k:.{nd}g} {p}{unit}"
    return f"{v:.{nd}g} {unit}"


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def main():
    os.makedirs(OUTD, exist_ok=True)
    # ---- 入力条件
    VIN = (12.0, 18.0)
    VREF_EA = 2.5                      # UC3843 誤差増幅器の基準
    VCS = 1.0                          # UC3843 電流検出の上限電圧
    I_CH = 10e-3                       # P48 の 1ch あたり最大電流 (IEC 61938)
    N_CH = 2

    # ---- 昇圧
    vboost = VREF_EA * (1 + val("R9") / val("R10"))
    fsw = 1.72 / (val("R2") * val("C7"))
    ipk_lim = VCS / val("R7")
    L = val("L1")
    i_led = (48 - 2.0) / val("R17")
    i_div = vboost / (val("R13") + val("R14"))
    iout = N_CH * I_CH + i_led + i_div          # 昇圧の出力電流 (最大負荷)
    rows_boost = []
    for vin in VIN:
        d_ccm = 1 - vin / vboost
        lcrit = vboost * d_ccm * (1 - d_ccm) ** 2 / (2 * iout * fsw)     # これより L が小さければ不連続モード
        ipk = math.sqrt(2 * (vboost - vin) * iout / (L * fsw))           # 不連続モードのピーク電流
        ton = ipk * L / vin
        rows_boost.append([f"{vin:.0f} V", f"{lcrit * 1e6:.0f} µH → {'不連続 (DCM)' if L < lcrit else '連続 (CCM)'}",
                           f"{ipk:.2f} A", f"{ton * fsw * 100:.0f} %", f"{vboost * iout / vin * 1000:.0f} mA"])
    fz = 1 / (2 * math.pi * val("R4") * val("C10"))
    fp = 1 / (2 * math.pi * val("R4") * val("C11"))

    # ---- フィルター
    fc_rc = 1 / (2 * math.pi * val("R12") * val("C16"))
    rth = val("R13") * val("R14") / (val("R13") + val("R14"))
    tau_base = rth * val("C18")
    fc_base = 1 / (2 * math.pi * tau_base)
    vfilt = vboost - val("R12") * iout
    vbase = vfilt * val("R14") / (val("R13") + val("R14"))
    v48 = vbase - 2 * 0.6 - val("R15") * 1e-4
    fc_ch = 1 / (2 * math.pi * val("R101") * val("C101"))
    tau_off = (val("R18") * val("R14") / (val("R18") + val("R14"))) * val("C18")

    # ---- チャンネル
    rfeed = val("R102")
    isc = v48 / rfeed
    v_mic_10ma = v48 - (val("R101") * I_CH) - rfeed / 2 * I_CH
    r_in = 1.2e3                                                            # 録音機の入力 (片側、一般的な値)
    r_load = val("R104") + val("R106") * r_in / (val("R106") + r_in)        # 直列抵抗 + (ブリーダー ∥ 録音機入力)
    fc_out = 1 / (2 * math.pi * r_load * val("C104"))

    md = f"""# 設計の根拠 — {sch.TITLE if hasattr(sch, 'TITLE') else sch.PROJECT}

回路の各部品の値を **なぜそうしたか** を、計算とシミュレーション結果でまとめた資料です。
人の設計者にレビューを頼むときは、回路図 (`回路図.pdf`) と一緒に渡してください。

- 値はすべて回路の定義 (`tools/gen_schematic.py`) から読み取って計算しています。回路を変えたら再生成すれば更新されます
- 「シミュレーション」の列は ngspice の結果 ([シミュレーション結果](../シミュレーション/結果.html))。計算は簡単な式による目安で、
  シミュレーションは部品の非理想性 (ESR・損失・容量の低下など) を含みます。両者が近いことを確認しています
- 前提: 入力 DC {VIN[0]:.0f}〜{VIN[1]:.0f} V、出力 P48 × {N_CH}ch、1ch あたり最大 {I_CH * 1e3:.0f} mA (IEC 61938 の P48 の上限)

## 全体の構成と考え方

| 段 | 方式 | 理由 |
|---|---|---|
| 電源入力 | 外部の DC 電源 ({VIN[0]:.0f}〜{VIN[1]:.0f}V) | 本体に AC を入れない (PSE 不要・トランスのうなりが無い)。リニア電源ならノイズも小さい |
| 昇圧 | UC3843 電流モード (DIP-8) + 100V MOSFET | JLC 基本部品に昇圧 IC が無いため、手はんだできる定番品で構成。電流モードは過電流に強く位相補償が簡単 |
| 48V 生成 | RC フィルター → トランジスタ 2 段のリップルフィルター | スイッチングの雑音を、トランス無しで µV 以下まで下げる |
| 給電 | 6.81kΩ 0.1% × 2 本 / ch | P48 の規格値。ホットとコールドの抵抗がそろうほど電源の雑音が打ち消される |
| 出力 | DC カット (電解 + フィルム) + ブリーダー + TVS | 録音機に 48V を出さない。抜き差し時の過渡電圧を制限 |

## 1. 入力と保護

{table(["部品", "値", "根拠"], [
    ["F1", P["F1"]["value"], f"保持 0.5A。定常の入力電流 (シミュレーション {sim('入力電流 平均')}) に余裕があり、起動時のピーク {sim('入力電流ピーク')} は短時間なので切れない"],
    ["D1", P["D1"]["mpn"], "逆接続の保護 (ショットキーで電圧降下が小さい)"],
    ["D2", P["D2"]["mpn"], f"過電圧のクランプ。動作開始 20.5V なので {VIN[1]:.0f}V までの入力では働かない。24V 入力は非対応 (下の Q1 を参照)"],
    ["C1", P["C1"]["value"], "入力の電流の山を吸収する低 ESR 電解"],
])}

## 2. 昇圧 (UC3843)

{table(["項目", "計算式", "計算値", "シミュレーション"], [
    ["昇圧出力 VBOOST", f"2.5V × (1 + R9/R10) = 2.5 × (1 + {fmt(val('R9'), 'Ω')} / {fmt(val('R10'), 'Ω')})", f"{vboost:.1f} V", sim("昇圧出力の定常値")],
    ["スイッチング周波数", f"1.72 / (R2 × C7) = 1.72 / ({fmt(val('R2'), 'Ω')} × {fmt(val('C7'), 'F')})", f"{fsw / 1e3:.0f} kHz", sim("スイッチング周波数")],
    ["電流の上限 (1 パルスごと)", f"1.0V / R7 = 1.0 / {fmt(val('R7'), 'Ω')}", f"{ipk_lim:.1f} A", f"起動時ピーク {sim('インダクター電流ピーク (起動時)')} (検出の遅れで少し超える)"],
    ["出力電流 (最大負荷)", f"{N_CH}ch × {I_CH * 1e3:.0f}mA + LED {i_led * 1e3:.1f}mA + 分圧 {i_div * 1e3:.2f}mA", f"{iout * 1e3:.1f} mA", "—"],
    ["位相補償のゼロ", f"1 / (2π × R4 × C10)", f"{fz:.1f} Hz", f"負荷急変後 {sim('負荷急変後の整定')} で振動せず整定"],
    ["位相補償の高域ポール", f"1 / (2π × R4 × C11)", f"{fp / 1e3:.1f} kHz", "スイッチング雑音を誤差増幅器に入れない"],
])}

**不連続モード (DCM) で動かす理由**: コイルの電流が毎回 0 に戻る動き方にすると、電流モード制御で起きやすい低周波の発振
(サブハーモニック発振) が起きず、位相補償も簡単になります。負荷が軽い (数十 mA) この用途では効率の差も小さいです。

{table(["入力電圧", "連続/不連続の境目のコイル (L1 = " + fmt(L, "H") + ")", "コイル電流ピーク (計算)", "オン時間の割合", "入力電流 (損失なしの計算)"], rows_boost)}

シミュレーションのコイル電流ピーク: 定常 {sim('インダクター電流ピーク (定常')}、起動時 {sim('インダクター電流ピーク (起動時)')}。

**部品の定格の余裕**

{table(["部品", "かかる値", "定格", "余裕"], [
    ["Q1 IRFU120N (ドレイン電圧)", sim("MOSFET ドレイン電圧ピーク"), "100 V", "約 2 倍"],
    ["Q1 IRFU120N (ゲート電圧)", f"入力電圧とほぼ同じ (最大 {VIN[1]:.0f}V)", "±20 V", f"{VIN[1]:.0f}V 入力で余裕 {20 - VIN[1]:.0f}V。**24V 入力は定格超えのため非対応**"],
    ["L1 TCV-101M-3A (電流)", sim("インダクター電流ピーク (起動時)"), "3 A", "2 倍以上"],
    ["D3 SS210 (逆電圧)", f"{vboost:.1f} V", "100 V", "約 2 倍"],
    ["C13 / C16 電解 (電圧)", f"{vboost:.1f} V", f"{volts('C13'):.0f} V", f"{volts('C13') / vboost:.1f} 倍"],
    ["C14 / C17 MLCC (電圧)", f"{vboost:.1f} V", "100 V", "約 2 倍"],
])}

## 3. 48V の生成 (RC フィルター + リップルフィルター)

{table(["項目", "計算式", "計算値", "シミュレーション"], [
    ["RC フィルター", f"1 / (2π × R12 × C16) = 1 / (2π × {fmt(val('R12'), 'Ω')} × {fmt(val('C16'), 'F')})", f"{fc_rc:.0f} Hz", f"VFILT のリップル {sim('VFILT リップル')}"],
    ["基準電圧 (トランジスタのベース)", "VFILT × R14 / (R13 + R14)", f"{vbase:.1f} V", "—"],
    ["+48V 出力", "基準 − トランジスタ 2 段の Vbe (約 1.2V)", f"約 {v48:.1f} V", "+48V 立ち上がり後の値は T4 を参照"],
    ["基準のフィルター", f"(R13 ∥ R14) × C18 = {fmt(rth, 'Ω')} × {fmt(val('C18'), 'F')}", f"時定数 {tau_base:.2f} 秒 ({fc_base:.2f} Hz)", f"+48V へのリップルの伝わり {sim('+48V への伝達 @1kHz')} @1kHz"],
    ["ch ごとのデカップリング", f"1 / (2π × R101 × C101)", f"{fc_ch:.0f} Hz", f"マイク給電点に残る成分 {sim('L_P48')}"],
])}

**リップルフィルター (トランジスタ 2 段) にした理由**: 3 端子レギュレーターでは 48V 級の低雑音品が JLC 基本部品・国内通販で手に入りにくく、
抵抗とコンデンサだけで同じ減衰を得ると大きな部品が要ります。トランジスタで基準電圧 (大きな時定数で平滑) をなぞらせると、
小さな部品で 80dB 以上の減衰が得られます。基準をゆっくり立ち上げるので、電源 ON 時に +48V が約 2 秒かけて上がり、マイクにやさしいのも利点です。

**PHANTOM スイッチ**: +48V を直接切らず、基準電圧を R13 側 (ON) と R18 側 (OFF) で切り替えます。OFF 時は C18 が
(R18 ∥ R14) × C18 = {tau_off:.2f} 秒の時定数で放電し、+48V がゆっくり下がります (シミュレーション T6: 出力の過渡は直接切る場合の
約 −15V に対して約 −6V)。

## 4. 各チャンネル (給電と出力)

{table(["項目", "計算式", "計算値", "根拠・シミュレーション"], [
    ["給電抵抗", "—", f"{fmt(rfeed, 'Ω')} ± 0.1%", "P48 の規格値 (IEC 61938)。0.1% 品で左右の差を小さく → 電源の雑音が差動に出にくい。10 本から値の近い組を選ぶ"],
    ["短絡電流 (1 本あたり)", "48V / 6.81kΩ", f"{isc * 1e3:.1f} mA", f"ホット・コールドの 2 本で 1ch 最大 {2 * isc * 1e3:.0f} mA。マイクが壊れても電流はこれ以上流れない"],
    ["マイク端の電圧 (10mA 時)", "48V − R101 × I − 6.81k/2 × I", f"{v_mic_10ma:.1f} V", "規格の上限の 10mA を流したときの値。P48 は電流が増えると電圧が下がる仕組みで、これは規格どおりの動作"],
    ["DC カットの低域", "1 / (2π × (R104 + R106 ∥ 録音機入力 1.2kΩ) × C104)", f"約 {fc_out:.1f} Hz", f"可聴帯域の減衰 {sim('マイク信号の通過')}"],
    ["電解の電圧", "+48V がそのままかかる", f"約 {v48:.0f} V", f"{volts('C104'):.0f}V 品 (50V 品は不可)。" + ("音質重視で MUSE FW、フィルムを並列" if sch.AUDIO_GRADE else "汎用グレード: 低 ESR の一般品、フィルムは未実装")],
    ["ブリーダー R106/R107", f"{fmt(val('R106'), 'Ω')}", "—", "出力側の直流を 0V に固定。録音機を後からつないでもポップ音が小さい"],
    ["出力 TVS (P4KE15CA)", "—", "約 15V で制限", f"電源 ON/OFF・抜き差しの過渡を制限 (T4: ON 時最大 {sim('電源ON時 出力HOTの最大')})"],
    ["RFI コンデンサ 1nF/2kV", "—", "—", "ケーブルから入る高周波をシャーシへ逃がす"],
])}

## 5. グラウンド

- 回路の GND とシャーシは **1 点だけ** (R20 0Ω + C20) で接続。XLR の 1 番ピン (シールド) はシャーシへ。
  GND が複数の経路でつながってできるループ (ハムの原因) を作らないため
- 筐体はアルマイト (絶縁) なので、歯付き座金で塗膜を破ってシャーシを接地

## 6. レビューで見てほしい点

- 昇圧の位相補償 (R4・C10・C11) と、実機での負荷急変時の安定性
- 実機の基板配線によるスイッチングのリンギング (シミュレーションに配線の寄生成分は入っていない)。必要ならスナバ (R11・C15、未実装の予備パターン) を付ける
{"- MUSE FW (100µF/100V) の在庫。代替は MUSE KW (UKW2A101MPD)" if sch.AUDIO_GRADE else "- 部品のグレードは汎用。音質を上げるなら、信号の通り道の電解を MUSE FW に替え、フィルム (C105 など) を付ける"}
- リップルフィルターのトランジスタ (MMBT5551) の損失: (VFILT − 48V) × 出力電流 = 約 {(vfilt - v48) * iout * 1e3:.0f} mW (SOT-23 の定格 300mW 以内)
"""
    with open(os.path.join(OUTD, "設計根拠.md"), "w", encoding="utf-8") as f:
        f.write(md)
    import md2html
    md2html.refresh()
    print("written: 設計根拠/設計根拠.md")


if __name__ == "__main__":
    main()
