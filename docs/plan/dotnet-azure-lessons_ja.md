# .NET / Azure 教訓プラグイン

## 概要

`dotnet-azure-lessons` は、過去のエージェントセッションで繰り返し受けた訂正を、.NET・Azure・PowerShell 開発で確認できるルールにします。工程別の 9 個のスキルと読み取り専用のレビューエージェントで、同じ誤りの再発を防ぎます。追跡: 親 Issue #107、子 Issue #108-#111。

## 設計

- 抽出元: 17 プロジェクトのエージェントセッションでの、やり直しの依頼、ユーザーの訂正、reviewer・Copilot・Codex の指摘です。重複をまとめると約 70 件です。プロジェクト名、ホスト名、ドメイン、URL は一般化し、公開しません。
- 各スキルは作業の 1 つの工程で読み込まれ、同じ構成を持ちます: 使う場面、使わない場面、ルール（ルール・確認方法・理由）、完了チェックリスト。
- 既存スキルが扱う手順は繰り返さず、引き渡します: ネイティブコマンドの引用符は `windows-shell-safety`、PR 本文と閉鎖キーワードは `github-pull-request`、Issue 階層は `github-plan-issues`、パイプラインの実行は `azure-devops-pipelines`、ADR とアーキテクチャ文書は `project-documentation`、パッケージのバージョンは `nuget-validate`。
- `dotnet-lessons-reviewer` エージェントは、差分に当てはまるスキルを選び、その完了チェックリストで差分を確認し、ファイルを編集せずに指摘を報告します。

| スキル | 工程 |
|---|---|
| `dotnet-architecture-design` | 設計書、ADR、対応バージョン |
| `dotnet-coding` | C# の実装 |
| `vs-extension-remote-ui` | Visual Studio Remote UI の ViewModel と XAML |
| `powershell-scripting` | PowerShell スクリプト |
| `dotnet-debugging` | 障害の調査 |
| `dotnet-testing` | テストと、変更が検証済みかの判断 |
| `dotnet-documentation` | コードとともに変わる文書 |
| `dotnet-ci-cd` | ワークフローとパイプラインの定義、パッケージング |
| `pr-issue-workflow` | レビュースレッド、コミット、マージ、Issue のクローズ |

## 検証

- `python scripts/validate_marketplaces.py` で、マニフェスト、スキルの frontmatter、相対リンクを確認します。
- プラグインのディレクトリで URL とプライベートなホスト名を検索し、何も見つからないことを確認します。
- 各 description に工程と固有の語を書き、使わない場面に隣接するスキルを書くことで、1 つのプロンプトですべてのスキルが読み込まれないようにします。
