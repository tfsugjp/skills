# .NET ミューテーションテスト プラグイン

## 概要

`dotnet-mutation-testing` は、.NET の利用側リポジトリにある既存の MSTest 単体テストに対して、Stryker.NET のミューテーションテストを実行します。ミューテーションテストは多数のミュータントごとにビルドとテストを繰り返すため、プルリクエストを作成する直前に 1 回だけ、PR のベースブランチからの変更コードに限って実行します。通常の単体テストの実行は変更しません。

追跡: [Issue #113](https://github.com/tfsugjp/skills/issues/113)

## 設計

- 工程別のルール集である `dotnet-azure-lessons` とは別のプラグインにします。`dotnet-testing` と `pr-issue-workflow` からは、インストールされている場合に案内します。
- `dotnet-stryker` はリポジトリのローカルツールマニフェストで固定し、既存のマニフェストがあればそれを使います。グローバルにはインストールしません。固定する前に `nuget-validate` でバージョンを検証します。
- しきい値、生成コードの除外、`since.ignore-changes-in`（`stryker-config.json` 用）はルートの `stryker-config.json` に記述します。ベースブランチは PR ごとに変わるため、コマンドラインで `--since:origin/<base>` として渡します。`StrykerOutput/` は無視対象にします。利用側リポジトリにファイルを追加する前に確認します。
- リポジトリのルートの `global.json` から VSTest か Microsoft.Testing.Platform かを判定し、Stryker に `--test-runner` を渡します。Stryker の既定は VSTest です。
- 差分モードは未コミットの変更も含みます。Stryker がテストプロジェクトに属すると判断した C# 以外のファイルが変更されると、すべてのミュータントをテストします。補助ツールはログからこの切り替わりを検出してプロセスツリーを停止し、該当ファイルを一覧にして、明示的な `--allow-full-run` を求めます。実行時間の上限も設けます。
- レポートは固定の `--output` パスに出力します。Survived と NoCoverage のミュータント（ファイル、行、変異の種類、置換内容）を要約し、スコア 100% を目指さずに、リスクの高い生存ミュータントを検出する MSTest テストを提案します。合否は Stryker の exit code（`thresholds.break`）だけで判定します。
- 補助ツールは単一ファイルの C# アプリとし、スキルのディレクトリから解決します。利用側の .NET リポジトリにほかのランタイムやリポジトリ相対パスを必要としません。
- `dotnet test`、pre-commit フック、毎回のビルドを行う CI には組み込みません。任意のテンプレートは、対象の PR イベントまたは手動実行のときだけ動き、PR への通常の追加 push では実行しません。GitHub Actions はドラフトでない PR に対する `pull_request: types: [opened, reopened, ready_for_review]` または `workflow_dispatch` で `fetch-depth: 0`、Azure Pipelines は手動実行で `fetchDepth: 0` を使います。どちらも補助ツールのコピー（`eng/mutation-run.cs`）を呼び出すので、CI でも全件実行への切り替わりでの停止、実行時間の上限、ランナーの判定が働きます。ベースブランチ名は検証済みの環境変数で渡し、スクリプトの本文には直接埋め込みません。

## 検証

Microsoft Learn の `PriceCalculator` の例を基にしたサンプル（MSTest 4、net11.0、.NET SDK 11.0.100、Stryker.NET 5.1.0）で、全件実行（68.75%、記事と同じ 5 件の生存ミュータント）、ベースブランチとの差分実行、しきい値割れによる exit code 2、未コミットの C# 以外のファイルによる全件実行への切り替わり、`since.ignore-changes-in`、VSTest と MTP の両ランナー、補助ツールの要約を確認します。マーケットプレースのメタデータとスキル内の相対リンクは `scripts/validate_marketplaces.py` で検査します。
