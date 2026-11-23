# Visual Studio 拡張機能と WPF XAML プラグイン

## 概要

`visual-studio-extension` は、VisualStudio.Extensibility と Remote UI で作る out-of-process の Visual Studio 拡張機能について、確認可能な規則をまとめます。`wpf-xaml` は WPF の規則を、Remote UI での例外とあわせてまとめます。Remote UI のバインド、シリアライズ、選択、レイアウトの規則は `dotnet-azure-lessons/vs-extension-remote-ui` に置きます。

追跡: [Issue #120](https://github.com/tfsugjp/skills/issues/120)

## プラグインとスキル

| プラグイン | スキルまたはエージェント | 範囲 |
|---|---|---|
| `visual-studio-extension` | `vs-extensibility-project` | ホスティングの選択、コードによるコマンド定義、Extensibility SDK のビルドエラー、Remote UI XAML の埋め込み、`.vsextension` のローカライズ、テストプロジェクトのターゲットフレームワーク、設定、VSIX マニフェスト |
| `visual-studio-extension` | `vs-extension-deployment` | SDK が管理する F5、LoaderLock MDA、Experimental Instance の重複 ID、パッケージ後の VSIX の検証、End-to-End のハッシュ比較、`ActivityLog.xml`、VSIX のロックへの対処 |
| `visual-studio-extension` | `vs-extension-lifecycle` | 冪等な Dispose、診断出力の読み取りタスクの所有、ワーカーの起動と停止の直列化、一度だけ実行される非同期の後処理 |
| `visual-studio-extension` | `vs-extension-remote-ui-theming` | 自動テーマ適用を優先、Visual Studio 2026 の `ShellColors` トークン、`DynamicResource`、状態ごとの前景色と背景色の対、コントロールスタイルの載せ替え、テーマの確認 |
| `visual-studio-extension` | `vs-extension-oauth` | パブリッククライアントのサインイン: 範囲内のときだけ設定値を聞く、クライアントシークレットを持たない、MSAL のサイレント優先、親ウィンドウ付きの WAM ブローカー、他プロバイダーでの PKCE、暗号化したトークンキャッシュ |
| `visual-studio-extension` | エージェント `vs-extension-reviewer` | 読み取り専用の差分レビュー。上記スキル、`vs-extension-remote-ui`、`wpf-xaml`、`nuget-validate` に振り分け、導入されていないスキルを報告 |
| `wpf-xaml` | `wpf-xaml` | WPF の適用判定、MVVM、CommunityToolkit.Mvvm、Dispatcher のスレッド、仮想化、Freezable、リソース、テーマカラー、アクセシビリティ |
| `dotnet-azure-lessons` | `vs-extension-remote-ui` | シリアライズの規則（`[DataContract]`、`IAsyncCommand`、public な `CanExecute`、データコンテキストへのバインドの検証）と、`CanContentScroll` と仮想化のトレードオフを追加 |

## 設計判断

- **2つのプラグイン。** WPF だけのプロジェクトは、Visual Studio 拡張機能の規則なしで `wpf-xaml` を導入できます。
- **規則ごとに正本は1つ。** Remote UI のバインドとシリアライズの規則は `vs-extension-remote-ui` だけに、テーマキーとコントロールスタイルは `vs-extension-remote-ui-theming` だけに、WPF 一般の規則は `wpf-xaml` だけに置きます。他のスキルは正本を参照します。
- **プラグインをまたぐ参照は名前で。** 各プラグインは単体で導入でき、相対リンクはプラグインのルートを出られないため、関連スキルはプラグイン名とともに「導入されている場合」として示します。
- **根拠の表示。** Microsoft Learn に裏付けのある規則は、理由の中でそう示します。Extensibility SDK のアナライザーのコードや SDK のシリアライズの内部挙動のように、実際の失敗に基づき Microsoft Learn に記載のない規則には「observed in practice」と付けます。
- **現行のテーマトークン。** Visual Studio 2026 では、`EnvironmentColors`、`CommonControlsColors`、`TreeViewColors` が `ShellColors` に置き換わりました。新しい UI は `ShellColors` を使い、旧キーはサポート範囲に古いバージョンが含まれ、そこで全キーの存在を確認した場合だけ残します。
- **WPF の規則に Remote UI の例外を明記。** 生成される `[RelayCommand]` は `IAsyncCommand` ではなく、`[ObservableProperty]` のフィールドには `[property: DataMember]` が必要で、`StaticResource` の優先、`Freeze`、マージされたディクショナリは Remote UI の共有リソースには当てはまりません。
- **製品固有の内容を含めない。** 規則には元のプロジェクトの製品、発行者、拡張機能 ID、クラス、テストの名前を書かず、フレームワークや SDK のバージョンも固定せず、リポジトリが固定したバージョンを参照します。
- **承認ゲート。** Experimental Instance から古い ID を削除するには対象を特定した承認が必要で、Experimental Instance 全体のリセットには別の承認が必要です。VSIX をロックしているプロセスの停止は、現在のビルドのプロセスに限ります。
- **OAuth の設定値は条件付き。** プロバイダー、クライアント ID、authority、スコープ、リダイレクト URI は、サインインを追加または変更する作業のときだけ聞きます。

## 検証

- `scripts/validate_marketplaces.py` が成功すること。
- 新規・変更ファイルに元資料の製品固有の識別子が残っていないこと。
- `vs-extension-reviewer` と `AGENTS.md` に書いたスキルがすべてこのリポジトリに存在すること。
