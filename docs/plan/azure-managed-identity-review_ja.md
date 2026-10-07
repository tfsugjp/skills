# Azure Managed Identity Review プラグイン

## 概要

`azure-managed-identity-review` は、Azure のマネージド ID を、それを共有するすべてのリソース・アプリ設定・コード・フェデレーション資格情報（FIC）を横断してレビューします。ユーザー割り当て ID は、あるリソース用（たとえばストレージのカスタマーマネージドキー）に作られたあと、ほかのリソース（Function App や GitHub Actions のワークフロー）でも使い回されがちです。最初の用途で付けた権限は、ほかの利用者が使う audience（Service Bus、SQL、Cosmos DB データプレーン、独自 API）をカバーせず、その利用者だけにとどまりもしません。しかもローカル E2E は開発者本人の権限で動くため、権限漏れはデプロイ後にしか現れません。追跡: 親 issue #91、サブ issue #92-#95。

## 設計

- 読み取り専用のスクリプト `scripts/msi_review.py`（Python 3.9 以上、標準ライブラリのみ）を一つ用意し、二つの収集器で同じモデルを構築します。モデルは、ID、利用者（`identity` に ID を持つリソース、または CMK・Key Vault 参照・イメージ取得・kubelet などのプロパティで ID を参照するリソース）、ターゲット（各利用者がどの ID で何にアクセスするか）、権限（Azure RBAC、Cosmos DB SQL ロール割り当て、Key Vault アクセスポリシー）、FIC です。
- `static <path>` は Bicep のエントリファイル（モジュールとして参照されていないファイル）を `bicep build --stdout` または `az bicep build --stdout` でコンパイルし、任意のデプロイスコープの ARM JSON を読み取り（ソースの隣にある Bicep 生成 JSON は除外）、渡されたパラメーターつきで入れ子のデプロイを再帰的に処理し、ARM 式（`parameters`、`variables`、`format`、`concat`、`resourceId`、`extensionResourceId`、`reference(...).principalId/clientId`）とリテラルのリソース ID を評価します。解決できない名前は安定した `{param:...}` ラベルを保ち、MIR000 の注記になります。Terraform は波かっこを追跡する HCL リーダー（文字列、ヒアドキュメント、コメント対応）で解析するか、`terraform show -json` から読み取ります（参照は `configuration`、マップの値は `planned_values` から取得）。`--parameters` は ARM パラメーター JSON（`bicep build-params` の出力）を受け付けます。ソースコードと `local.settings.json` は、資格情報クラス、トークンのスコープ、サービスのホスト名を検索します。コードは `--map <dir>=<resource>` でリソースに対応付けます。アプリと Functions プロジェクトがそれぞれ一つだけのときは自動で対応付けます。
- `live --subscription <id>` は読み取り専用の `az` 呼び出しだけを使います。Resource Graph は UTF-8 の `--body @<file>` を渡す `az rest` で照会し（拡張機能は不要）、`az role assignment list --assignee-object-id --all --include-inherited --fill-principal-name false`（Microsoft Graph を呼ばない）、`az identity federated-credential list`、`az webapp config appsettings list`、Cosmos DB のターゲットがある場合は `az cosmosdb sql role assignment list` を使います。アプリ設定の値は、ID の設定、GUID、サービスのエンドポイント以外をマスクします。エンドポイントはホストとパスを残しますが、クエリ文字列は残しません。接続文字列と SAS URL は常にマスクします。`--record`/`--replay` はマスク済みの出力を保存・再利用し、`--static <path>` はドリフトの指摘を追加します。
- ID の選択はプラットフォームの動作に合わせます。Functions の接続は `<prefix>__clientId`/`__managedIdentityResourceId`、なければシステム割り当て ID を使います。SDK のコードは `AZURE_CLIENT_ID`、なければ割り当て済み ID のクライアント ID を持つ設定（エンドポイント設定と名前の接頭辞が最も長く一致するもの）、なければシステム割り当て ID を使います。Key Vault 参照は `keyVaultReferenceIdentity`、なければシステム割り当て ID を使います。
- 権限がターゲットをカバーするのは、ロールがそのサービスのデータロール（組み込みロールの ID と名前は `az role definition list` で確認済み、AI サービスのロールは Cognitive Services のデータアクションで選定）であり、スコープがターゲットのリソースかそれより広い場合です。ターゲットの子リソース（コンテナー、キュー、シークレット、Foundry プロジェクト）に対する権限は、利用者が使うエンドポイントがその子を指す場合だけ有効とみなします。ターゲット名は、設定値、Key Vault 参照の `VaultName=`/`SecretUri=`、レジストリのログインサーバー、CMK の Key Vault URI から取得します。`*.servicebus.*` のホストは、名前空間のリソースの種類が Event Hubs であれば Event Hubs とみなします。SQL、Graph、独自 API、データプレーンの割り当てがない Cosmos DB には RBAC 以外の権限付与が必要です。
- 規則: MIR000 解決できない参照（注記）、MIR001 複数のリソースに割り当てられた ID、MIR002 カバーする権限がないターゲット（接続とプラットフォームのスロットはエラー、URL やコードからの推定、または権限がターゲットの子リソースにしかない場合は警告）、MIR003 共有 ID に付いた広いスコープや特権の権限、または一つの利用者だけが必要とする権限（FIC があれば警告、なければ情報）、MIR004 リソースが使う ID の FIC、標準外の FIC audience、柔軟なサブジェクト照合、MIR005 クライアント ID が指定されず、システム割り当て ID がない（エラー）または意図した ID でない（警告）、またはクライアント ID がリソースのどの ID とも一致しない（警告）、MIR006 確認が必要な RBAC 以外の権限（情報）、MIR007 ローカルでは開発者として動くコードやローカル設定（情報）、MIR008 Azure と IaC のドリフト。情報と注記だけなら終了コード 0、警告かエラーがあれば 1、入力エラーは 2 です。
- 出力は Markdown レポート（ID ごとに、利用者と用途、権限とそれを必要とする利用者、FIC、続いて修正方法つきの指摘）または `--json` です。`--resource` はそのリソースが使う ID と、その ID のほかのすべての利用者をレビューし、`--identity` は ID（名前またはリソース ID）を起点にします。スキルがロール割り当て・FIC・ID を作成することはなく、修正は IaC の変更として提案します。

## 検証

- `python3 scripts/validate_marketplaces.py` で plugin のメタデータとリンクを検証します。
- `tests/test_msi_review.py`（unittest、既存の Ubuntu の `tests` ジョブで実行）は次を検証します。リテラルの ID を含むサブスクリプションスコープのテンプレート、別の Key Vault・レジストリ・子リソースに対する権限、Event Hubs の判定を確認します。正規シナリオ（ストレージ CMK 用の ID を Function App が Service Bus 用に使い回し、GitHub Actions の FIC からも信頼されている）はコンパイル済み ARM、Terraform、コードつき Bicep（スタンドアロンの `bicep` CLI がなければスキップ）で確認します。さらに、ID の選択、RBAC 以外のターゲット、独自名のクライアント ID 設定、指摘のないクリーンな構成、解決できない参照、Terraform の plan JSON、ドリフトを含む記録済みの live 出力、ARM 式の評価器、HCL リーダー、マスク処理を確認し、すべての規則 MIR000-MIR008 に検出例のフィクスチャがあることも確かめます。
- 実際のサブスクリプションに対する読み取り専用の live 実行で、`az` の引数、マスク処理、ID の推定を確認しました。
