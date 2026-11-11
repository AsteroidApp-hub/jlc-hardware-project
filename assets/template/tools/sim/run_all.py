#!/usr/bin/env python3
"""2ch P48 ファンタム電源 — ngspice シミュレーション一式

使い方 (numpy / matplotlib が必要):  python3 tools/sim/run_all.py [T1 T2 ...]
結果: シミュレーション/ フォルダに グラフ(PNG) と 結果.md を出力する。

T1 起動と負荷急変   : 昇圧回路をスイッチング込みで 0〜40ms。30msで負荷+16mA
T2 定常リップル     : 昇圧出力のリップルとスペクトル (オーディオ帯の低周波成分の有無も確認)
T3 周波数特性 (AC)  : 昇圧出力 → +48V / マイク出力 への伝達 (0.1%抵抗と電解±20%の誤差込み)、マイク信号の通過特性
T4 電源ON/OFF       : 0〜14秒。+48Vの立ち上がりと、XLR出力に出る過渡電圧
"""
import shutil, os, subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
OUTD = os.path.join(ROOT, "シミュレーション")
WORK = os.path.join(HERE, "out")
os.makedirs(OUTD, exist_ok=True)
os.makedirs(WORK, exist_ok=True)
for f in ("Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans JP", "Noto Sans CJK JP"):
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3, "font.size": 9})

FSW = 153e3
RESULTS = []


# ngspice のコマンド (Windows 版は ngspice_con.exe がバッチ実行用。環境変数 NGSPICE で指定も可)
NGSPICE = os.environ.get("NGSPICE") or shutil.which("ngspice_con") or shutil.which("ngspice") or "ngspice"

def run(name, body, signals, wr_step=None):
    """ネットリストを実行し、signals の列を numpy 配列で返す (先頭列は時間/周波数)"""
    data = os.path.join(WORK, name + ".dat")
    if os.environ.get("REUSE") and os.path.exists(data):   # 既存の計算結果を再利用 (グラフ・集計だけやり直す)
        return np.loadtxt(data, skiprows=1)
    ctrl = ["set wr_singlescale", "set wr_vecnames", "run"]
    if wr_step:
        ctrl.append(f"linearize {' '.join(signals)}")
    ctrl += [f"wrdata {data} {' '.join(signals)}", "quit"]
    net = f"* {name}\n" + body + "\n.control\n" + "\n".join(ctrl) + "\n.endc\n.end\n"
    path = os.path.join(WORK, name + ".cir")
    open(path, "w").write(net)
    r = subprocess.run([NGSPICE, "-b", path], capture_output=True, text=True)
    if not os.path.exists(data):
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"{name}: ngspice failed")
    arr = np.loadtxt(data, skiprows=1)
    return arr


def note(title, rows):
    RESULTS.append((title, rows))
    print("==", title)
    for k, v, j in rows:
        print(f"   {k}: {v}  [{j}]")


