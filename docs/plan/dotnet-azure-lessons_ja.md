# .NET / Azure 教訓プラグイン

## 概要

`dotnet-azure-lessons` は、過去のエージェントセッションで繰り返し受けた訂正を、.NET・Azure・PowerShell 開発で確認できるルールにします。11 個のスキルと読み取り専用のレビューエージェントで、同じ誤りの再発を防ぎます。追跡: 親 Issue #107、子 Issue #108-#111。

## 設計

- 抽出元: 17 プロジェクトのエージェントセッションでの、やり直しの依頼、ユーザーの訂正、reviewer・Copilot・Codex の指摘です。重複をまとめると約 70 件です。さらに別のワークステーションの Claude Code と Codex のセッション（13 プロジェクト）、および macOS ワークステーションの Claude Code のセッション（13 プロジェクトディレクトリ、約 115 セッション。この端末の Codex 履歴は読んでいません）と照合しました。照合のたびに、漏れていた教訓の追加、履歴と矛盾するルールの修正、スキル間で重複していたルールの統合を行いました。プロジェクト名、ホスト名、ドメイン、URL は一般化し、公開しません。
- 9 個のスキルは作業の 1 つの工程で、2 個は状況（macOS での作業、エージェントセッションが原因のコマンド失敗）で読み込まれます。構成は共通で、使わない場面とルールです。すべてのルールに確認方法と理由を付け、各スキルの末尾に「完了を報告する前に該当する確認方法を点検する」という 1 行を置きます。完了チェックリストはルールの言い直しだったため、置きません。
- すべてのコマンドで守るべきルール（たとえば権限ルールに一致するコマンドの形）は、スキルが発動するかどうかに依存できません。`agent-sandbox-troubleshooting` は失敗した後の切り分けを扱い、常時守るコマンドのルールはユーザーまたはリポジトリのエージェント向け指示に置きます。
- 既存スキルが扱う手順は繰り返さず、引き渡します: ネイティブコマンドの引用符は `windows-shell-safety`、PR 本文と閉鎖キーワードは `github-pull-request`、Issue 階層は `github-plan-issues`、パイプラインの実行は `azure-devops-pipelines`、ADR とアーキテクチャ文書は `project-documentation`、パッケージのバージョンは `nuget-validate`、コンテナのコマンドは `native-container-cli`。スキル間の参照は、番号ではなくルールの見出しで示します。
- `dotnet-lessons-reviewer` エージェントは、差分に当てはまるスキルを選び、各ルールの確認方法で差分を点検し、ファイルを編集せずに指摘を報告します。

| スキル | 工程または状況 |
|---|---|
| `dotnet-architecture-design` | 設計書、ADR、対応バージョン |
| `dotnet-coding` | C# の実装 |
| `vs-extension-remote-ui` | Visual Studio Remote UI の ViewModel と XAML |
| `powershell-scripting` | PowerShell スクリプト |
| `dotnet-debugging` | 障害の調査 |
| `dotnet-testing` | テストと、変更が検証済みかの判断 |
| `dotnet-documentation` | コードとともに変わる文書 |
| `dotnet-ci-cd` | ワークフローとパイプラインの定義、パッケージング |
| `pr-issue-workflow` | レビュースレッド、コミット、push、マージ、Issue のクローズ |
| `dotnet-macos-development` | macOS や Apple silicon での .NET / Azure の作業 |
| `agent-sandbox-troubleshooting` | エージェントセッションの sandbox、権限、資格情報が原因でコマンドが失敗したとき |

## 検証

- `python scripts/validate_marketplaces.py` で、マニフェスト、スキルの frontmatter、相対リンクを確認します。
- プラグインのディレクトリで URL とプライベートなホスト名を検索し、何も見つからないことを確認します。
- 各 description に工程、または発動のきっかけになる症状を書き、使わない場面に隣接するスキルを書くことで、1 つのプロンプトですべてのスキルが読み込まれないようにします。
- 未検証: 実際のセッションで、各スキルが意図した状況だけで読み込まれるか。
