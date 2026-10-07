# TFSUG.JP Agent Skills

Azure DevOps、GitHub、.NET のパッケージメンテナンス、Relaypublisher、Windows での安全なコマンド実行、Azure マネージド ID レビューのワークフロー向け plugin（skills + agents）です。Claude Code、GitHub Copilot、Codex で同じ plugin 内容を検証・利用できる構成にしています。

## Plugin

| Plugin | 含まれるスキルとエージェント |
|---|---|
| `azure-devops-toolkit` | スキル: Azure DevOps Foundation、Boards、Repos、Pipelines、Artifacts、Test Plans、Wikis、Advanced Security、CLI、security triage。Boards は Windows でネイティブ PowerShell を使い、本文を Markdown で書き込み、Bug の Repro Steps に根本原因と修正方針を記録し、Work Item から Wiki ページへ逆リンクします。また、Feature 相当の Work Item と承認済みのバグ修正方針は Wiki への登録を必須とします。Wikis は計画とバグ修正方針を、リポジトリをルートとする階層（`/<repo>` の全体設計、`/<repo>/plan` と `/<repo>/bug` の一覧）に、同梱のページテンプレートと検証スクリプトを使って登録します。エージェント: Azure DevOps Agent、Azure DevOps Work Item Agent |
| `nuget-validate` | NuGet の脆弱性、非推奨、掲載状態、公開からの経過日数、プロジェクト監査 |
| `dependabot-safe-merge` | Dependabot pull request の安全な更新、公開経過時間ポリシー、マージゲート、メジャーアップグレード計画 |
| `github-plan-wiki` | スキル: GitHub Plan Issues（親 issue と sub-issue の階層）、GitHub Wiki Plan（英日 Wiki plan と Home index の管理） |
| `relaypublisher-manifest` | Relaypublisher manifest (v1.1.0) の作成・更新・静的検証。Windows Win32 の script/file-system detection と、複数 bundle を含む macOS PKG/LOB の detection に対応 |
| `repository-init` | ライセンス、セキュリティ、言語方針、`AGENTS.md` をリポジトリ作成時に一度だけ初期化 |
| `azure-managed-identity-review` | Azure のマネージド ID を読み取り専用でレビューします。同じ ID を共有するリソース・アプリ設定・コード・フェデレーション資格情報（FIC）をすべて洗い出し、各利用者の audience に対する権限漏れ、他の利用者への権限の漏洩、ID 選択の誤り、IaC とのドリフトを報告します（`msi_review.py`、規則 MIR000-MIR008） |
| `windows-shell-safety` | Windows で Azure CLI・JSON・パイプを安全に実行するための規則、`cmd.exe` による引数欠落を実行前に検出する lint（`Test-NativeCommand.ps1`）、JSON を UTF-8 の `@<file>` で渡す PowerShell 7 ヘルパー |

すべて MIT License で配布します。認証情報は含めず、MCP server も自動構成しません。Azure DevOps の認証と権限は利用者が設定してください。

## Claude Code からインストール

```text
claude plugin marketplace add tfsugjp/skills
claude plugin install azure-devops-toolkit@tfsugjp-agent-skills
claude plugin install nuget-validate@tfsugjp-agent-skills
claude plugin install dependabot-safe-merge@tfsugjp-agent-skills
claude plugin install github-plan-wiki@tfsugjp-agent-skills
claude plugin install relaypublisher-manifest@tfsugjp-agent-skills
claude plugin install repository-init@tfsugjp-agent-skills
claude plugin install windows-shell-safety@tfsugjp-agent-skills
claude plugin install azure-managed-identity-review@tfsugjp-agent-skills
```

## GitHub Copilot からインストール

Copilot CLI はこのリポジトリの Claude 共通 marketplace catalog を読み取ります。

```text
copilot plugin marketplace add tfsugjp/skills
copilot plugin install azure-devops-toolkit@tfsugjp-agent-skills
copilot plugin install nuget-validate@tfsugjp-agent-skills
copilot plugin install dependabot-safe-merge@tfsugjp-agent-skills
copilot plugin install github-plan-wiki@tfsugjp-agent-skills
copilot plugin install relaypublisher-manifest@tfsugjp-agent-skills
copilot plugin install repository-init@tfsugjp-agent-skills
copilot plugin install windows-shell-safety@tfsugjp-agent-skills
copilot plugin install azure-managed-identity-review@tfsugjp-agent-skills
```

