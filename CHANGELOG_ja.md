# 変更履歴

## 未リリース

- `windows-shell-safety` プラグインを追加しました。Windows で `az`（`az.cmd`）などのバッチファイルが `cmd.exe` を経由するときに `|`、`&`、`%VAR%`、二重引用符、インライン JSON が失われる問題や、シェルをまたいで `-Command` 文字列を入れ子にする問題を防ぐスキルです。実行前 lint（`Test-NativeCommand.ps1`、規則 WSS001-WSS009）と、本文を UTF-8 の `@<file>` で渡す PowerShell 7 ヘルパー（`Invoke-AzJson`、`Invoke-NativeJson`、`Show-NativeArgs`）を同梱します。`windows-latest` の CI ジョブで引数の欠落を再現し、安全なパターンを検証します。
- `azure-devops-toolkit` を 0.3.1 に更新しました。`azure-devops-boards` スキルは、`/multilineFieldsFormat/<field>`（MCP では `format: "Markdown"`）でフィールドを Markdown に切り替えてから本文を Markdown で書き込みます。サーバーが Markdown フィールドに対応していない場合に限り HTML に切り替え、読み戻し検査も形式に応じて行います。Azure DevOps Services での実機確認に基づき、`<` は本文中では `&amp;lt;`、コード内では `&lt;` に変換します。サーバーはタグの形をした文字列を削除し、フォームのプレビューは値を一度デコードしてから描画するためです（MCP サーバーと同じ一重の `&lt;script&gt;` では、それ以降の本文が表示されませんでした）。
- Bug では、AI が分析した根本原因（Root cause）と修正方針（Fix approach）を、再現手順・期待結果と実際の結果とあわせて、Bug フォームの本文欄である Repro Steps に記録するようにしました。Work Item エージェントも同じ規則に従います。
- 内容を Azure DevOps Wiki に登録した Work Item は、種類を問わず、本文の `## Wiki` セクションと `Hyperlink` リンクでページへ逆リンクします。そのために `azure-devops-wiki` スキルはページの `remoteUrl` を返します。Windows ネイティブ実行リファレンスには、検証済みの PowerShell ヘルパー `Write-WorkItemBody` と `Add-WikiBackLink`、および Linux/macOS 版の手順を追加しました。`azure-devops-cli` と `azure-devops-security-triage` スキルも、Work Item の本文については同じ規則に従うようにしました。
- `azure-devops-toolkit` を 0.3.0 に更新しました。`azure-devops-wiki` スキルは、リポジトリ名をルートとする階層（`/<repo>` の概要と全体設計、`/<repo>/plan` と `/<repo>/bug` の一覧）に登録します。ルート・一覧・計画・バグ修正方針のテンプレート、Work Item と pull request の必須参照、非準拠ページを承認後に移行する手順を追加しました。
- Wiki 検証スクリプトに `--require-pr` / `-RequirePr` と `--require-page-link` / `-RequirePageLink` を追加し、PowerShell 版との一致も確かめる単体テストを追加しました。
- Boards スキルと Work Item エージェントは、承認済みのバグ修正方針を Wiki スキルへ引き渡し、Wiki 構造の作成を Wiki スキルの登録手順に委ねるようにしました。
- リポジトリのガバナンスを一度だけ初期化し、中断から再開でき、完了後は冪等に動作する明示呼び出し専用の `repository-init` プラグインを追加しました。

## 0.1.0

- `azure-devops-toolkit` プラグインを追加しました。
- `nuget-validate` プラグインを追加しました。
- Claude Code と GitHub Copilot のマーケットプレースメタデータを追加しました。
- Codex のリポジトリローカルマーケットプレースメタデータを追加しました。
- マーケットプレース検証と GitHub Actions のチェックを追加しました。