# ------------------------------------------------------------------ T1
def t1():
    extra = """
Istep VBOOST 0 PWL(0 0 30m 0 30.001m 16m 35m 16m 35.001m 0)
.options reltol=1e-4 abstol=1n vntol=10u itl4=200
.tran 20n 40m 0 20n
"""
    sig = ["v(VBOOST)", "i(LL1)", "v(SW)", "i(Vadapter)", "v(P48V)", "v(COMP)", "v(VCC)"]
    a = run("T1_startup", build.build(extra=extra), sig)
    t, vb, il, vsw, iin, v48, comp, vcc = a.T
    iin = -iin
    # 指標
    reg = np.median(vb[(t > 25e-3) & (t < 29.9e-3)])
    t95 = t[np.argmax(vb > 0.95 * reg)]
    over = vb[t < 29.9e-3].max() - reg
    w = (t > 30e-3) & (t < 34.9e-3)
    dip = reg - vb[w].min()
    post = np.median(vb[(t > 33e-3) & (t < 34.9e-3)])
    w2 = (t > 35e-3)
    ovs = vb[w2].max() - reg
    # 負荷急変後に ±0.1V に収まるまでの時間
    idx = np.where(w & (np.abs(vb - post) > 0.1))[0]
    settle = (t[idx[-1]] - 30e-3) if len(idx) else 0
    note("T1 起動と負荷急変 (入力12V, 昇圧出力にマイク 2ch 分の負荷 + 30msで+16mA)", [
        ("昇圧出力の定常値", f"{reg:.2f} V", "設計値 51.5V"),
        ("起動時間 (95%到達)", f"{t95 * 1e3:.1f} ms", ""),
        ("起動時の行き過ぎ", f"{over * 1e3:.0f} mV", "OK" if over < 1.0 else "要対策"),
        ("インダクター電流ピーク (起動時)", f"{il.max():.2f} A", "TCV-101M-3A 定格3A" + (" 超過" if il.max() > 3 else " 以内")),
        ("インダクター電流ピーク (定常 +16mA時)", f"{il[w].max():.2f} A", ""),
        ("MOSFET ドレイン電圧ピーク", f"{vsw.max():.1f} V", "IRFU120N 定格100V"),
        ("入力電流ピーク (起動時)", f"{iin.max():.2f} A", "MF-R050 保持0.5A/トリップ1A (短時間なら遮断しない)"),
        ("入力電流 平均 (定常)", f"{np.mean(iin[(t > 25e-3) & (t < 29.9e-3)]) * 1e3:.0f} mA", ""),
        ("負荷+16mA時の電圧低下", f"{dip * 1e3:.0f} mV", ""),
        ("負荷急変後の整定 (±0.1V)", f"{settle * 1e3:.2f} ms", "振動せず収束すれば位相余裕あり"),
        ("負荷解放時の行き過ぎ", f"{ovs * 1e3:.0f} mV", ""),
    ])
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    ax[0].plot(t * 1e3, vb, lw=0.8, label="VBOOST (昇圧出力)")
    ax[0].plot(t * 1e3, v48, lw=0.8, label="+48V (立ち上がりは約1秒かけて上昇)")
    ax[0].set_ylabel("V"); ax[0].legend(loc="lower right")
    ax[0].set_title("T1 起動と負荷急変 (30msで+16mA、35msで解放)")
    ax[1].plot(t * 1e3, il, lw=0.4, label="インダクター電流")
    ax[1].plot(t * 1e3, iin, lw=0.4, alpha=0.7, label="入力電流 (アダプター)")
    ax[1].axhline(3.0, color="r", ls="--", lw=0.8, label="TCV-101M-3A 定格 3A")
    ax[1].set_ylabel("A"); ax[1].legend(loc="upper right")
    ax[2].plot(t * 1e3, comp, lw=0.8, label="COMP (誤差増幅器出力)")
    ax[2].plot(t * 1e3, vcc, lw=0.8, label="VCC")
    ax[2].set_ylabel("V"); ax[2].set_xlabel("時間 [ms]"); ax[2].legend(loc="center right")
    fig.tight_layout(); fig.savefig(os.path.join(OUTD, "T1_起動と負荷急変.png")); plt.close(fig)
    # 負荷急変部分の拡大
    fig, ax = plt.subplots(1, 1, figsize=(9, 3.5))
    m = (t > 29e-3) & (t < 38e-3)
    ax.plot(t[m] * 1e3, vb[m], lw=0.6)
    ax.set_title("T1 負荷急変の拡大 (VBOOST)"); ax.set_xlabel("時間 [ms]"); ax.set_ylabel("V")
    fig.tight_layout(); fig.savefig(os.path.join(OUTD, "T1_負荷急変_拡大.png")); plt.close(fig)
    # 1周期の波形
    fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    m = (t > 28e-3) & (t < 28e-3 + 3 / FSW)
    ax[0].plot((t[m] - 28e-3) * 1e6, vsw[m], lw=0.8); ax[0].set_ylabel("ドレイン電圧 [V]")
    ax[0].set_title("T1 スイッチング波形 (定常, 3周期)")
    ax[1].plot((t[m] - 28e-3) * 1e6, il[m], lw=0.8); ax[1].set_ylabel("インダクター電流 [A]")
    ax[1].set_xlabel("時間 [µs]")
    fig.tight_layout(); fig.savefig(os.path.join(OUTD, "T1_スイッチング波形.png")); plt.close(fig)


