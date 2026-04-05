# Slack Post Interceptor

Slack でメッセージを送信しようとしたとき、特定のキーワードを含む場合に送信をブロックして警告するmacOS専用ツール。

## 仕組み

1. **EventTap（Active）** でマウスクリック・キーボードイベントをグローバル監視する
2. 送信ボタンクリックまたは **Cmd+Enter** を検出したとき処理を開始する
   - 送信ボタン検出: クリック座標の周囲32×32pxをスクリーンキャプチャし、ボタン色（RGB: 22, 133, 103）を判定する
   - Cmd+Enter 検出: Shift+Enter（改行）は除外。通常の Enter（IME確定）は監視しない
3. AX（Accessibility API）でメッセージ本文を取得する
4. **警告キーワード**（「確認」「対応」）が含まれていれば送信をブロックしてダイアログを表示する
5. キーワードがなければそのまま送信を続行する
6. ダイアログ表示中は新たなインターセプトを行わず、警告を無視して送信したい場合は一度ダイアログを開いたまま再度送信操作を行う

## 要件

- macOS
- Slackアプリ
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- macOSの権限：**アクセシビリティ**、**画面収録**

## セットアップ

```bash
uv sync
```

## 起動

```bash
uv run src/main.py
# または
task start
```

初回起動時、権限が未付与の場合はダイアログが表示されます。  
**システム設定 > プライバシーとセキュリティ** でアクセシビリティと画面収録を許可してください。

## バックグラウンド実行

```bash
nohup uv run src/main.py &
echo $! > pid.txt
```

## 停止

```bash
kill $(cat pid.txt) &&
rm pid.txt
```

プロセスが残っている場合は以下で一括終了できます：

```bash
ps aux | grep "slack-post-interceptor.*main.py" | grep -v grep | awk '{print $2}' | xargs kill
```

## カスタマイズ

`.env` ファイルで設定を変更できます：

```env
LOG_LEVEL=INFO   # DEBUG / INFO / WARNING / ERROR
```

警告キーワードの変更は `src/event_tap.py` の `WARN_KEYWORDS` を編集してください：

```python
WARN_KEYWORDS: tuple[str, ...] = ("確認", "対応")
```

## アーキテクチャ

```
src/
├── main.py        # エントリポイント。権限チェックと起動
├── event_tap.py       # CGEventTap によるイベント監視・キーワードチェック
├── screen_capture.py  # スクリーンキャプチャによるボタン色判定
└── accessibility.py   # AX APIによるテキスト取得
```

### 技術的な背景

**なぜスクリーンキャプチャか**  
Slack（Electron製）のAXツリーは送信ボタン要素を安定的に返さないため、ピクセル色でボタンを検出している。

**なぜ Active タップか**  
Active タップのコールバックは軽量に保つ必要がある（タイムアウトで無効化されるため）。Slack 内の全 mouseDown をインターセプトし、バックグラウンドスレッドで `is_send_button_at()` を実行する。送信ボタン以外のクリックは即 repost するので体感遅延はほぼない。

**なぜ Cmd+Enter のみか**  
通常の Enter はIME確定（日本語変換）にも使われるため、誤検知を避けるため Cmd+Enter のみを送信ショートカットとして監視する。

**なぜ位置ベースのAX探索か**  
ボタンクリック時はフォーカスが移動するため `AXFocusedUIElement` が使えない。`AXUIElementCopyElementAtPosition` でクリック座標から要素を特定し、親を遡ってテキストエリアを探索している。Cmd+Enter 時はフォーカスが保持されているため `AXFocusedUIElement` を使う。
