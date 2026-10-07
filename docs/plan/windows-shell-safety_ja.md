# Windows Shell Safety プラグイン

## 概要

`windows-shell-safety` は、Windows で Azure CLI・JSON ペイロード・パイプがネイティブコマンドに届くまでに文字を失い、エージェントが時間を浪費することを防ぎます。スキルが安全な実行手順を一つに定め、同梱の lint が壊れるコマンド形を実行前に検出し、PowerShell 7 のヘルパーがその安全な手順を実装します。追跡: 親 issue #84、サブ issue #85-#88。

## 設計

- Windows の `az` はバッチファイル `az.cmd` であり、引数は PowerShell の後に `cmd.exe` でも解釈されます。PowerShell 7.3+ は `.cmd`/`.bat` に対して Legacy の引数渡し（空白を含む引数だけを引用符で囲み、内部の `"` はエスケープしない）を維持し、`cmd.exe` は引用符外の `|`、`&`、`<`、`>`、`^` を消費し、`%NAME%` は引用符内でも展開します。他のバッチシム（`npm`、`npx`、`pnpm`、`yarn`、`code`、`func`、`ng`）も同様で、`gh` や `git` などの `.exe` は影響を受けません。
- 規則（優先順）: `pwsh` だけを使う、スクリプトは `-Command` 文字列ではなく `pwsh -File` で実行する、JSON を引数に入れない（BOM なし UTF-8 ファイルを引用符付きの `'@<file>'` で渡す）、`ConvertFrom-Json` で絞り込むか `--query` を `'@<file>'` から読み込んで `cmd` メタ文字や引用符を `az` の引数に入れない（az は任意の引数で `@<file>` を受け付ける）、ネイティブ出力を解析する前にコンソールを UTF-8 にし `PYTHONIOENCODING=utf-8` を設定する、実行前に lint を通す、エスケープを変える前に受信 argv を確認する。
- `Test-NativeCommand.ps1` は `-Command`、`-Path`、パイプライン入力を受け付け、PowerShell を言語 AST で解析し、Bash のコマンドラインにも効く行単位の規則を加えます。行単位の規則はコメントとメッセージ文字列を対象外にします。規則: WSS001 `cmd /c`/`%COMSPEC%`、WSS002 パイプ・引用符・波括弧を含む `-Command` 文字列、WSS003 バッチ対象の引数（文字列変数を含む）の `cmd` メタ文字、WSS004 インライン JSON（リテラル、`ConvertTo-Json` の結果、変数）、WSS005 埋め込まれた二重引用符、WSS006 Windows PowerShell 5.1、WSS007 同じブロックまたは外側のブロックで先に UTF-8 を設定していないネイティブ出力の JSON 解析（警告）、WSS008 MSYS の回避策、WSS009 引用符なし `@file` のスプラッティング。終了コードは問題なし 0、指摘あり 1、ファイルなし 2。機械処理用に `-AsJson` を提供します。
- `Invoke-NativeJson.ps1` はドットソースで読み込みます。`Invoke-NativeJson` は呼び出し中のエンコーディングを UTF-8 にし、`-Body` を UTF-8 一時ファイルに書いて `@<file>` で参照させ（`gh api --input <file>` のように形式は変更可能）、バッチ対象では `cmd` に書き換えられる引数を実行前に拒否し、失敗時は stderr 付きで例外を投げ、JSON 出力を解析し、後始末をします。`Invoke-AzJson` は `-o json` と `PYTHONIOENCODING` を追加します。`Show-NativeArgs` は `az.cmd` と同じく `%*` を転送する `.cmd` シム経由で、子プロセスが受け取った argv を表示します。
- PreToolUse フックは使いません。lint は助言にとどめ、誤検知で作業が止まらないようにします。Azure DevOps スキルは規則を重複させず、このスキルを参照します。

## 検証

- `python3 scripts/validate_marketplaces.py` でプラグインのメタデータとリンクを検証します。
- `tests/test_native_command_lint.py`（`pwsh` 経由の unittest）は、各危険フィクスチャが対応する規則を報告すること、WSS001-WSS009 のすべてにフィクスチャがあること、安全フィクスチャで指摘がないこと、コマンド・パイプライン・パスの各入力と終了コード、ヘルパーの UTF-8 本文の往復・バッチ対象での拒否・stderr の報告・argv の表示を確認します。既存の Ubuntu テストジョブで実行されます。
- `tests/Invoke-WindowsRepro.ps1` は `windows-latest` の CI ジョブで実行され、`az` が `az.cmd` に解決されること、`.cmd` シムで `a|b`、`a&b`、インライン JSON、`%USERNAME%` が失われること、引用符なしのパイプや埋め込み引用符で `az version --query` が壊れることを示し、`--query '@<file>'`、`ConvertFrom-Json` での絞り込み、ヘルパーの拒否、lint が記載どおりに動くことを検証します。`az version` はサインイン不要です。