# ------------------------------------------------------------------ T2
def t2():
    # 昇圧出力を 51.5V に予備充電した状態から開始し、定常に入った後のリップルを測る
    extra = """
Spre VBOOST vpre ctl 0 SWPRE
Vpre vpre 0 DC 51.5
Vctl ctl 0 PWL(0 1 1u 1 1.1u 0)
.model SWPRE SW(Ron=0.01 Roff=1G Vt=0.5 Vh=0.1)
.options reltol=1e-5 abstol=1p vntol=1u itl4=300 method=gear
.tran 20n 18m 0 20n
"""
    sig = ["v(VBOOST)", "v(VFILT)"]
    a = run("T2_ripple", build.build(extra=extra), sig)
    t, vb, vf = a.T
    m = t > 8e-3
    tt = np.arange(t[m][0], t[m][-1], 20e-9)
    # 予備充電からの整定によるゆっくりした変化 (積分の時定数 R4·C10 ≒ 47ms) を2次式で除いてから評価する
    vbi = np.interp(tt, t, vb)
    vfi = np.interp(tt, t, vf)
    drift = vbi[-1] - vbi[0]
    vbi = vbi - np.polyval(np.polyfit(tt, vbi, 2), tt)
    vfi = vfi - np.polyval(np.polyfit(tt, vfi, 2), tt)
    win = np.hanning(len(tt))
    def spec(x):
        X = np.fft.rfft((x - x.mean()) * win) / (win.sum() / 2)
        return np.fft.rfftfreq(len(tt), 20e-9), np.abs(X)
    f, Sb = spec(vbi)
    _, Sf = spec(vfi)
    np.save(os.path.join(WORK, "T2_spec.npy"), np.vstack([f, Sb, Sf]))
    k = np.argmax(Sb * (f > 50e3))
    audio = (f > 20) & (f < 20e3)
    note("T2 定常リップル (昇圧出力 VBOOST / RCフィルター後 VFILT)", [
        ("VBOOST リップル p-p", f"{(vbi.max() - vbi.min()) * 1e3:.1f} mV", "ダイオード電流×C13のESRによるスパイク状"),
        ("評価区間の整定によるゆっくりした変化", f"{drift * 1e3:.0f} mV / {(tt[-1] - tt[0]) * 1e3:.0f} ms", "除去して評価"),
        ("VFILT リップル p-p", f"{(vfi.max() - vfi.min()) * 1e3:.2f} mV", "R12 22Ω + C16 47µF"),
        ("スイッチング周波数 (スペクトル最大)", f"{f[k] / 1e3:.1f} kHz", "設計 153kHz"),
        ("VBOOST 基本波成分", f"{Sb[k] * 1e3:.2f} mV (振幅)", ""),
        ("VBOOST 可聴帯域(20Hz〜20kHz)の最大成分", f"{Sb[audio].max() * 1e6:.1f} µV @ {f[audio][np.argmax(Sb[audio])]:.0f}Hz",
         "パルススキップ等の低周波成分の有無"),
    ])
    fig, ax = plt.subplots(2, 1, figsize=(9, 6))
    mm = (t > 15e-3) & (t < 15e-3 + 4 / FSW)
    ax[0].plot((t[mm] - 15e-3) * 1e6, (vb[mm] - vb[mm].mean()) * 1e3, lw=0.8, label="VBOOST")
    ax[0].plot((t[mm] - 15e-3) * 1e6, (vf[mm] - vf[mm].mean()) * 1e3, lw=0.8, label="VFILT")
    ax[0].set_xlabel("時間 [µs]"); ax[0].set_ylabel("リップル [mV]"); ax[0].legend()
    ax[0].set_title("T2 定常リップル")
    ax[1].loglog(f[1:], Sb[1:], lw=0.6, label="VBOOST")
    ax[1].loglog(f[1:], Sf[1:], lw=0.6, label="VFILT")
    ax[1].axvspan(20, 20e3, color="g", alpha=0.08, label="可聴帯域")
    ax[1].set_xlim(100, 3e6); ax[1].set_ylim(1e-9, 1)
    ax[1].set_xlabel("周波数 [Hz]"); ax[1].set_ylabel("振幅 [V]"); ax[1].legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUTD, "T2_定常リップル.png")); plt.close(fig)