## Codex の repository-local marketplace からインストール

チェックアウトしたリポジトリの絶対パスを `REPO_ROOT` に設定します。

```text
codex plugin marketplace add "$REPO_ROOT"
codex plugin add azure-devops-toolkit@tfsugjp-agent-skills
codex plugin add nuget-validate@tfsugjp-agent-skills
codex plugin add dependabot-safe-merge@tfsugjp-agent-skills
codex plugin add github-plan-wiki@tfsugjp-agent-skills
codex plugin add relaypublisher-manifest@tfsugjp-agent-skills
codex plugin add repository-init@tfsugjp-agent-skills
codex plugin add windows-shell-safety@tfsugjp-agent-skills
codex plugin add azure-managed-identity-review@tfsugjp-agent-skills
```

Codex の local marketplace は開発・チーム配布用です。公開 listing への申請は、検証完了後の別リリース作業とします。

`repository-init` は `$repository-init` を明示的に呼び出したときだけ使用します。新規または既存リポジトリの不足するガバナンスファイルを整備し、確定したライセンスと言語プロファイルを `.repository-init.json` に保存します。完了後に再度呼び出してもファイルを変更しません。Git の初期化、リモート作成、Issue／Work Item 作成、Wiki 公開、コミット、プッシュは行いません。

## Windows Shell Safety

`windows-shell-safety` は、Windows で Azure CLI などのネイティブコマンドを実行するエージェント（と人）のためのプラグインです。`az` の実体はバッチファイル `az.cmd` のため、引数は PowerShell の後に `cmd.exe` でも解釈されます。その結果、引用符外の `|`、`&`、`<`、`>`、`^` が消費され、`%VAR%` が展開され、インライン JSON の二重引用符が失われます。エスケープを変えて再試行するのではなく、スキルが定める一つの安全な手順に従います。

- 規則: `pwsh` だけを使う、スクリプトは `-Command` 文字列ではなく `pwsh -File` で実行する、JSON は UTF-8 ファイルを `'@<file>'` で渡す、`az` の出力は `ConvertFrom-Json` で絞り込む（または `--query` を `'@<file>'` から読み込む）、ネイティブ出力を解析する前にコンソールを UTF-8 にする。
- 実行前の lint: `Test-NativeCommand.ps1` は規則 WSS001-WSS009（`cmd.exe`、入れ子の `-Command`、`az` に渡す `cmd` メタ文字やインライン JSON、引用符なしの `@file` など）を理由と安全な書き換えつきで報告し、指摘があれば終了コード 1 を返します。
- ヘルパー: `Invoke-NativeJson.ps1` をドットソースすると、`Invoke-AzJson` / `Invoke-NativeJson`（UTF-8 の本文ファイル、JSON 出力の解析、テキスト出力用の `-Raw`、`cmd.exe` に書き換えられる引数の拒否）と、`.cmd` 対象が実際に受け取る argv を表示する `-EchoArgs` / `Show-NativeArgs` を使えます。

```powershell
$skill = 'plugins/windows-shell-safety/skills/windows-shell-safety'
pwsh -NoProfile -File "$skill/scripts/Test-NativeCommand.ps1" -Command 'az version --query "keys(@)|[0]" -o tsv'
. "$skill/scripts/Invoke-NativeJson.ps1"
(Invoke-AzJson -Arguments 'version').'azure-cli'
```

このスキルは助言用です。フックを同梱しないため、lint の指摘だけでツール呼び出しが止まることはありません。

## Azure Managed Identity Review

`azure-managed-identity-review` は、リソースにマネージド ID を設定する変更のためのプラグインです。あるリソース用に作ったユーザー割り当て ID（たとえばストレージのカスタマーマネージドキー用）は、ほかのリソース（Function App や、フェデレーション資格情報経由の GitHub Actions など）でも使い回されがちです。最初の用途で付けた権限は、ほかの利用者が使う audience（Service Bus、SQL、Cosmos DB データプレーン、独自 API）をカバーせず、逆に不要な利用者にまで権限が漏れます。ローカル E2E は開発者本人の権限で動くため、権限漏れはデプロイ後まで分かりません。

