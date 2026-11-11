#!/bin/bash
# jlc-hardware-project: 設計に必要なソフトを macOS にまとめて入れる
#
# 使い方 (ターミナルに貼り付けて Enter):
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/AsteroidApp-hub/jlc-hardware-project/main/setup/install_mac.sh)"
#   (「curl ... | bash」の形だと Homebrew の導入時にパスワードを入力できないので、この形で実行する)
#
# 入るもの: Homebrew (無ければ) / KiCad / ngspice / uv / Git / VS Code + Claude Code 拡張機能 /
#           この Skill (~/.claude/skills/jlc-hardware-project) / CAD 用の Python 仮想環境 (~/.jlc-hardware-project/venv)
# すでに入っているものは飛ばす。何度実行してもよい。
#
# 環境変数:
#   SKIP_VSCODE=1  VS Code と拡張機能を入れない
#   DRY_RUN=1      実行せず、行う内容だけ表示する
set -euo pipefail

REPO="https://github.com/AsteroidApp-hub/jlc-hardware-project.git"
SKILL_DIR="$HOME/.claude/skills/jlc-hardware-project"
VENV="${JLC_VENV:-$HOME/.jlc-hardware-project/venv}"
PKGS="build123d ezdxf matplotlib numpy pyvista"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
run()  { echo "+ $*"; [ "${DRY_RUN:-0}" = 1 ] || "$@"; }
have() { command -v "$1" >/dev/null 2>&1; }

[ "$(uname)" = "Darwin" ] || { echo "macOS 用のスクリプトです"; exit 1; }

say "1/7 Homebrew (ソフトをまとめて入れる道具)"
if ! have brew; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done
fi
if ! have brew; then
  echo "Homebrew を入れます。途中で Mac のパスワードを聞かれたら入力してください (入力中の文字は表示されません)。"
  run /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$b" ]; then
      eval "$("$b" shellenv)"
      grep -q 'brew shellenv' "$HOME/.zprofile" 2>/dev/null || echo "eval \"\$($b shellenv)\"" >> "$HOME/.zprofile"
    fi
  done
else
  echo "入っています: $(brew --version | head -1)"
fi

say "2/7 KiCad (回路図・基板)"
if [ -d "/Applications/KiCad/KiCad.app" ]; then echo "入っています"; else run brew install --cask kicad; fi
if ! have kicad-cli && [ -x /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli ]; then
  # Homebrew 以外で入れた KiCad: kicad-cli を使えるようにする
  LINE='export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"'
  grep -qF "$LINE" "$HOME/.zshrc" 2>/dev/null || { echo "+ ~/.zshrc に kicad-cli の場所を追加"; [ "${DRY_RUN:-0}" = 1 ] || echo "$LINE" >> "$HOME/.zshrc"; }
  export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"
fi

say "3/7 ngspice (回路シミュレーション)・uv (Python の環境づくり)・Git"
for f in ngspice uv git; do
  if have "$f"; then echo "入っています: $f"; else run brew install "$f"; fi
done

say "4/7 VS Code と Claude Code 拡張機能"
CODE="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
if [ "${SKIP_VSCODE:-0}" = 1 ]; then
  echo "飛ばします (SKIP_VSCODE=1)"
else
  [ -d "/Applications/Visual Studio Code.app" ] && echo "VS Code は入っています" || run brew install --cask visual-studio-code
  if [ -x "$CODE" ] || [ "${DRY_RUN:-0}" = 1 ]; then
    run "$CODE" --install-extension anthropic.claude-code --force
  fi
fi

say "5/7 この Skill"
if [ -d "$SKILL_DIR/.git" ]; then
  run git -C "$SKILL_DIR" pull --ff-only
elif [ -e "$SKILL_DIR" ]; then
  echo "$SKILL_DIR はすでにあります (Git 管理ではないのでそのままにします)"
else
  run mkdir -p "$(dirname "$SKILL_DIR")"
  run git clone "$REPO" "$SKILL_DIR"
fi

say "6/7 CAD 用の Python 仮想環境 (筐体の 3D・図・グラフ用。数分かかります)"
if [ ! -x "$VENV/bin/python" ]; then
  run mkdir -p "$(dirname "$VENV")"
  run uv venv -p 3.12 "$VENV"
fi
run uv pip install --python "$VENV/bin/python" $PKGS

say "7/7 確認"
if [ "${DRY_RUN:-0}" = 1 ]; then
  echo "+ python3 $SKILL_DIR/setup/check.py"
else
  python3 "$SKILL_DIR/setup/check.py" || true
fi

cat <<'EOF'

完了しました。
次は VS Code を開き、左のバーの Claude のアイコン (または Cmd + Esc) から Claude にサインインしてください。
機器ごとに空のフォルダを作って VS Code で開き、作りたいものを Claude に話しかければ始められます。
(新しく入れたソフトを使うため、開いているターミナルや VS Code は一度閉じて開き直してください)
EOF