# ------------------------------------------------------------------ T3
def t3():
    sig = ["v(P48V)", "v(L_P48)", "v(L_OUT_H)", "v(L_OUT_C)"]
    common = "\n.options reltol=1e-6\n.ac dec 50 1 10Meg\n"
    # (a) 昇圧出力 → 各部 (マイク信号なし)
    body = build.build(vboost_src="DC 51.5 AC 1", extra=common).replace("MICCH IPH=0.0035",
                                                                        "MICCH IPH=0.0035 ACM=0")
    body = body.replace("Vsh mh mid DC 0 AC 0.5", "Vsh mh mid DC 0 AC {ACM/2}").replace(
        "Vsc mid mc DC 0 AC 0.5", "Vsc mid mc DC 0 AC {ACM/2}").replace(
        ".subckt MICCH HOT COLD SHIELD params: IPH=3.5m", ".subckt MICCH HOT COLD SHIELD params: IPH=3.5m ACM=1")
    sigc = ["vm(P48V)", "vm(L_P48)", "vm(L_OUT_H,L_OUT_C)", "vm(L_OUT_H)", "vm(L_OUT_C)"]
    a = run("T3a_supply_ac", body, sigc)
    f = a[:, 0]
    h48, hp, hd, hh, hc = a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5]
    hcm = (hh + hc) / 2
    # (b) マイク信号 → 出力 (差動)
    body2 = build.build(vboost_src="DC 51.5", extra=common)
    b = run("T3b_signal_ac", body2, ["vm(L_OUT_H,L_OUT_C)", "vp(L_OUT_H,L_OUT_C)"])
    fs, gs = b[:, 0], b[:, 1]
    # T2 のスペクトルと組み合わせて、マイク出力に現れるスイッチング成分を求める
    spec = np.load(os.path.join(WORK, "T2_spec.npy")) if os.path.exists(os.path.join(WORK, "T2_spec.npy")) else None

    def at(x, fr):
        return np.interp(np.log10(fr), np.log10(f), x)
    rows = [
        ("+48V への伝達 @1kHz", f"{20 * np.log10(at(h48, 1e3)):.0f} dB", "リップルフィルター + RC"),
        ("+48V への伝達 @153kHz", f"{20 * np.log10(at(h48, FSW)):.0f} dB", ""),
        ("マイク出力 差動への伝達 @1kHz", f"{20 * np.log10(at(hd, 1e3)):.0f} dB", "0.1%抵抗の誤差と電解±20%を含む"),
        ("マイク出力 差動への伝達 @153kHz", f"{20 * np.log10(at(hd, FSW)):.0f} dB", ""),
        ("マイク出力 同相への伝達 @1kHz", f"{20 * np.log10(at(hcm, 1e3)):.0f} dB", "録音機側のCMRRでさらに除去される"),
    ]
    if spec is not None:
        fsp, Sb, _ = spec
        sel = fsp > 1e3
        def via(h):
            return Sb[sel] * np.interp(np.log10(fsp[sel]), np.log10(f), h)
        rows.append(("+48V に残るスイッチング成分 (最大)", f"{via(h48).max() * 1e9:.0f} nV", "T2のスペクトル × 伝達特性"))
        rows.append(("L_P48 (マイクへの給電点) に残るスイッチング成分", f"{via(hp).max() * 1e9:.1f} nV", ""))
        rows.append(("マイク出力 差動に出るスイッチング成分 (最大)", f"{via(hd).max():.1e} V",
                     "一般的なコンデンサーマイクの自己雑音 (数µV) より桁違いに小さい"))
        rows.append(("マイク出力 同相に出るスイッチング成分 (最大)", f"{via(hcm).max():.1e} V", ""))
        aud = (fsp > 20) & (fsp < 20e3)
        if aud.any():
            ha = Sb[aud] * np.interp(np.log10(fsp[aud]), np.log10(f), hd)
            rows.append(("マイク出力 差動 可聴帯域の電源由来成分 (最大)", f"{ha.max():.1e} V", ""))
    rows.append(("マイク信号の通過 @20Hz / 1kHz / 20kHz",
                 " / ".join(f"{20 * np.log10(np.interp(x, fs, gs)):.2f} dB" for x in (20, 1e3, 20e3)),
                 "録音機入力 1.2kΩ×2 のとき"))
    note("T3 周波数特性 (AC解析)", rows)
    fig, ax = plt.subplots(2, 1, figsize=(9, 7))
    ax[0].semilogx(f, 20 * np.log10(h48), label="+48V")
    ax[0].semilogx(f, 20 * np.log10(hp), label="L_P48 (チャンネル給電点)")
    ax[0].semilogx(f, 20 * np.log10(hcm), label="マイク出力 同相")
    ax[0].semilogx(f, 20 * np.log10(hd), label="マイク出力 差動 (信号に混ざる成分)")
    ax[0].axvline(FSW, color="r", ls="--", lw=0.8, label="スイッチング 153kHz")
    ax[0].axvspan(20, 20e3, color="g", alpha=0.08)
    ax[0].set_ylabel("昇圧出力からの伝達 [dB]"); ax[0].legend(fontsize=8)
    ax[0].set_title("T3 電源ノイズの伝達 (昇圧出力 VBOOST → 各部)")
    ax[1].semilogx(fs, 20 * np.log10(gs))
    ax[1].set_ylim(-3, 1); ax[1].set_xlim(1, 1e6)
    ax[1].set_title("T3 マイク信号の通過特性 (マイク → 録音機 1.2kΩ×2)")
    ax[1].set_xlabel("周波数 [Hz]"); ax[1].set_ylabel("dB")
    fig.tight_layout(); fig.savefig(os.path.join(OUTD, "T3_周波数特性.png")); plt.close(fig)


