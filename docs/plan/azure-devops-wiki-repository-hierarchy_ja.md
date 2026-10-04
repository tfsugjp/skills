# Azure DevOps Wiki のリポジトリ階層

[English](https://github.com/tfsugjp/skills/wiki/azure-devops-wiki-repository-hierarchy)

## 概要

`azure-devops-wiki` スキルが、計画とバグ修正方針を、リポジトリをルートとする固定の階層に登録するようにします。リポジトリのルートページにはリポジトリ概要と現在の全体設計を置き、仕様変更のたびに更新します。`plan` と `bug` の一覧ページには、すべての子ページを Work Item・pull request・状態・概要とともに掲載します。

## 追跡

| 種別 | Issue |
|---|---|
| 親 | [Issue #73](https://github.com/tfsugjp/skills/issues/73) |
| サブイシュー | [Issue #74](https://github.com/tfsugjp/skills/issues/74) |
| サブイシュー | [Issue #75](https://github.com/tfsugjp/skills/issues/75) |
| サブイシュー | [Issue #76](https://github.com/tfsugjp/skills/issues/76) |
| サブイシュー | [Issue #77](https://github.com/tfsugjp/skills/issues/77) |

## 背景

既存の Azure DevOps Wiki には複数の形が混在しています。設計を持つ `<repo>-plan` ページの直下に計画を置く形、概要表はあるが設計がないリポジトリページ、PR 列のない計画一覧、子ページが漏れている一覧などです。PR を `#<n>` と書いた箇所もあり、Azure DevOps Wiki では Work Item 参照として表示されます。また、スキルが Wiki 構造の作成を禁止していたため、これらをスキル経由で修復できませんでした。

## 設計

- 固定の階層: `/<repo>`（概要表と全体設計）、`/<repo>/plan` と `/<repo>/bug`（一覧）、`/<repo>/plan/<id>-<slug>` と `/<repo>/bug/<id>-<slug>`（Work Item ID で命名する子ページ）。
- ルートページ: リポジトリ、既定ブランチ、インフラ（CLI、Azure PaaS、IaC の起点）、ビルド成果物、定義へのリンク付きの CI/CD、設計書の各行を持つ概要表と、最終形の全体設計を置きます。仕様を変える計画やバグ修正は、同じ登録の中でルートも更新します。
- 一覧ページ: Work Item・ページ・PR・状態・概要の列を持つ1つの表に、存在するすべての子ページを掲載します。
- 計画とバグのテンプレート: Work Item・ブランチ・PR・状態のメタデータ表に続けて、計画の各節、またはバグの症状・根本原因・修正方針・検証を書きます。バグページは Bug の修正方針が承認された時点で作成し、PR 行は PR 作成後に埋めます。
- PR は `!` で始まるテキストのリンクで書きます。Wiki ページ間は、ページ移動時にリンクを修復できる標準の Markdown リンクで結びます。本文の言語は既存 Wiki に合わせます。
- 非準拠ページは検出して対応案を示し、ユーザーの承認後にのみページ移動 API で移します。ページは削除しません。
- Boards スキルと Work Item エージェントは、承認済みの計画とバグ修正方針を Wiki スキルへ引き渡し、構造の作成は Wiki スキルの登録手順に委ねます。

## 実装

1. `azure-devops-wiki` スキルに、階層、登録手順、移行手順、4つのテンプレートを追加します。
2. Python と PowerShell の検証スクリプトに `--require-pr` と `--require-page-link` を追加し、テンプレートと PowerShell 版との一致を確かめる単体テストを追加します。
3. Boards スキルと Work Item エージェントの引き渡しを、バグ修正方針の登録を含めて更新します。
4. `.github` のミラー、CHANGELOG（英語と日本語）、プラグインのバージョン 0.3.0 を同期します。

## 検証

- PowerShell 7 との一致を含む検証スクリプトの単体テストと、マーケットプレースの検証を実行します。
- `plugins/azure-devops-toolkit` と `.github` のミラーがバイト単位で一致することを確認します。
- 各テンプレートにサンプル値を入れ、必須の Work Item・PR・ページリンクで検証を通ることを確認します。
