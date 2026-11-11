# jlc-hardware-project: 設計に必要なソフトを Windows にまとめて入れる
#
# 使い方 (スタートメニューで「PowerShell」を開き、貼り付けて Enter):
#   irm https://raw.githubusercontent.com/AsteroidApp-hub/jlc-hardware-project/main/setup/install_windows.ps1 | iex
#
# 入るもの: Git / KiCad / Python 3.12 / uv / VS Code + Claude Code 拡張機能 (winget で) /
#           ngspice (公式サイトの Windows 版) / この Skill (%USERPROFILE%\.claude\skills\jlc-hardware-project) /
#           CAD 用の Python 仮想環境 (%USERPROFILE%\.jlc-hardware-project\venv)
# すでに入っているものは飛ばす。何度実行してもよい。途中で「このアプリがデバイスに変更を加えることを許可しますか」と出たら「はい」。
#
# 環境変数 (実行前に $env:SKIP_VSCODE = "1" のように設定):
#   SKIP_VSCODE=1  VS Code と拡張機能を入れない
#   DRY_RUN=1      実行せず、行う内容だけ表示する

function Install-JlcHardware {
    # Windows PowerShell 5.1 では "Stop" にすると外部コマンドの警告出力だけで止まることがあるので Continue にし、結果は個別に確かめる
    $ErrorActionPreference = "Continue"
    $ProgressPreference = "SilentlyContinue"            # 進捗表示があるとダウンロードが極端に遅くなる
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $Repo     = "https://github.com/AsteroidApp-hub/jlc-hardware-project.git"
    $SkillDir = Join-Path $env:USERPROFILE ".claude\skills\jlc-hardware-project"
    $Venv     = if ($env:JLC_VENV) { $env:JLC_VENV } else { Join-Path $env:USERPROFILE ".jlc-hardware-project\venv" }
    $NgVer    = "47"
    $NgUrl    = "https://sourceforge.net/projects/ngspice/files/ng-spice-rework/$NgVer/ngspice-${NgVer}_64.7z/download"
    $NgDir    = Join-Path $env:LOCALAPPDATA "ngspice"
    $Dry      = $env:DRY_RUN -eq "1"

    function Say($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }
    function Run([string]$exe, [string[]]$a) {
        Write-Host "+ $exe $($a -join ' ')"
        if (-not $Dry) { & $exe @a; if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { Write-Host "  (終了コード $LASTEXITCODE)" -ForegroundColor Yellow } }
    }
    function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }
    function Refresh-Path {
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    }
    function Add-UserPath($dir) {
        $cur = [Environment]::GetEnvironmentVariable("Path", "User")
        if (-not $cur) { $cur = "" }
        if (($cur -split ";") -notcontains $dir) {
            Write-Host "+ ユーザーの PATH に追加: $dir"
            if (-not $Dry) { [Environment]::SetEnvironmentVariable("Path", ($cur.TrimEnd(";") + ";" + $dir), "User") }
        }
        if (($env:Path -split ";") -notcontains $dir) { $env:Path = "$env:Path;$dir" }
    }
    function Winget-Install($id, $what, $override = $null) {
        & winget list --id $id -e --accept-source-agreements *> $null
        if ($LASTEXITCODE -eq 0) { Write-Host "入っています: $what"; return }
        $a = @("install", "--id", $id, "-e", "--accept-package-agreements", "--accept-source-agreements")
        if ($override) { $a += @("--override", $override) }
        Run "winget" $a
    }

    if (-not (Have "winget")) {
        Write-Host "winget が見つかりません。Microsoft Store で「アプリ インストーラー」を入れて (更新して) から、もう一度実行してください。" -ForegroundColor Red
        return
    }

    Say "1/8 Git (Skill の取得と、Claude Code がコマンドを動かすのに使う)"
    Winget-Install "Git.Git" "Git"
    Say "2/8 KiCad (回路図・基板)"
    Winget-Install "KiCad.KiCad" "KiCad"
    Say "3/8 Python 3.12 と uv (Python の環境づくり)"
    # 既定のインストールでは python コマンドが PATH に入らないので、PATH に追加するオプションを付ける
    Winget-Install "Python.Python.3.12" "Python 3.12" "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1"
    Winget-Install "astral-sh.uv" "uv"
    Refresh-Path

    Say "4/8 KiCad のコマンド (kicad-cli) を使えるようにする"
    $cli = Get-ChildItem "C:\Program Files\KiCad\*\bin\kicad-cli.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($cli) { Add-UserPath $cli.DirectoryName } else { Write-Host "kicad-cli.exe が見つかりません (KiCad のインストール後にもう一度実行してください)" -ForegroundColor Yellow }

    Say "5/8 ngspice (回路シミュレーション)"
    $ngBin = Get-ChildItem $NgDir -Recurse -Filter "ngspice_con.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ngBin) {
        Write-Host "入っています: $($ngBin.FullName)"
    } else {
        $tmp = Join-Path $env:TEMP "ngspice-$NgVer.7z"
        Write-Host "+ ダウンロード: $NgUrl"
        if (-not $Dry) {
            New-Item -ItemType Directory -Force -Path $NgDir | Out-Null
            Invoke-WebRequest -Uri $NgUrl -OutFile $tmp -UserAgent "Wget" -MaximumRedirection 10
            # .7z の展開: Windows の tar で試し、だめなら 7-Zip を入れて展開する
            & tar -xf $tmp -C $NgDir 2>$null
            if ($LASTEXITCODE -ne 0 -or -not (Get-ChildItem $NgDir -Recurse -Filter "ngspice_con.exe" -ErrorAction SilentlyContinue)) {
                Winget-Install "7zip.7zip" "7-Zip"
                & "C:\Program Files\7-Zip\7z.exe" x $tmp "-o$NgDir" -y | Out-Null
            }
            Remove-Item $tmp -ErrorAction SilentlyContinue
        }
        $ngBin = Get-ChildItem $NgDir -Recurse -Filter "ngspice_con.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if ($ngBin) { Add-UserPath $ngBin.DirectoryName } elseif (-not $Dry) { Write-Host "ngspice を入れられませんでした。https://ngspice.sourceforge.io/download.html から手動で入れてください" -ForegroundColor Yellow }

    Say "6/8 VS Code と Claude Code 拡張機能"
    if ($env:SKIP_VSCODE -eq "1") {
        Write-Host "飛ばします (SKIP_VSCODE=1)"
    } else {
        Winget-Install "Microsoft.VisualStudioCode" "VS Code"
        Refresh-Path
        $code = @("$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd", "C:\Program Files\Microsoft VS Code\bin\code.cmd") |
                Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($code) { Run $code @("--install-extension", "anthropic.claude-code", "--force") }
        elseif ($Dry) { Write-Host "+ code --install-extension anthropic.claude-code" }
        else { Write-Host "VS Code のコマンドが見つかりません。VS Code の拡張機能から「Claude Code」を入れてください" -ForegroundColor Yellow }
    }

    Say "7/8 この Skill"
    $git = (Get-Command git -ErrorAction SilentlyContinue).Source
    if (-not $git) { $git = "C:\Program Files\Git\cmd\git.exe" }
    if (Test-Path (Join-Path $SkillDir ".git")) {
        Run $git @("-C", $SkillDir, "pull", "--ff-only")
    } elseif (Test-Path $SkillDir) {
        Write-Host "$SkillDir はすでにあります (Git 管理ではないのでそのままにします)"
    } else {
        if (-not $Dry) { New-Item -ItemType Directory -Force -Path (Split-Path $SkillDir) | Out-Null }
        Run $git @("clone", $Repo, $SkillDir)
    }

    Say "8/8 CAD 用の Python 仮想環境 (筐体の 3D・図・グラフ用。数分かかります)"
    $vpy = Join-Path $Venv "Scripts\python.exe"
    $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if (-not $uv) {
        $uv = @("$env:LOCALAPPDATA\Microsoft\WinGet\Links\uv.exe", "$env:USERPROFILE\.local\bin\uv.exe") |
              Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $uv) { $uv = "uv" }
    }
    if (-not (Test-Path $vpy)) {
        if (-not $Dry) { New-Item -ItemType Directory -Force -Path (Split-Path $Venv) | Out-Null }
        Run $uv @("venv", "-p", "3.12", $Venv)
    }
    Run $uv @("pip", "install", "--python", $vpy, "build123d", "ezdxf", "matplotlib", "numpy", "pyvista")

    Say "確認"
    # python が Microsoft Store の案内 (WindowsApps) を指すことがあるので、py ランチャーを優先する
    $check = Join-Path $SkillDir "setup\check.py"
    $pyl = (Get-Command py -ErrorAction SilentlyContinue).Source
    $py = (Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" } | Select-Object -First 1).Source
    if ($Dry) { Write-Host "+ py -3 $check" }
    elseif ($pyl -and (Test-Path $check)) { & $pyl -3 $check }
    elseif ($py -and (Test-Path $check)) { & $py $check }
    else { Write-Host "PowerShell を開き直してから python `"$check`" で確認できます" }

    Write-Host ""
    Write-Host "完了しました。" -ForegroundColor Green
    Write-Host "次は VS Code を開き、左のバーの Claude のアイコン (または Ctrl + Esc) から Claude にサインインしてください。"
    Write-Host "機器ごとに空のフォルダを作って VS Code で開き、作りたいものを Claude に話しかければ始められます。"
    Write-Host "(新しく入れたソフトを使うため、開いている PowerShell や VS Code は一度閉じて開き直してください)"
}

Install-JlcHardware
