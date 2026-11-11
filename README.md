# jlc-hardware-project

小型の電子機器を **要件 → 部品選定 → KiCad 回路図 → ngspice シミュレーション → 板金筐体 → 基板 → 発注データ → 資料** まで
一貫して設計するための [Claude Code](https://code.claude.com/docs/en/overview) 用 Skill です。

- 基板は JLCPCB (SMD 実装は基本部品のみ)、筐体は JLCCNC の板金で作る前提
- 手はんだ部品は国内通販 (秋月電子通商・千石電商・Digi-Key Japan など) で、購入リンク付きのリストを作る
- 2ch P48 ファンタム電源の実例で一通り動いた雛形スクリプト一式 (`assets/template/`) を同梱

A Claude Code skill for end-to-end small hardware projects: KiCad schematic and PCB generated from a Python part list,
ngspice verification, sheet-metal enclosure (build123d), JLCPCB/JLCCNC fabrication files, and HTML documentation.
Documentation and comments are in Japanese.

## 必ず作るもの

1. KiCad の回路図 (1 枚にすべてつながった形、PDF/PNG 付き)
2. 基板の 3D 画像 (真上・斜め)
3. ngspice のシミュレーション (起動・リップル・周波数特性・電源 ON/OFF、定格の確認)
4. 購入リンク付きの部品リスト (送料を抑えるよう店をまとめる)
5. 原寸チェック用の基板図 (A4・1:1) と、設計の根拠 (計算とシミュレーションの対比)

## おすすめの使い方: VS Code + Claude Code 拡張機能

この Skill は **VS Code (無料のエディター) の Claude Code 拡張機能** で使うのがおすすめです。

### ブラウザやデスクトップアプリのチャットと比べたメリット

この Skill は 1 つの機器で数十〜数百のファイル (回路図・基板・ガーバー・3D 画像・PDF・HTML 資料・購入リストなど) を作ります。

| | チャット (ブラウザ / デスクトップアプリ) | VS Code + Claude Code |
|---|---|---|
| できたファイル | 1 つずつダウンロードして開く | **自分のフォルダに直接できる**。左のエクスプローラーにすぐ並ぶ |
| 確認 | ダウンロードした場所を探して開く | 画像はそのまま VS Code で表示。HTML・PDF・KiCad はクリックや右クリックの「Finder で表示」/「エクスプローラーで表示」 ですぐ開ける |
| 修正 | 直したらまたダウンロード | 同じフォルダのファイルが上書きされるので、開き直すだけ |
| KiCad・ngspice・Python | 使えない (環境が無い) | **自分のパソコンのソフトをそのまま使う**。回路図の照合・DRC・シミュレーション・ガーバー出力まで自動で行う |
| 変更の確認 | — | 変更前後の差分が並べて表示され、変更ごとに採用・却下を選べる |
| 指示の出し方 | ファイルの中身を貼り付ける | `@ファイル名` でファイルを指定、選択した部分もそのまま伝わる |
| 管理 | 会話ごとにばらばら | 1 機器 = 1 フォルダ。Git で履歴も残せる |

あると便利な VS Code 拡張機能 (どちらも無料・任意): **Live Preview** (Microsoft。HTML 資料を VS Code 内で表示)、**vscode-pdf** (PDF を VS Code 内で表示)。

### 必要なもの

- Claude の有料プラン (Pro / Max / Team / Enterprise) または Claude Console のアカウント。無料プランでは Claude Code を使えません
- パソコン: macOS、または Windows 10 (1809 以降) / 11

### 導入手順 (かんたん: コマンド 1 行でまとめて入れる)

設計に必要なソフト (KiCad・ngspice・Python・uv・Git)、VS Code と Claude Code 拡張機能、この Skill、
CAD 用の Python 環境を **まとめて入れるスクリプト** を用意しています。すでに入っているものは飛ばすので、何度実行しても大丈夫です。
全部で 10〜20 分ほどかかります (通信速度によります)。

#### macOS

1. 「ターミナル」を開く (Finder →「アプリケーション」→「ユーティリティ」→「ターミナル」、または `Cmd + Space` で「ターミナル」と入力)
2. 次の 1 行を貼り付けて Enter

   ```sh
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/AsteroidApp-hub/jlc-hardware-project/main/setup/install_mac.sh)"
   ```

3. 途中で Mac のパスワードを聞かれたら入力して Enter (入力中の文字は表示されません)
4. 最後に「確認」の一覧がすべて `[OK]` になれば完了

Homebrew (Mac 用のソフト管理ツール) が無ければ、最初に自動で入ります。

#### Windows

1. スタートメニューで「PowerShell」と入力して **Windows PowerShell** を開く
2. 次の 1 行を貼り付けて Enter

   ```powershell
   irm https://raw.githubusercontent.com/AsteroidApp-hub/jlc-hardware-project/main/setup/install_windows.ps1 | iex
   ```

3. 途中で「このアプリがデバイスに変更を加えることを許可しますか?」と出たら **「はい」**
4. 最後に「確認」の一覧がすべて `[OK]` になれば完了。PowerShell と VS Code は一度閉じて開き直す

winget (Windows 標準のソフト管理ツール) を使います。「winget が見つからない」と出たら、Microsoft Store で「アプリ インストーラー」を入れて (更新して) からもう一度実行してください。
ngspice は winget に無いため、公式サイトの Windows 版を `%LOCALAPPDATA%\ngspice` に入れます。

#### 入れたあと

1. VS Code を開き、左のバーの Claude のアイコン (または `Cmd + Esc` / `Ctrl + Esc`) から Claude にサインイン
2. 状態はいつでも次のコマンドで確認できます (VS Code の Claude に「環境を確認して」と頼んでも同じです)

   ```sh
   python3 ~/.claude/skills/jlc-hardware-project/setup/check.py          # macOS
   py -3 "$env:USERPROFILE\.claude\skills\jlc-hardware-project\setup\check.py"   # Windows (PowerShell)
   ```

スクリプトの中身は [`setup/`](setup/) で確認できます。オプション: VS Code を入れない場合は実行前に
`export SKIP_VSCODE=1` (macOS) / `$env:SKIP_VSCODE = "1"` (Windows)、内容の表示だけなら `DRY_RUN=1`。

<details>
<summary>手動で入れる場合 (スクリプトを使わない)</summary>


#### macOS

1. **VS Code** を https://code.visualstudio.com/ からインストール (1.94 以降)。日本語表示にするなら拡張機能「Japanese Language Pack」も
2. VS Code の拡張機能 (`Cmd + Shift + X`) で **「Claude Code」 (発行元 Anthropic)** を検索してインストール。Claude のパネルを開いてサインイン
3. **この Skill を入れる**: VS Code のターミナル (メニュー「ターミナル」→「新しいターミナル」、英語表示では Terminal → New Terminal) で

   ```sh
   git clone https://github.com/AsteroidApp-hub/jlc-hardware-project.git ~/.claude/skills/jlc-hardware-project
   ```

   (git が無いと言われたら、表示に従って「コマンドライン・デベロッパツール」をインストールしてからもう一度)
4. **設計用のソフト** を入れる
   - KiCad 9 以降: https://www.kicad.org/download/
   - ngspice: [Homebrew](https://brew.sh/) で `brew install ngspice`
   - uv (Python の環境づくり): `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - `kicad-cli` を使えるようにする: `echo 'export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"' >> ~/.zshrc` を実行してターミナルを開き直す

#### Windows

1. **VS Code** を https://code.visualstudio.com/ からインストール (1.94 以降)。日本語表示にするなら拡張機能「Japanese Language Pack」も
2. **Git for Windows** を https://git-scm.com/downloads/win からインストール (設定はそのままで可)。
   Skill の取得と、Claude Code がコマンドを実行するのに使います
3. VS Code の拡張機能 (`Ctrl + Shift + X`) で **「Claude Code」 (発行元 Anthropic)** を検索してインストール。Claude のパネルを開いてサインイン
4. **この Skill を入れる**: VS Code のターミナル (PowerShell) で

   ```powershell
   git clone https://github.com/AsteroidApp-hub/jlc-hardware-project.git "$env:USERPROFILE\.claude\skills\jlc-hardware-project"
   ```

5. **設計用のソフト** を入れる
   - KiCad 9 以降: https://www.kicad.org/download/
   - Python 3: https://www.python.org/downloads/ (インストール画面で **「Add python.exe to PATH」にチェック**)
   - ngspice: https://ngspice.sourceforge.io/download.html から Windows 64bit 版を取得して展開し (7-Zip などで)、展開した `Spice64\bin` フォルダを環境変数 PATH に追加
   - uv: PowerShell で `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - `kicad-cli` を使えるようにする: `C:\Program Files\KiCad\<版>\bin` を環境変数 PATH に追加
   - (任意) PDF を画像にする poppler (`pdftoppm`)。無くても動くが、基板レイアウト画像の切り抜きなど一部が簡略になる

PATH の追加が難しければ、**Claude にそのまま頼めます** (例: 「KiCad と ngspice を使えるように PATH を設定して」)。

#### 確認 (手動)

VS Code を開き直し、Claude のパネルで次のように話しかけます。

> jlc-hardware-project の Skill で、設計に必要なソフト (KiCad・ngspice・Python・uv) が使えるか確認して

足りないものがあれば、Claude が入れ方を案内します (筐体や図を作るための Python の仮想環境もこのとき作れます)。

</details>

### 使い方

1. 機器ごとに空のフォルダを作り、VS Code で開く (メニュー「ファイル」→「フォルダーを開く」、英語表示では File → Open Folder)
2. Claude のパネル (`Cmd + Esc` / `Ctrl + Esc`) で、作りたいものを話す。例:

   > マイク用の 2ch ファンタム電源を作りたいです。基板は JLCPCB、筐体は JLCCNC の板金で。部品は国内通販で買いたいです

3. Claude が要件を質問し、部品選定 → 回路図 → シミュレーション → 筐体 → 基板 → 発注データ → 資料 の順に進めます。
   できた資料は、フォルダの **`はじめにお読みください.html`** から全部たどれます

ターミナルで Claude Code を使う場合も同じ Skill が使われます (CLI の導入は [公式の手順](https://code.claude.com/docs/en/setup))。

### 動作確認の状況

- macOS (KiCad 10・ngspice 47): 回路図から発注データ・資料まで一通り動作を確認。一括インストールスクリプトも実機で確認済み
- Windows: 一括インストールスクリプト・KiCad の場所の検出・Python や ngspice のコマンド名の違い・日本語フォントに対応済みですが、
  Windows の実機での通し確認はまだです。うまく動かない場合は Issue で教えてください

## 必要なソフト (まとめ)

| ソフト | 用途 |
|---|---|
| KiCad 9 以降 (`kicad-cli`、同梱の Python) | 回路図・基板・DRC・3D 画像・ガーバー |
| ngspice | シミュレーション |
| Python 3 | ジェネレーター (回路図・購入リスト・資料は標準ライブラリのみ) |
| Python 3.12 の仮想環境 (`build123d ezdxf matplotlib numpy pyvista`、uv で作る) | 筐体の 3D・図面、シミュレーションのグラフ、製作者向け資料 |

KiCad が標準の場所に無い場合は、環境変数 `KICAD_SHARE` / `KICAD_PYTHON` で指定できます (`python tools/kicad_env.py` で検出結果を表示)。
ngspice は `NGSPICE`、Python は `PYTHON` でも指定できます。

## 構成

| パス | 内容 |
|---|---|
| `SKILL.md` | Skill 本体 (進め方・必須の成果物・工程・完了の目安) |
| `references/` | 工程ごとの詳しい手順と落とし穴 (部品選定、KiCad 生成、シミュレーション、筐体、発注、資料、実例) |
| `scripts/jlc_basic_parts.py` | JLCPCB 基本部品の検索・BOM のチェック |
| `assets/template/` | 雛形 (2ch P48 ファンタム電源)。`assets/template/README.md` に書き換える場所の説明 |

## 注意

- 価格・在庫・送料・JLCPCB/JLCCNC の条件は 2026 年 11 月時点の調査に基づきます。使う時点で確認してください。
- メーカーの 3D モデル (Neutrik の STEP など) は再配布できないため含めていません。ダウンロード先の URL のみ記載しています。
- 雛形の回路は実例であり、実機での動作を保証するものではありません。高電圧 (48V 級) を扱うので、組立・試験は注意して行ってください。
- JLCPCB、JLCCNC、KiCad、Digi-Key、各部品メーカー名は各社の商標です。この Skill は各社と関係ありません。

## ライセンス

MIT License (`LICENSE`)
