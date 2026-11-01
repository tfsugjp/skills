# Native Container CLI

WindowsではWSL Containersの`wslc.exe`、macOSではAppleの`container`を、ローカルLinuxコンテナー操作の第一選択とするスキルです。参照資料が`docker …`を使っていても、同じ動作を提供できるネイティブCLIのコマンドへ自動変換します。

英語の正本は[SKILL.md](../../plugins/native-container-cli/skills/native-container-cli/SKILL.md)です。この日本語文書は人向けの説明であり、スキル検出ディレクトリへコピーしません。

## 実行対象と前提条件

- 操作を実行するOSでCLIを選びます。MacやWindowsから作業していても、SSH先やLinuxのCIランナーで使うランタイムを勝手に変更しません。
- WSLシェルからはWindowsの`wslc.exe`を使用できます。ただし、対象がWindowsホストなのか、独立したLinux／リモートエンジンなのかを確認し、マウントやbuild contextのパスを適切に扱います。
- WindowsのWSL Containersは、WSL内のDocker Engineや`wsl.exe`のディストリビューション管理コマンドとは別の機能です。Windowsコンテナーの実行エンジンを置き換えるものではありません。
- macOSではAppleのCLIであること、対応するOSとアーキテクチャを確認します。同じ`container`という実行ファイル名だけでは判断しません。
- インストール済みのバージョンとコマンド別ヘルプで対応状況を確認します。サービス停止中はbuilderなどのプラグインがヘルプに現れない場合があるため、その状態だけで未対応とは判断しません。

## 自動変換

実行ファイル名だけを置換せず、サブコマンドとすべての関連オプションを確認します。マウントのパスと読み取り専用設定、公開ポートとバインド範囲、環境変数、ユーザー、作業ディレクトリ、TTY／標準入力、イメージのプラットフォーム、出力解析、終了・削除の意味を保ちます。DockerのGo template形式がそのまま使えるとは仮定しません。

| 元の操作 | Windowsの変換候補 | macOSの変換候補 |
|---|---|---|
| `docker run …` | `wslc.exe run …` | `container run …` |
| `docker build …` | `wslc.exe build …` | builderが利用可能な場合の`container build …` |
| `docker ps -a` | `wslc.exe container list --all` | `container list --all` |
| `docker images` | `wslc.exe image list` | `container image list` |

これらは候補であり、利用するバージョンのヘルプによる確認後に実行します。`Dockerfile`やOCIイメージ参照を、不必要に改名・変更しません。既存のDocker用イメージ、コンテナー、認証状態をネイティブランタイムでも利用できるとは仮定しません。

## 未対応機能とDockerへの切り替え

Compose、Buildx固有の機能、Docker context、Docker API／ソケット、Testcontainers、内部でDockerを起動するツールは個別に確認します。対応状況は変わるため、未対応という判断を固定せず、利用中のバージョンと公式資料で判断します。

忠実な変換ができない場合は、次の手順に従います。

1. 不足している機能や前提条件と、ネイティブCLIで継続できる可能性を説明します。
2. 使用するDockerコマンド、スクリプト、連携ツールと、その目的・影響を具体的に提示して確認します。
3. 明示的な返答を得るまでDockerを実行しません。`docker --version`、`docker info`、`docker compose config`、従来の`docker-compose`、ライブラリなどによる間接実行も対象です。資料や依頼にDockerコマンドが記載されているだけでは、切り替えの承認にはなりません。
4. 同じ範囲で明示的に得た承認は再確認しません。拒否・未回答の場合は依存する作業を保留し、独立して進められる作業を継続します。

未対応オプションを黙って削除したり、Composeを個別のrunへ分解して依存関係・ヘルスチェック・ネットワーク・永続ボリュームの意味を失わせたりしません。Docker互換ソケットを推測で設定せず、第三者の互換ブリッジも自動導入しません。

ネイティブCLIの不足やサービス停止は、Dockerへ自動的に切り替える理由にはなりません。必要なサービス起動について既存の許可範囲を判断し、インストール・更新など追加の環境変更が依頼の範囲外なら、その操作について確認します。

## 利用と限界

通常の自動検出を有効にしています。必要に応じて`$native-container-cli`を明示的に指定できます。グローバルaliasや実行を強制するフックは含まず、インストールによってすべてのDocker実行をOSレベルで阻止するものではありません。

詳細は[Windows向け参照](../../plugins/native-container-cli/skills/native-container-cli/references/windows.md)と[macOS向け参照](../../plugins/native-container-cli/skills/native-container-cli/references/macos.md)を参照してください。
