# discord-notifier

RSSフィードやYouTubeチャンネルの新着を確認し、Discord webhookへ通知する小さなスクリプトです。

BBC、NHK、GizmodoなどのニュースRSSや、指定したYouTubeチャンネルを巡回して、新しい記事・動画だけをDiscordに投稿します。`discord-newsbot` と組み合わせると、ここで流したニュースをBot側で深掘り解説・日次要約できます。

## 主な機能

- YouTube新着通知
  - 指定したYouTubeチャンネルのRSSから最新動画を確認します。
  - 前回通知した動画と違う場合だけDiscordに送信します。

- RSS新着通知
  - BBC、NHK、GizmodoなどのRSSフィードを確認します。
  - 未通知の記事だけをDiscordに送信します。
  - 記事タイトル、概要、URLを投稿します。

- 重複通知の防止
  - `state.json` に通知済みの記事IDや動画IDを保存します。
  - RSSは最新200件分の通知済みIDを保持します。

## 構成

- `notify.py`
  - RSS/YouTubeの取得、新着判定、Discord webhook送信を行う本体です。
- `config.json`
  - 通知元の一覧を管理します。
  - `type` で `youtube` または `rss` を指定します。
  - `webhook` には `.env` 側のwebhook名を指定します。
- `state.json`
  - 前回どこまで通知したかを保存します。
- `.env`
  - Discord webhook URLなどの秘密情報を置きます。Git管理しない想定です。

## 必要な環境変数

`.env` に、`config.json` の `webhook` 名に対応するDiscord webhook URLを設定します。

例:

```env
DISCORD_WEBHOOK_BBC=...
DISCORD_WEBHOOK_NHK=...
DISCORD_WEBHOOK_GIZMODO=...
DISCORD_WEBHOOK_QUIZKNOCK=...
DISCORD_WEBHOOK_MAGUROHEAD=...
```

`config.json` で `"webhook": "bbc"` と書いた場合、スクリプトは `DISCORD_WEBHOOK_BBC` を探します。

## 設定例

```json
{
  "type": "rss",
  "name": "BBC Top Stories",
  "url": "https://feeds.bbci.co.uk/news/rss.xml",
  "webhook": "bbc"
}
```

```json
{
  "type": "youtube",
  "name": "QuizKnock",
  "channel_id": "UCQ_MqAw18jFTlBB-f8BP7dw",
  "webhook": "quizknock"
}
```

## 実行

```bash
python notify.py
```

定期実行したい場合は、cron、launchd、GitHub Actionsなどから `python notify.py` を呼び出す形にできます。

## 補足

- `.env` にはDiscord webhook URLが入るため、公開しないでください。
- `state.json` を消すと、過去の記事や動画が再通知される可能性があります。
- 通信エラーやRSS取得エラーが起きた場合は、対象ソース名とエラー内容を表示して次のソースへ進みます。
