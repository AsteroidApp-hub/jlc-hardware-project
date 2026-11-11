#!/usr/bin/env python3
"""KiCadが書き出したネットリストと expected_nets.txt (設計意図) を照合する。
使い方: kicad-cli sch export netlist --format kicadsexpr -o out.net <PROJECT>.kicad_sch
        python3 tools/check_netlist.py out.net kicad/expected_nets.txt
接続(どのピン同士がつながるか)とネット名の両方を比べる。"""
import re, sys
t = open(sys.argv[1]).read()
t = t[t.index("(nets"):]
got = {}
for chunk in re.split(r"\(net\s*\(code", t)[1:]:
    name = re.search(r'\(name "([^"]*)"\)', chunk).group(1).lstrip("/")
    got[name] = frozenset(f"{r}.{p}" for r, p in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', chunk))
exp = {}
for line in open(sys.argv[2]):
    n, v = line.rstrip("\n").split(": ", 1)
    exp[n] = frozenset(v.split())
gotsets = {v: k for k, v in got.items()}
bad = 0
for n, pins in sorted(exp.items()):
    if pins in gotsets:
        if gotsets[pins] != n:
            print("NAME", n, "is called", gotsets[pins])
            bad += 1
        continue
    bad += 1
    hit = {k: sorted(v & pins) for k, v in got.items() if v & pins}
    print("MISMATCH", n, "expected", sorted(pins))
    for k, v in hit.items():
        print("     in sch net %-22s: %s%s" % (k, v, "  +extra " + str(sorted(got[k] - pins)) if got[k] - pins else ""))
    lost = pins - set().union(*got.values())
    if lost:
        print("     unconnected:", sorted(lost))
expsets = set(exp.values())
for k, v in sorted(got.items()):
    # 期待に無いネット (2ピン以上)。未接続ピン用の "unconnected-..." は除く
    if v not in expsets and len(v) > 1 and not k.startswith(("unconnected-", "Net-(")):
        print("EXTRA", k, sorted(v))
        bad += 1
    elif v not in expsets and len(v) > 1:
        print("EXTRA (無名ネット = 意図しない接続の可能性)", k, sorted(v))
        bad += 1
print(f"exported {len(got)} nets, expected {len(exp)}, problems {bad}")
sys.exit(1 if bad else 0)
