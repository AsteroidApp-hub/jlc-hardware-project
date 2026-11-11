#!/usr/bin/env python3
"""回路定義 (tools/gen_schematic.py の PARTS) から ngspice ネットリストを生成する。

回路図とシミュレーションの回路を一致させるため、部品・接続はすべて PARTS から作る。
コネクタ類は試験用の部品に置き換える:
  J1 (DCジャック)  -> 12V ACアダプター (出力抵抗 0.1Ω)
  J2 (電源SW)      -> 0.01Ω
  J101/J201 (MIC IN) -> マイクの等価モデル (ファンタム電流シンク + 50Ω平衡出力)
  J102/J202 (OUT)  -> 録音機の入力 (各線 Rin 対GND)
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import gen_schematic as sch  # noqa: E402

PFX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "R": 1.0, "": 1.0}


def value(s):
    """'100k' / '6.81k 0.1%' / '10uF/50V' / '2.2nF C0G' / '1R' / '0R' -> float"""
    m = re.match(r"\s*([0-9.]+)\s*([pnuµmkKMR]?)", s)
    if not m:
        raise ValueError(s)
    v = float(m.group(1)) * PFX[m.group(2)]
    return v


def node(net):
    if net is None:
        return None
    if net == "GND":
        return "0"
    return net.replace("+", "P").replace("/", "_")


# 電解コンデンサのESR [Ω] (データシート代表値からの概算)
ESR = {"35ZLH470M": 0.05, "UPW2A470MPD": 0.3, "UFW1J101MPD": 0.6}
# MLCCのDCバイアスによる容量低下 (実効容量の倍率, 概算)
DERATE = {"C2": 0.5, "C4": 0.5, "C14": 0.8, "C17": 0.8, "C19": 0.8}

MODELS = r"""
* ---- models (データシートからの概算モデル)
.model SS34 D(Is=1e-5 N=1.3 Rs=0.03 Cjo=200p M=0.5 Vj=0.35 BV=40 IBV=1m)
.model SS210 D(Is=2e-6 N=1.5 Rs=0.06 Cjo=120p M=0.45 Vj=0.35 BV=110 IBV=0.5m)
.model D1N4148 D(Is=2.52n Rs=0.568 N=1.752 Cjo=4p M=0.4 Tt=20n BV=100 IBV=100u)
.model LEDG D(Is=8e-27 N=2.0 Rs=10 Cjo=20p)
.model Z15 D(Is=1e-12 N=1 Rs=0.3 BV=15 IBV=1m Cjo=400p)
.model MMBT5551 NPN(IS=2.511f XTI=3 EG=1.11 VAF=100 BF=242.6 NE=1.249 ISE=2.511f IKF=.3458 XTB=1.5 BR=3.197
+ NC=2 ISC=0 IKR=0 RC=1 CJC=4.883p MJC=.3047 VJC=.75 FC=.5 CJE=18.79p MJE=.3416 VJE=.75 TR=1.202n TF=560.1p
+ ITF=50m VTF=5 XTF=8 RB=10)
.model IRFU120N VDMOS(Vto=3.2 Kp=6 Rd=0.12 Rs=0.03 Rg=3 Cgdmax=0.35n Cgdmin=0.03n a=0.4 Cgs=0.4n Cjo=0.25n
+ m=0.6 Is=1e-11 Rb=0.02 BV=100 IBV=250u tt=120n mtriode=1.5 lambda=0.01)
.model DCLAMP D(Is=1e-14 N=1 Rs=10)
.model SWPH SW(Ron=0.05 Roff=1G Vt=0.5 Vh=0.05)

* 双方向TVS P4KE15CA (VBR 15V) / P6KE24CA (VBR 24V)
.subckt TVS15 A1 A2
D1 A1 m Z15
D2 A2 m Z15
.ends
.model Z24 D(Is=1e-12 N=1 Rs=0.3 BV=24 IBV=1m Cjo=400p)
.subckt TVS24 A1 A2
D1 A1 m Z24
D2 A2 m Z24
.ends

* 電解コンデンサ (容量 + ESR)
.subckt ECAP P N C=100u ESR=0.3
R1 P a {ESR}
C1 a N {C}
.ends