- `msi_review.py static` は Bicep（Bicep CLI でコンパイル）、ARM JSON、Terraform（`*.tf` または `terraform show -json`）、アプリ設定、ソースコードを読み取ります。`--resource <name>` を指定すると、そのリソースが使う ID と、その ID を使うほかのすべての利用者をレビューします。
- `msi_review.py live` は読み取り専用の `az` 呼び出し（Resource Graph、ロール割り当て、フェデレーション資格情報、マスクしたアプリ設定）でサブスクリプションを読み取ります。`--static` を付けると IaC とのドリフトも報告します。
- レポートには ID ごとに、利用者とその用途、権限とそれを必要とする利用者、フェデレーション資格情報を示し、続けて修正方法つきの指摘 MIR000-MIR008 を出力します。ロール割り当てや資格情報を作成することはありません。

```bash
python3 plugins/azure-managed-identity-review/skills/azure-managed-identity-review/scripts/msi_review.py static plugins/azure-managed-identity-review/skills/azure-managed-identity-review/tests/fixtures/terraform-canonical --resource stshared001
```

```powershell
$skill = 'plugins/azure-managed-identity-review/skills/azure-managed-identity-review'
python3 "$skill/scripts/msi_review.py" static "$skill/tests/fixtures/terraform-canonical" --resource stshared001
```

Windows では同じスクリプトを `python` で実行します。

## プロジェクト文書管理

[project-documentation](.github/skills/project-documentation/SKILL.md) は英語の文書を `docs/adr/`、`docs/architecture/`、`docs/infra/`、`docs/test/e2e/`、`docs/setup/` に整理します。既存記録の変更には明示承認が必要です。判断は同じ項目を更新し、旧判断の要約・更新理由・承認情報を履歴に残します。選定根拠URLと実際のE2E実行証跡も記録します。

### 導入・利用

このリポジトリには英語スキルが検出ディレクトリに配置されています。別リポジトリで利用する場合は `.github/skills/project-documentation/` 全体を、ライセンス・テンプレートも含めて対象の `.github/skills/` にコピーしてください。対応クライアントで文書作成を依頼します。検出・起動の動作はクライアントに依存します。

依頼例:

- 「現在の構成と判断根拠を docs 配下に文書化してください」
- 「ADR 0001 の更新案・差分・理由を提示し、承認まで待ってください」
- 「購入フローのE2Eシナリオを、計画と実際の実行証跡を区別して記録してください」

### リソース

- [英語スキル](.github/skills/project-documentation/SKILL.md)
- [ADR](.github/skills/project-documentation/templates/adr/decision.md)
- [アーキテクチャ](.github/skills/project-documentation/templates/architecture/design.md)
- [インフラ](.github/skills/project-documentation/templates/infra/runbook.md)
- [テスト戦略](.github/skills/project-documentation/templates/test/strategy.md)
- [E2E](.github/skills/project-documentation/templates/test/e2e/scenario.md)
- [セットアップ](.github/skills/project-documentation/templates/setup/guide.md)
- [人間向け日本語参考訳](docs/skill-guides/project-documentation_ja.md)

日本語参考訳はスキルとして登録しません。検出ディレクトリへのコピー、スキル用フロントマターの付与、エージェントの正本入力としての利用は禁止です。テンプレートはひな型であり、判断やテスト実行済みの証拠ではありません。

## 開発時の検証

リポジトリのルートで次を実行します。

```text
python scripts/validate_marketplaces.py
python -m unittest discover -s plugins/github-plan-wiki/skills/github-wiki-plan/tests -p 'test_*.py'
```

JSON、plugin 名とバージョン、skill frontmatter、source path、相対リンク、plugin root 外参照、GitHub Wiki template の平坦化された公開 route を検証します。GitHub Actions でも `main` への push と pull request に対して同じ検証を実行します。`tests` ジョブは各 plugin の `tests/test_*.py` も実行し（`windows-shell-safety` のテストには `pwsh` が必要）、`windows-latest` の `windows-shell-safety` ジョブは `cmd.exe` による引数の欠落を再現して安全なパターンを検証します。

## ライセンス

MIT License です。ルートの [LICENSE](LICENSE) と各 plugin bundle 内の LICENSE を参照してください。

project-documentation スキルには [MIT ライセンスのコピー](.github/skills/project-documentation/LICENSE.txt) を同梱しています。脆弱性の報告方法は [SECURITY.md](SECURITY.md) を参照してください。

[English overview](README.md)