# ------------------------------------------------------------------ T4
def t4():
    src = "PWL(0 0 0.1 0 0.12 51.5 10 51.5 10.5 0)"
    out = {}
    for case, rin in (("録音機 未接続", 1e6), ("録音機 接続 (各線6.8kΩ)", 6.8e3)):
        extra = "\n.options reltol=1e-4\n.tran 1m 14 0 2m\n"
        body = build.build(vboost_src=src, rin=rin, extra=extra)
        sig = ["v(VBOOST)", "v(P48V)", "v(L_OUT_H)", "v(L_OUT_C)", "v(L_IN_H)", "i(VBOOST)"]
        a = run("T4_onoff_" + ("open" if rin > 1e5 else "6k8"), body, sig)
        out[case] = a
    rows = []
    for case, a in out.items():
        t, vb, v48, oh, oc, ih, ib = a.T
        t10 = t[np.argmax(v48 > 0.1 * 48.2)]
        t90 = t[np.argmax(v48 > 0.9 * 48.2)]
        on = t < 10
        rows += [
            (f"[{case}] +48V 立ち上がり 10→90%", f"{(t90 - t10):.2f} 秒", ""),
            (f"[{case}] 電源ON時 出力HOTの最大", f"{oh[on].max():.1f} V",
             "TVSが動作して約15Vに制限" if oh[on].max() > 14 else "TVSの動作電圧(約15V)未満"),
            (f"[{case}] 電源OFF時 出力HOTの最小", f"{oh[~on].min():.1f} V",
             "TVSが動作して約-15Vに制限" if oh[~on].min() < -14 else ""),
            (f"[{case}] 出力が±1V以内に戻るまで (ON後)",
             f"{(t[on][np.where(np.abs(oh[on]) > 1)[0][-1]] - 0.1) if (np.abs(oh[on]) > 1).any() else 0:.1f} 秒", ""),
        ]
    note("T4 電源ON/OFF時の過渡 (0.1秒で電源ON、10秒で電源OFF)", rows)
    fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for i, (case, a) in enumerate(out.items()):
        t, vb, v48, oh, oc, ih, ib = a.T
        if i == 0:
            ax[0].plot(t, vb, lw=1, label="VBOOST (昇圧出力, 理想電源で模擬)")
            ax[0].plot(t, v48, lw=1, label="+48V")
            ax[0].plot(t, ih, lw=1, label="L_IN_H (マイクHOT側)")
        ax[1].plot(t, oh, lw=1, label=f"出力 HOT ({case})")
    ax[0].set_ylabel("V"); ax[0].legend(); ax[0].set_title("T4 電源ON/OFF時の過渡")
    ax[1].axhline(15, color="r", ls="--", lw=0.8); ax[1].axhline(-15, color="r", ls="--", lw=0.8, label="TVS 約±15V")
    ax[1].set_ylabel("V"); ax[1].set_xlabel("時間 [秒]"); ax[1].legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUTD, "T4_電源ONOFF.png")); plt.close(fig)


