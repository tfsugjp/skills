# GitHub Issue ステータス スキル

## 概要

`github-plan-wiki` プラグインに `github-issue-status` スキルを追加します。Issue の作成時と着手時に計画ステータスを設定し、親 Issue とサブ Issue のステータスを整合させます。

## 追跡

| 種別 | Issue |
|---|---|
| 親 | [Issue #126](https://github.com/tfsugjp/skills/issues/126) |
| サブ Issue | [Issue #127](https://github.com/tfsugjp/skills/issues/127) |
| サブ Issue | [Issue #128](https://github.com/tfsugjp/skills/issues/128) |
| サブ Issue | [Issue #129](https://github.com/tfsugjp/skills/issues/129) |

## 背景

GitHub の Issue に、open と closed 以外の計画ステータスが追加されました（[changelog](https://github.blog/changelog/2026-11-23-issue-statuses-and-repository-boards-are-in-public-preview/)）。既定のステータスは Backlog、Todo、In progress、In review、Done、Not planned、Duplicate です。各ステータスはカテゴリ（`backlog`、`planned`、`started`、`completed`、`not_planned`、`duplicate`）に属し、カテゴリが open と closed の状態を決めます。GitHub は一部のイベントでステータスを変更します。ユーザーのアサインで Todo、エージェントのアサインやドラフト PR のリンクで In progress、Ready for review または open の PR のリンクで In review になります。親 Issue とサブ Issue の間でステータスは連動せず、`gh` にもステータスのフラグはありません。GraphQL API には `Repository.planningStatuses`、`Issue.status`、`Issue.viewerCanSetStatus`、`CreateIssueInput.statusId`、`setIssueStatus` ミューテーションがあり、`setIssueStatus` はカテゴリに応じて Issue をクローズまたは再オープンします。

## 設計

- **実行時の解決。** リポジトリの `planningStatuses` を読み、`category.key` でステータスを選びます。`In progress` と `In review` はどちらも `started` なので、その中では名前で選びます。ステータス ID はハードコードしません。`planningStatuses` が null、または `viewerCanSetStatus` が false の場合は、ステータスの手順を省略したことを伝えて、本来の作業を続けます。
- **単独のコマンド。** 読み取りと書き込みは、参照ファイルにまとめた単独の `gh api graphql` コマンドで行います。同梱スクリプトは JSON から遷移を計算するだけなので、`gh` を単独のコマンドとして実行する必要がある環境でも動きます。
- **作成時。** 担当者またはマイルストーンがある Issue、承認済み plan から作る Issue は `Todo`、それ以外は `Backlog` にします。`gh issue create` にはステータスのフラグがないため、作成直後に `setIssueStatus` で設定して読み戻します。
- **着手時。** 先にアサインし、次に `In progress` を設定し、読み戻します。アサイン時の自動化による上書きを避けるためです。未解決の `blocked-by` Issue があれば警告します。
- **親 Issue とサブ Issue。** 子が着手されたら、すべての祖先を `In progress` に昇格します。完了済みの祖先は `In progress` で再オープンします。親が着手されたら、`Backlog` の子を `Todo` に昇格します。この再オープンの場合を除き、ステータスは前にだけ進めます。
- **完了時。** すべてのサブ Issue が完了したら、親を `Done` にすることを提案します。`Done`、`Not planned`、`Duplicate` は Issue をクローズするので、確認を得てから実行します。PR による `In progress` と `In review` は GitHub の自動化に任せます。
- **連携。** `github-plan-issues` は GraphQL の手順を重複させず、初期ステータスと読み戻しにこのスキルを使います。

## 実装フェーズ

1. スキル、GraphQL の参照、遷移スクリプトと単体テストを追加します（Issue #127）。
2. `github-plan-issues` をこのスキルに連携させます（Issue #128）。
3. AGENTS.md、README、CHANGELOG、`docs/plan` の英語版と日本語版、両方のプラグインマニフェストを更新します（Issue #129）。

## 検証

- すべての遷移、後退させないルール、ステータスを利用できない場合の単体テスト。
- スクラッチリポジトリで、スキルあり・なしの評価を実行します。
- `scripts/validate_marketplaces.py` と、英語版・日本語版の整合性の確認。