* UC3843 動作モデル
*   発振: R2/C7 から求めた 153kHz の理想クロック (デッドタイム 250ns = 最大デューティ 96%)
*   誤差増幅器: 基準 2.5V, 開ループ 90dB, GBW 約1MHz, 出力 0.7〜6V
*   電流比較: しきい値 = min((COMP-1.4V)/3, 1.0V)
*   UVLO: VCC > 8.4V で動作, VREF = 5V
.subckt UC3843 COMP FB CS RC GND OUT VCC VREF params: FSW=153k
Ben en GND V = 0.5*(1+tanh((V(VCC,GND)-8.4)/0.05))
Bref vr0 GND V = 5*V(en)
Rref vr0 VREF 2
Gcc VCC GND value = {15m*V(en)}
* 誤差増幅器
Gea GND ea value = {1m*(2.5*V(en) - V(FB,GND))}
Rea ea GND 31.6Meg
Cea ea GND 159p
Dh ea hcl DCLAMP
Vh hcl GND 6.0
Dl lcl ea DCLAMP
Vl lcl GND 0.0
Bco co GND V = min(max(V(ea,GND),0.7),6)*V(en)
Rco co COMP 100
* 電流比較
Bth th GND V = min(max((V(COMP,GND)-1.4)/3,0),1.0)
Bcmp cmp GND V = 0.5*(1+tanh((V(CS,GND)-V(th,GND))/2m))
* クロック (デッドタイム中は出力OFF、デッドタイム終了時にセット)
Vdead dead GND PULSE(0 1 0 5n 5n 240n {1/FSW})
Vset setp GND PULSE(0 1 255n 5n 5n 40n {1/FSW})
* SRラッチ (アナログ等価): セットでQ→1、電流比較またはデッドタイムでQ→0
Gq GND q value = {2m*V(setp)*(1-V(q)) - 2m*min(V(cmp)+V(dead)+1-V(en),1)*V(q)}
Cq q GND 10p
Rq q GND 1G
Bqa qa GND V = min(max(V(q),0),1)
* ゲートドライバ (出力 約±1A)
Bdrv drv GND V = V(qa)*max(V(VCC,GND)-1.5,0)*V(en)
Rdrv drv OUT 6
* RC ピンは外付けの R2/C7 を接続するだけ (内部では未使用)
Rrc RC GND 1G
.ends

