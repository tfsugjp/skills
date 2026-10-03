# Agent Skills

Team Foundation Users Japan が管理する再利用可能なエージェントスキルです。既存の一覧とリポジトリの指針は [AGENTS.md](AGENTS.md) を参照してください。正本は [英語README](README.md) です。

## プロジェクト文書管理

[project-documentation](.github/skills/project-documentation/SKILL.md) は英語の文書を `docs/adr/`、`docs/architecture/`、`docs/infra/`、`docs/test/e2e/`、`docs/setup/` に整理します。既存記録の変更には明示承認が必要です。判断は同じ項目を更新し、旧判断の要約・更新理由・承認情報を履歴に残します。選定根拠URLと実際のE2E実行証跡も記録します。

## 導入・利用

このリポジトリには英語スキルが検出ディレクトリに配置されています。別リポジトリで利用する場合は `.github/skills/project-documentation/` 全体を、ライセンス・テンプレートも含めて対象の `.github/skills/` にコピーしてください。対応クライアントで文書作成を依頼します。検出・起動の動作はクライアントに依存します。

依頼例:

- 「現在の構成と判断根拠を docs 配下に文書化してください」
- 「ADR 0001 の更新案・差分・理由を提示し、承認まで待ってください」
- 「購入フローのE2Eシナリオを、計画と実際の実行証跡を区別して記録してください」

## リソース

- [英語スキル](.github/skills/project-documentation/SKILL.md)
- [ADR](.github/skills/project-documentation/templates/adr/decision.md)
- [アーキテクチャ](.github/skills/project-documentation/templates/architecture/design.md)
- [インフラ](.github/skills/project-documentation/templates/infra/runbook.md)
- [テスト戦略](.github/skills/project-documentation/templates/test/strategy.md)
- [E2E](.github/skills/project-documentation/templates/test/e2e/scenario.md)
- [セットアップ](.github/skills/project-documentation/templates/setup/guide.md)
- [人間向け日本語参考訳](docs/skill-guides/project-documentation_ja.md)

日本語参考訳はスキルとして登録しません。検出ディレクトリへのコピー、スキル用フロントマターの付与、エージェントの正本入力としての利用は禁止です。テンプレートはひな型であり、判断やテスト実行済みの証拠ではありません。

## セキュリティ・ライセンス

報告方法は [SECURITY.md](SECURITY.md)、日本語参考は [SECURITY_ja.md](SECURITY_ja.md) を参照してください。リポジトリと新スキルは [MIT](LICENSE) です。スキルには [LICENSE.txt](.github/skills/project-documentation/LICENSE.txt) を同梱します。既存の第三者スキルは個別のライセンス条件を確認してください。
