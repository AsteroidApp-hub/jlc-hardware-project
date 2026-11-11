#!/usr/bin/env python3
"""設計に必要なソフトがそろっているか確認する (macOS / Windows / Linux、標準ライブラリのみ)。

使い方: python3 setup/check.py      (Windows は python setup\\check.py)
仮想環境の場所は環境変数 JLC_VENV で変えられる (既定: ~/.jlc-hardware-project/venv)。
"""
import glob, os, platform, shutil, subprocess, sys

WIN = platform.system() == "Windows"
HOME = os.path.expanduser("~")
VENV = os.environ.get("JLC_VENV") or os.path.join(HOME, ".jlc-hardware-project", "venv")
VPY = os.path.join(VENV, "Scripts", "python.exe") if WIN else os.path.join(VENV, "bin", "python")
SKILL = os.path.join(HOME, ".claude", "skills", "jlc-hardware-project", "SKILL.md")
ok_all = True


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def item(name, ok, detail, fix=""):
    global ok_all
    ok_all &= ok
    print(f"[{'OK' if ok else 'NG'}] {name}: {detail}")
    if not ok and fix:
        print(f"      → {fix}")


def first_line(s):
    return s.splitlines()[0] if s else ""


def find_kicad_cli():
    p = shutil.which("kicad-cli")
    if p:
        return p
    for g in ([r"C:\Program Files\KiCad\*\bin\kicad-cli.exe"] if WIN else
              ["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"]):
        m = sorted(glob.glob(g), reverse=True)
        if m:
            return m[0]
    return None


def main():
    print(f"=== jlc-hardware-project 環境確認 ({platform.system()} {platform.release()}) ===")
    item("Skill", os.path.exists(SKILL), SKILL if os.path.exists(SKILL) else "見つからない",
         "setup のインストールスクリプトを実行するか、git clone で ~/.claude/skills/jlc-hardware-project に置く")

    cli = find_kicad_cli()
    if cli:
        rc, out = run([cli, "version"])
        on_path = shutil.which("kicad-cli") is not None
        item("KiCad (kicad-cli)", rc == 0 and on_path, f"{first_line(out)}  ({cli})",
             "" if on_path else f"PATH に {os.path.dirname(cli)} を追加する (インストールスクリプトが自動で行う)")
    else:
        item("KiCad (kicad-cli)", False, "見つからない", "KiCad 9 以降をインストール: https://www.kicad.org/download/")

    sp = shutil.which("ngspice_con") or shutil.which("ngspice")
    if sp:
        rc, out = run([sp, "-v"])
        ver = next((l for l in out.splitlines() if "ngspice" in l.lower()), first_line(out))
        item("ngspice", rc == 0, f"{ver.strip()}  ({sp})")
    else:
        item("ngspice", False, "見つからない",
             "macOS: brew install ngspice / Windows: インストールスクリプトが公式版を入れて PATH に追加する")

    item("Python", sys.version_info >= (3, 9), f"{platform.python_version()} ({sys.executable})", "Python 3.9 以降を入れる")

    uv = shutil.which("uv")
    item("uv", bool(uv), uv or "見つからない", "https://docs.astral.sh/uv/ の手順で入れる")

    if os.path.exists(VPY):
        rc, out = run([VPY, "-c", "import build123d, ezdxf, matplotlib, numpy, pyvista; print('ok')"])
        item("CAD 用の仮想環境", rc == 0 and out.endswith("ok"), VENV if rc == 0 else first_line(out.splitlines()[-1] if out else ""),
             f'uv pip install --python "{VPY}" build123d ezdxf matplotlib numpy pyvista')
    else:
        item("CAD 用の仮想環境", False, f"{VENV} が無い",
             f'uv venv -p 3.12 "{VENV}" の後、uv pip install --python "{VPY}" build123d ezdxf matplotlib numpy pyvista')

    git = shutil.which("git")
    item("Git", bool(git), git or "見つからない", "Windows: https://git-scm.com/downloads/win / macOS: xcode-select --install")

    print()
    if ok_all:
        print("すべてそろっています。VS Code で空のフォルダを開き、Claude に作りたい機器を話しかけてください。")
    else:
        print("NG の項目があります。→ の手順で直すか、VS Code の Claude に「この結果を見て直して」と頼んでください。")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