# ------------------------------------------------------------------ T5
def t5():
    """入力電圧 12 / 18 / 24V の比較 (外部リニア電源の電圧選び)"""
    rows, curves = [], {}
    for vin in (12, 18, 24):
        extra = """
Istep VBOOST 0 PWL(0 0 30m 0 30.001m 16m 35m 16m 35.001m 0)
.options reltol=1e-4 abstol=1n vntol=10u itl4=200
.tran 20n 40m 0 20n
"""
        a = run(f"T5_vin{vin}", build.build(adapter=f"DC {vin}", extra=extra),
                ["v(VBOOST)", "i(LL1)", "i(Vadapter)", "v(SW)", "v(GATE)"])
        t, vb, il, iin, vsw, vg = a.T
        iin = -iin
        ss = (t > 25e-3) & (t < 29.9e-3)
        reg = np.median(vb[ss])
        w = (t > 30e-3) & (t < 34.9e-3)
        post = np.median(vb[(t > 33e-3) & (t < 34.9e-3)])
        idx = np.where(w & (np.abs(vb - post) > 0.1))[0]
        pin = np.mean(iin[ss]) * vin
        curves[vin] = (t, vb)
        rows.append((f"入力 {vin}V", f"平均 {np.mean(iin[ss]) * 1e3:.0f} mA ({pin:.2f} W) / 起動 {t[np.argmax(vb > 0.95 * reg)] * 1e3:.0f} ms / "
                     f"整定 {(t[idx[-1]] - 30e-3) * 1e3 if len(idx) else 0:.1f} ms / ゲート最大 {vg.max():.1f} V / "
                     f"インダクター最大 {il.max():.2f} A",
                     "ゲートが IRFU120N の定格 ±20V を超える" if vg.max() > 20 else "OK"))
    note("T5 入力電圧の比較 (12 / 18 / 24V、負荷急変つき)", rows)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for vin, (t, vb) in curves.items():
        ax.plot(t * 1e3, vb, lw=0.7, label=f"入力 {vin}V")
    ax.set_xlabel("時間 [ms]"); ax.set_ylabel("VBOOST [V]"); ax.legend(); ax.set_title("T5 入力電圧ごとの起動と負荷急変")
    fig.tight_layout(); fig.savefig(os.path.join(OUTD, "T5_入力電圧比較.png")); plt.close(fig)


