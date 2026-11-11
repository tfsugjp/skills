# 変更履歴

## 未リリース

- `dotnet-azure-lessons` を追加しました。.NET・Azure・PowerShell・macOS・エージェントセッションの障害切り分け向けに、適用場面を絞った11個のスキルと読み取り専用レビュアーを提供します。各ルールには観測可能な確認方法と簡潔な失敗理由を残しました。複数PCの履歴を基に、古い非同期結果、投稿前のPR差分再確認、環境更新のステージング、認証の切り分け、ソースファイルのエンコーディングへの対策を盛り込みました。重複チェックリストを削除し、無関係な移行・インストール・外部更新や不要な承認待ちにつながるルールを限定しました。レビュアーの権限は読み取り・検索のみです。呼び出し側から差分と検証報告を渡し、欠陥と証拠不足を区別します。
- `github-plan-wiki` を 0.2.1、`azure-devops-toolkit` を 0.3.2 に更新しました。GitHub PR と Azure DevOps Repos の手順は、先に PR を作成してリンクしてから、証拠のある受け入れ基準を更新します（Issue 本文は書き込み直前に再読込し、チェックボックスのない Work Item ではコメントで進捗を記録）。PR の追跡リンクも確認し、未完了の基準を保持し、追跡項目自体のクローズは別に扱います。
- `github-issue-artifacts` スキル（`github-plan-wiki`）を追加しました。`gh issue artifact` で長い補足資料やリッチな記録を扱い、Artifact が使えない場合は内容を捨てずに Wiki 登録へ回し、未完了として報告します。
- `azure-managed-identity-review` プラグインを追加しました。ある利用者（たとえばストレージのカスタマーマネージドキー）のために付けた権限は、同じ ID を使うほかの利用者の audience をカバーせず、その利用者だけにとどまりもしません。しかもローカル E2E は開発者本人の権限で動きます。そこで、このスキルは ID を共有するすべてのリソース・アプリ設定・コード・フェデレーション資格情報を横断してレビューします。`msi_review.py` は Bicep、ARM、Terraform、アプリ設定、コード（`static`）、または読み取り専用の `az` 呼び出しでサブスクリプション（`live`、アプリ設定はマスクし IaC とのドリフトも検出）を読み取り、規則 MIR000-MIR008 を報告します。
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
