# SimpleMusicBot (Refactored)

py-cord製のDiscord音楽Bot。[HandledQuest/SimpleMusicBot](https://github.com/HandledQuest/SimpleMusicBot) をベースに、マルチサーバー対応・非同期化・セキュリティ強化を中心とした大規模リファクタを行ったものです。

## 主な特徴

- **マルチサーバー対応**: ギルドごとに再生キュー・音量・再生状態を分離(`GuildPlayer`)。複数のDiscordサーバーで同時運用してもキューが混ざりません。
- **非同期I/O**: `yt-dlp`や歌詞検索(`lyricsgenius`)などのブロッキング処理はすべて`run_in_executor`でスレッドプールに逃がし、イベントループを止めません。
- **セキュリティ**: `/url`コマンドのURLはhttp(s)以外のスキームやlocalhost・プライベートIP・クラウドメタデータアドレスへのアクセスを拒否します(SSRF対策)。トークン類は`.env`で管理し、リポジトリにコミットされません。
- **ロギング**: `print`は使わず標準`logging`に統一。コンソールと`logs/simplemusicbot.log`の両方に出力されます。
- **テスト**: `pytest`によるユニットテストを同梱(キュー操作・マルチギルド分離・URL検証・エラーハンドリング)。

## コマンド一覧

| コマンド | 説明 |
|---|---|
| `/url <url>` | 指定したURLの音楽を再生(キューに追加)します |
| `/yt <query>` | キーワードでYouTube検索し、一番上の結果を再生します |
| `/stp` | 再生を停止してボイスチャンネルから退室します |
| `/vol <percent>` | 音量を調整します(パーセント指定) |
| `/skp` | 現在の曲をスキップします |
| `/qe` | 現在のキューを表示します |
| `/nop` | 現在再生中の曲を表示します |
| `/nsp <position>` | 指定した番号の曲をキューから削除します |
| `/ly [title]` | 歌詞を表示します(省略時は再生中の曲) |

## セットアップ

### 1. 前提条件

- Python 3.10以上(開発・動作確認はPython 3.12〜3.13で実施)
- [FFmpeg](https://ffmpeg.org/download.html) がインストールされ、PATHが通っていること
- Discord Botトークン([Discord Developer Portal](https://discord.com/developers/applications)で取得)
- (任意)歌詞検索を使う場合は[Genius APIトークン](https://genius.com/api-clients)

### 2. インストール

```bash
git clone https://github.com/HandledQuest/SimpleMusicBot.git
cd SimpleMusicBot
pip install -r requirements.txt
```

### 3. 設定

初回に一度 `python bot.py` を実行すると `.env.example` が自動生成されます。これをコピーして `.env` を作成し、値を埋めてください。

```bash
cp .env.example .env
```

```ini
# .env
DISCORD_BOT_TOKEN=あなたのBotトークン
GENIUS_TOKEN=                  # 任意。歌詞検索を使わない場合は空のままでOK
DEFAULT_VOLUME=0.2
DEV_MODE=false
UPDATE_CHECK=true
LOG_LEVEL=INFO
```

> **Note:** 設定は 環境変数/`.env` > `config/simplemusicbot/config.ini` > デフォルト値 の優先順位で解決されます。旧バージョンの `config.ini` をお使いの場合、トークン以外の項目(音量、ステータス文言など)はそのまま引き継がれます。トークンは `.env` での管理を推奨しているため、`config.ini` 側に書かれていても `.env` の値が優先されます。

### 4. Botの招待

Discord Developer Portalの「Bot」タブで以下の Privileged Gateway Intents を**有効にする必要はありません**(本リファクタでは不要な権限を要求しない設計にしています)。OAuth2 URL生成では `bot` と `applications.commands` スコープ、権限は「メッセージを送信」「ボイスチャンネルに接続」「ボイスチャンネルで発言」程度で十分です。

### 5. 起動

```bash
python bot.py
```

正常に起動すると以下のようなログが出力されます。

```
2026-06-19 12:00:00 [INFO] bot: ログインしました: YourBot#1234 (ID: ...)
```

## テストの実行

```bash
pip install -r requirements.txt  # pytest, pytest-asyncio を含む
pytest tests/ -v
```

## ディレクトリ構成

```
.
├── bot.py                  # エントリポイント。設定読込・Cog登録・起動処理
├── config.py                # pydantic-settingsベースの設定管理
├── errors.py                 # 共通エラーハンドラ・安全な応答ユーティリティ
├── logging_setup.py          # logging初期化(コンソール+ファイル出力)
├── update.py                 # GitHub Releases経由の更新チェック(非同期)
├── music/
│   ├── manager.py            # GuildPlayer / GuildPlayerManager(ギルドごとの状態管理)
│   └── source.py              # yt-dlp抽出の非同期ラッパー、URL検証(SSRF対策)
├── cogs/
│   ├── playback.py            # 再生系スラッシュコマンド
│   └── lyrics.py               # 歌詞検索コマンド
├── tests/                     # pytestテストスイート
├── requirements.txt
└── .gitignore
```

## トラブルシューティング

- **`MissingVoiceDependenciesError` が出る**: `pip install "py-cord[voice]"` でボイス関連の依存(PyNaCl等)を導入してください。
- **`/url`などのコマンドで応答が返ってこない・エラーになる**: FFmpegがインストールされ、PATHが通っているか確認してください。
- **歌詞が取得できない**: `.env`の`GENIUS_TOKEN`が未設定の場合、`/ly`コマンドはその旨を案内して終了します。

## ライセンス

元プロジェクト([HandledQuest/SimpleMusicBot](https://github.com/HandledQuest/SimpleMusicBot))のライセンスに準拠します。リポジトリ内のLICENSEファイルを参照してください。
