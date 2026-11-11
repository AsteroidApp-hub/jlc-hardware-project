#!/usr/bin/env python3
"""KiCad のインストール場所を探す (macOS / Linux / Windows)。

環境変数で上書きできる:
  KICAD_SHARE   … symbols/ と footprints/ と 3dmodels/ がある共有フォルダ
  KICAD_PYTHON  … pcbnew モジュールが使える Python (KiCad 同梱 Python)
`python3 tools/kicad_env.py` で検出結果を表示する。
"""
import glob, os, shutil, sys


def _first(paths):
    for p in paths:
        for m in sorted(glob.glob(p), reverse=True):
            if os.path.exists(m):
                return m
    return None


def kicad_share():
    if os.environ.get("KICAD_SHARE"):
        return os.environ["KICAD_SHARE"]
    found = _first([
        "/Applications/KiCad/KiCad.app/Contents/SharedSupport",          # macOS
        "/usr/share/kicad", "/usr/local/share/kicad",                    # Linux
        r"C:\Program Files\KiCad\*\share\kicad",                         # Windows
    ])
    if not found:
        raise SystemExit("KiCad の共有フォルダが見つからない。環境変数 KICAD_SHARE を設定してください")
    return found


def kicad_python():
    if os.environ.get("KICAD_PYTHON"):
        return os.environ["KICAD_PYTHON"]
    found = _first([
        "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/*/bin/python3",  # macOS
        r"C:\Program Files\KiCad\*\bin\python.exe",                                                  # Windows
    ])
    if found:
        return found
    # Linux: システムの python3 で pcbnew が import できることが多い
    return shutil.which("python3") or sys.executable


if __name__ == "__main__":
    print("KICAD_SHARE  =", kicad_share())
    print("KICAD_PYTHON =", kicad_python())
