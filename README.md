# Slack Post Interceptor

Slack の送信ボタンをクリックしたとき、メッセージ本文をクリップボードに自動コピーするmacOS専用ツール。

## 仕組み

1. **EventTap（ListenOnly）** でマウスクリックをグローバル監視する
2. クリック座標の周囲32×32pxをスクリーンキャプチャし、Slackの送信ボタン色（RGB: 22, 133, 103）を検出する
3. ボタン検出時、AX（Accessibility API）でクリック座標付近のテキストエリアを探索してテキストを取得する
4. 取得したテキストをクリップボードにコピーし、送信はそのまま続行する

## 要件

- macOS
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- macOSの権限：**アクセシビリティ**、**画面収録**

## セットアップ

```bash
uv sync
```

## 起動

```bash
uv run main.py
# または
task start
```

初回起動時、権限が未付与の場合はダイアログが表示されます。  
**システム設定 > プライバシーとセキュリティ** でアクセシビリティと画面収録を許可してください。

## 開発

```bash
# Lint（自動修正あり）
task lint

# フォーマット
task format

# 型チェック
task type-check
```

## アーキテクチャ

```
src/slack_post_interceptor/
├── __main__.py        # エントリポイント。権限チェックと起動
├── event_tap.py       # CGEventTap によるマウス監視・コピー処理
├── screen_capture.py  # スクリーンキャプチャによるボタン色判定
└── accessibility.py   # AX APIによるテキスト取得
```

### 技術的な背景

**なぜ画像認識か**  
Slack（Electron製）のAXツリーは送信ボタン要素を安定的に返さないため、ピクセル色でボタンを検出している。

**なぜ ListenOnly タップか**  
アクティブタップのコールバックには1秒のタイムアウトがあり、重いスクリーンキャプチャ処理でタップが無効化される。ListenOnly はタイムアウト対象外のためこちらを使用している。

**なぜ位置ベースのAX探索か**  
ボタンクリック時はフォーカスが移動するため `AXFocusedUIElement` が使えない。`AXUIElementCopyElementAtPosition` でクリック座標から要素を特定し、親を遡ってテキストエリアを探索している。