* マイク 1ch 等価モデル: ファンタム電流シンク + 平衡出力 50Ω
.subckt MICCH HOT COLD SHIELD params: IPH=3.5m
Rh HOT mh 25
Rc COLD mc 25
Vsh mh mid DC 0 AC 0.5
Vsc mid mc DC 0 AC 0.5
* 電圧が低いうちは電流を引けない (約10V以上で一定電流 IPH)
Gph mid SHIELD value = {IPH*tanh(max(V(mid,SHIELD),0)/5)}
.ends
"""


def build(overrides=None, mic=True, iph=3.5e-3, rin=1.2e3, adapter="DC 12", vboost_src=None, extra="",
          mismatch=True, skip=(), phantom="DC 1"):
    """PARTS からネットリスト本文を作る。
    vboost_src: None=実際の昇圧回路 / 文字列=昇圧部を外して VBOOST にこの電圧源を置く
    """
    overrides = overrides or {}
    lines = []
    boost_refs = {"U1", "R1", "C4", "C5", "C6", "R2", "C7", "R9", "R10", "C10", "R4", "C11", "R5", "R6", "Q1", "R7",
                  "R8", "C12", "L1", "R11", "C15", "D3", "J1", "F1", "D1", "D2", "C1", "C2", "C3"}
    for p in sch.PARTS:
        ref, sym, pins = p["ref"], p["sym"], p["pins"]
        if ref in skip or p["asm"] == "-":
            continue
        if vboost_src is not None and ref in boost_refs:
            continue
        n = {k: node(v) for k, v in pins.items()}
        if ref in overrides:
            lines.append(overrides[ref].format(**{f"n{k}": v for k, v in n.items()}))
            continue
        if p["asm"] == "DNP":
            continue
        if sym == "Device:R":
            v = value(p["value"])
            if v == 0:
                v = 1e-3
            if mismatch and ref in ("R102", "R202"):
                v *= 1.001
            if mismatch and ref in ("R103", "R203"):
                v *= 0.999
            lines.append(f"R{ref} {n['1']} {n['2']} {v:.6g}")
        elif sym == "Device:C":
            v = value(p["value"]) * DERATE.get(ref, 1.0)
            lines.append(f"C{ref} {n['1']} {n['2']} {v:.6g}")
        elif sym == "Device:C_Polarized":
            mpn = p["mpn"].split()[-1] if p["mpn"] else ""
            esr = next((e for k, e in ESR.items() if k in p["mpn"]), 0.3)
            v = value(p["value"])
            if mismatch and ref in ("C104", "C204"):
                v *= 1.2
            if mismatch and ref in ("C106", "C206"):
                v *= 0.8
            lines.append(f"X{ref} {n['1']} {n['2']} ECAP C={v:.6g} ESR={esr}")
        elif sym == "Device:L":
            lines.append(f"L{ref} {n['1']} {ref}_dcr {value(p['value']):.6g}")
            lines.append(f"R{ref}_dcr {ref}_dcr {n['2']} 0.25")
        elif sym in ("Device:D", "Device:D_Schottky"):
            model = {"SS34": "SS34", "SS210": "SS210", "1N4148W": "D1N4148"}[p["value"]]
            lines.append(f"D{ref} {n['2']} {n['1']} {model}")
        elif sym == "Device:LED":
            lines.append(f"D{ref} {n['2']} {n['1']} LEDG")
        elif sym == "Device:D_TVS":
            lines.append(f"X{ref} {n['1']} {n['2']} " + ("TVS24" if "24" in p["value"] else "TVS15"))
        elif sym == "Device:Polyfuse":
            lines.append(f"R{ref} {n['1']} {n['2']} 1.0")
        elif sym == "Transistor_BJT:Q_NPN_BEC":
            lines.append(f"Q{ref} {n['3']} {n['1']} {n['2']} MMBT5551")
        elif sym == "Transistor_FET:Q_NMOS_GDS":
            lines.append(f"M{ref} {n['2']} {n['1']} {n['3']} IRFU120N")
        elif sym == "Regulator_Controller:UC3842_SOIC8":
            lines.append(f"X{ref} " + " ".join(n[str(i)] for i in range(1, 9)) + " UC3843")
        elif sym == "Connector:Barrel_Jack_Switch":
            lines.append(f"Vadapter adp 0 {adapter}")
            lines.append(f"Radapter adp {n['1']} 0.1")
        elif sym == "Connector_Generic:Conn_01x03":
            # PHANTOM スイッチ (ON-ON): 制御 1 = 2-1 接続 (ON), 0 = 2-3 接続 (OFF)
            lines.append(f"V{ref}_ctl {ref}_ctl 0 {phantom}")
            lines.append(f"B{ref}_inv {ref}_inv 0 V = 1 - V({ref}_ctl)")
            lines.append(f"S{ref}_on {n['2']} {n['1']} {ref}_ctl 0 SWPH")
            lines.append(f"S{ref}_off {n['2']} {n['3']} {ref}_inv 0 SWPH")
        elif sym == "Connector_Audio:XLR3_Ground":
            if mic:
                lines.append(f"X{ref} {n['2']} {n['3']} {n['1']} MICCH IPH={iph}")
        elif sym == "Connector_Audio:XLR3":
            lines.append(f"R{ref}_h {n['2']} {n['1']} {rin:.6g}")
            lines.append(f"R{ref}_c {n['3']} {n['1']} {rin:.6g}")
        else:
            raise SystemExit(f"no SPICE mapping for {ref} {sym}")
    if vboost_src is not None:
        lines.append(f"Vboost VBOOST 0 {vboost_src}")
    return MODELS + "\n* ---- circuit (generated from PARTS)\n" + "\n".join(lines) + "\n" + extra


if __name__ == "__main__":
    print(build())
