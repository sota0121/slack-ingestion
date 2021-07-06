# Ingest slack data scripts

## Setup

- `source ./setup-environ.sh`
  - Slackにアクセスするためのキー情報を環境変数に設定するスクリプトを実行します
  - 実行前にSlackにアクセスするために必要なキーを取得、設定してください
- create virtual env from `requirements.txt`
  - 実行に必要なパッケージをrequirements.txtに記載しているので、仮想環境を作るなりして、
  - 各パッケージをインストールしてください。

<br>

## Run : `gen_call_functions_sh.py`

メインSlackデータ取得スクリプトである `main.py` は、取得したいログの期間を指定するために、UNIX時間（実数）を指定する必要があります。手動でその時刻を設定するのは難しいので、「開始日付（YYYY-MM-DD）」「終了日付（YYYY-MM-DD）」を入力すると、指定のUNIX時間を引数とする `main.py` の呼び出しスクリプトを生成する支援ツールを作りました。

- `python gen_call_functions_sh.py 2021-01-01 2021-01-05`
  - 2021-01-01 0時 〜 2021-01-05 0時までのSlack会話データを取得したい場合
  - `call_functions_batch.sh` が出力されます

<br>

## Run : `main.py`

- `./call_functions_batch.sh` と入力して実行してください
  - 権限関係で実行できない場合は、`chmod +x ./*.sh` として実行権限を付与してください

<br>

## Result

以下のような出力になります。

```
ROOT/slack_lake/daily-ingest_target-date_YYYY-MM-DD
    - conversations_list.json
    - users_list.json
    - conversations_history.json
    - ingest_log_at_YYYY-MM-DDThh:mm:ss.ssss
```

以下、解説

- daily-ingest_target-date_YYYY-MM-DD
  - 1日ごと読み込んだSlackデータの保存先ディレクトリ
  - `YYYY-MM-DD` には取得したSlackデータの属する日付が入ります。処理実行時刻とは関係ないです。
- conversations_list.json
  - [conversations.list API](https://api.slack.com/methods/conversations.list) で取得したデータが入っています。
- users_list.json
  - [users.list API](https://api.slack.com/methods/users.list) で取得したデータが入っています。
- conversations_history.json
  - [conversations.history API](https://api.slack.com/methods/conversations.history) で取得したデータが入っています。
- ingest_log_at_YYYY-MM-DDThh:mm:ss.ssss
  - APIでのデータロード処理のログが記載されています
  - `YYYY-MM-DDThh:mm:ss.ssss` は処理実行開始時刻です。

