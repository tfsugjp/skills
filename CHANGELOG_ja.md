# 変更履歴

## 未リリース

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
