# TFSUG.JP Agent Skills

Azure DevOps と .NET のパッケージメンテナンス向け plugin（skills + agents）です。Claude Code、GitHub Copilot、Codex で同じ plugin 内容を検証・利用できる構成にしています。

## Plugin

| Plugin | 含まれるスキルとエージェント |
|---|---|
| `azure-devops-toolkit` | スキル: Azure DevOps Foundation、Boards、Repos、Pipelines、Artifacts、Test Plans、Wikis、Advanced Security、CLI、security triage。エージェント: Azure DevOps Agent、Azure DevOps Work Item Agent |
| `nuget-validate` | NuGet の脆弱性、非推奨、掲載状態、公開からの経過日数、プロジェクト監査 |

すべて MIT License で配布します。認証情報は含めず、MCP server も自動構成しません。Azure DevOps の認証と権限は利用者が設定してください。

## Claude Code からインストール

```text
claude plugin marketplace add tfsugjp/skills
claude plugin install azure-devops-toolkit@tfsugjp-agent-skills
claude plugin install nuget-validate@tfsugjp-agent-skills
```

## GitHub Copilot からインストール

Copilot CLI はこのリポジトリの Claude 共通 marketplace catalog を読み取ります。

```text
copilot plugin marketplace add tfsugjp/skills
copilot plugin install azure-devops-toolkit@tfsugjp-agent-skills
copilot plugin install nuget-validate@tfsugjp-agent-skills
```

## Codex の repository-local marketplace からインストール

チェックアウトしたリポジトリの絶対パスを `REPO_ROOT` に設定します。

```text
codex plugin marketplace add "$REPO_ROOT"
codex plugin add azure-devops-toolkit@tfsugjp-agent-skills
codex plugin add nuget-validate@tfsugjp-agent-skills
```

Codex の local marketplace は開発・チーム配布用です。公開 listing への申請は、検証完了後の別リリース作業とします。

## 開発時の検証

リポジトリのルートで次を実行します。

```text
python scripts/validate_marketplaces.py
```

JSON、plugin 名とバージョン、skill frontmatter、source path、相対リンク、plugin root 外参照を検証します。GitHub Actions でも `main` への push と pull request に対して同じ検証を実行します。

## ライセンス

MIT License です。ルートの [LICENSE](LICENSE) と各 plugin bundle 内の LICENSE を参照してください。