# ------------------------------------------------------------------ T6
def t6():
    """電源は入れたまま、PHANTOM スイッチで ON/OFF (0.5秒で ON、8秒で OFF)"""
    out = {}
    for case, rin in (("録音機 未接続", 1e6), ("録音機 接続 (各線6.8kΩ)", 6.8e3)):
        body = build.build(vboost_src="DC 51.5", rin=rin, phantom="PWL(0 0 0.5 0 0.501 1 8 1 8.001 0)",
                           extra="\n.options reltol=1e-4\n.tran 1m 14 0 2m\n")
        out[case] = run("T6_phantom_" + ("open" if rin > 1e5 else "6k8"), body,
                        ["v(P48V)", "v(L_OUT_H)", "v(L_IN_H)", "v(VBASE)"])
    rows = []
    for case, a in out.items():
        t, v48, oh, ih, vb = a.T
        on = (t > 0.5) & (t < 8)
        off = t >= 8
        t10 = t[on][np.argmax(v48[on] > 0.1 * 48.2)] - 0.5
        t90 = t[on][np.argmax(v48[on] > 0.9 * 48.2)] - 0.5
        f90 = t[off][np.argmax(v48[off] < 0.9 * 48.2)] - 8
        f10 = t[off][np.argmax(v48[off] < 0.1 * 48.2)] - 8
        rows += [
            (f"[{case}] ON: +48V 立ち上がり 10→90%", f"{t90 - t10:.2f} 秒", "スイッチONからの時間"),
            (f"[{case}] OFF: +48V 立ち下がり 90→10%", f"{f10 - f90:.2f} 秒", ""),
            (f"[{case}] ON時 出力HOTの最大", f"{oh[on].max():.1f} V", "TVSが動作" if oh[on].max() > 14 else "TVSの動作電圧(約15V)未満"),
            (f"[{case}] OFF時 出力HOTの最小", f"{oh[off].min():.1f} V", "TVSが動作" if oh[off].min() < -14 else "TVSの動作電圧(約15V)未満"),
        ]
    note("T6 PHANTOM スイッチの ON/OFF (電源は入れたまま、0.5秒で ON、8秒で OFF)", rows)
    fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for i, (case, a) in enumerate(out.items()):
        t, v48, oh, ih, vb = a.T
        if i == 0:
            ax[0].plot(t, v48, lw=1, label="+48V")
            ax[0].plot(t, ih, lw=1, label="L_IN_H (マイクHOT側)")
        ax[1].plot(t, oh, lw=1, label=f"出力 HOT ({case})")
    ax[0].axvline(0.5, color="g", ls=":", lw=0.8); ax[0].axvline(8, color="r", ls=":", lw=0.8)
    ax[0].set_ylabel("V"); ax[0].legend(); ax[0].set_title("T6 PHANTOM スイッチ ON (0.5秒) / OFF (8秒)")
    ax[1].axhline(15, color="r", ls="--", lw=0.8); ax[1].axhline(-15, color="r", ls="--", lw=0.8, label="TVS 約±15V")
    ax[1].set_ylabel("V"); ax[1].set_xlabel("時間 [秒]"); ax[1].legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUTD, "T6_PHANTOMスイッチ.png")); plt.close(fig)


def write_md():
    lines = ["# シミュレーション結果", "",
             "ngspice-47 による。回路は tools/gen_schematic.py の部品定義から自動生成 (tools/sim/build.py)。", "",
             "部品モデルはデータシートからの概算 (UC3843 は動作モデル、MOSFET/ダイオード/トランジスタは近似パラメーター)。",
             "電解コンデンサはESRを、積層セラミックはDCバイアスによる容量低下を見込んでいる。", ""]
    for title, rows in RESULTS:
        lines += ["## " + title, "", "| 項目 | 結果 | 備考 |", "|---|---|---|"]
        lines += [f"| {k} | {v} | {j} |" for k, v, j in rows]
        lines.append("")
    open(os.path.join(OUTD, "結果.md"), "w").write("\n".join(lines) + "\n")
    sys.path.insert(0, os.path.dirname(HERE))
    import md2html          # 同じ内容の HTML 版を作る
    md2html.refresh()


if __name__ == "__main__":
    todo = sys.argv[1:] or ["T1", "T2", "T3", "T4", "T5", "T6"]
    for name in todo:
        globals()[name.lower()]()
    write_md()
