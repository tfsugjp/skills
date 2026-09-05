# TFSUG.JP Agent Skills

Azure DevOps、GitHub、.NET のパッケージメンテナンス、Relaypublisher のワークフロー向け plugin（skills + agents）です。Claude Code、GitHub Copilot、Codex で同じ plugin 内容を検証・利用できる構成にしています。

## Plugin

| Plugin | 含まれるスキルとエージェント |
|---|---|
| `azure-devops-toolkit` | スキル: Azure DevOps Foundation、Boards、Repos、Pipelines、Artifacts、Test Plans、Wikis、Advanced Security、CLI、security triage。エージェント: Azure DevOps Agent、Azure DevOps Work Item Agent |
| `nuget-validate` | NuGet の脆弱性、非推奨、掲載状態、公開からの経過日数、プロジェクト監査 |
| `dependabot-safe-merge` | Dependabot pull request の安全な更新、公開経過時間ポリシー、マージゲート、メジャーアップグレード計画 |
| `github-plan-wiki` | スキル: GitHub Plan Issues（親 issue と sub-issue の階層）、GitHub Wiki Plan（英日 Wiki plan と Home index の管理） |
| `relaypublisher-manifest` | Relaypublisher manifest (v1.1.0) の作成・更新・静的検証。Windows Win32 の script/file-system detection と、複数 bundle を含む macOS PKG/LOB の detection に対応 |

すべて MIT License で配布します。認証情報は含めず、MCP server も自動構成しません。Azure DevOps の認証と権限は利用者が設定してください。

## Claude Code からインストール

```text
claude plugin marketplace add tfsugjp/skills
claude plugin install azure-devops-toolkit@tfsugjp-agent-skills
claude plugin install nuget-validate@tfsugjp-agent-skills
claude plugin install dependabot-safe-merge@tfsugjp-agent-skills
claude plugin install github-plan-wiki@tfsugjp-agent-skills
claude plugin install relaypublisher-manifest@tfsugjp-agent-skills
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
```

Codex の local marketplace は開発・チーム配布用です。公開 listing への申請は、検証完了後の別リリース作業とします。

## 開発時の検証

リポジトリのルートで次を実行します。

```text
python scripts/validate_marketplaces.py
python -m unittest discover -s plugins/github-plan-wiki/skills/github-wiki-plan/tests -p 'test_*.py'
```

JSON、plugin 名とバージョン、skill frontmatter、source path、相対リンク、plugin root 外参照、GitHub Wiki template の平坦化された公開 route を検証します。GitHub Actions でも `main` への push と pull request に対して同じ検証を実行します。

## ライセンス

MIT License です。ルートの [LICENSE](LICENSE) と各 plugin bundle 内の LICENSE を参照してください。
