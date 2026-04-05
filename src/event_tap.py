from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

import Quartz
from AppKit import NSEvent, NSPasteboard, NSPasteboardTypeString, NSWorkspace

from accessibility import SLACK_BUNDLE_ID, get_text_near_position
from screen_capture import is_send_button_at

_PREVIEW_MAX_LEN: int = 60
_RETRY_INTERVAL = 0.05
_RETRY_COUNT = 3
_HOVER_INTERVAL = 0.2
_REPOST_TOLERANCE: float = 2.0

WARN_KEYWORDS: tuple[str, ...] = ("確認", "対応")

_over_btn: bool = False
_repost_pending: tuple[float, float] | None = None


class EventTapHandler:
    def __init__(self) -> None:
        self._tap: Any = None

    def start(self) -> None:
        threading.Thread(target=_hover_poller, daemon=True).start()

        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseUp)
        )
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            self._callback,
            None,
        )
        if self._tap is None:
            print("[ERROR] CGEventTap の作成に失敗しました。アクセシビリティ権限を確認してください。")
            raise SystemExit(1)

        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetMain(), source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)
        print("[INFO] 監視開始 — Slack 送信ボタンをクリックするとコピー後に送信します")

    def _callback(self, _proxy: Any, event_type: int, event: Any, _refcon: Any) -> Any:
        global _repost_pending

        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            print("[WARN] EventTap タイムアウト — 再有効化します")
            Quartz.CGEventTapEnable(self._tap, True)
            return None

        loc = Quartz.CGEventGetLocation(event)
        x, y = float(loc.x), float(loc.y)

        if event_type == Quartz.kCGEventLeftMouseUp:
            if _repost_pending is not None:
                px, py = _repost_pending
                if abs(x - px) < _REPOST_TOLERANCE and abs(y - py) < _REPOST_TOLERANCE:
                    return None
            return event

        # mouseDown
        if _repost_pending is not None:
            px, py = _repost_pending
            if abs(x - px) < _REPOST_TOLERANCE and abs(y - py) < _REPOST_TOLERANCE:
                _repost_pending = None
                return event

        if not _is_slack_frontmost():
            return event

        if not _over_btn:
            return event

        threading.Thread(target=_process_send, args=(x, y), daemon=True).start()
        return None


# ---------------------------------------------------------------------------
# ホバーポーラー (バックグラウンドスレッド)
# Slack フロント時のみスキャン、それ以外はフラグをリセット
# ---------------------------------------------------------------------------


def _hover_poller() -> None:
    global _over_btn
    while True:
        try:
            pos = NSEvent.mouseLocation()
            mx = float(pos.x)
            screen_h = float(Quartz.CGDisplayBounds(Quartz.CGMainDisplayID()).size.height)
            my = screen_h - float(pos.y)
            _over_btn = is_send_button_at(mx, my)
        except Exception as e:
            print(f"[ERROR] hover_poller: {e}")
        time.sleep(_HOVER_INTERVAL)


# ---------------------------------------------------------------------------
# 送信処理 (バックグラウンドスレッド)
# ---------------------------------------------------------------------------


def _process_send(x: float, y: float) -> None:
    text = None
    for _ in range(_RETRY_COUNT):
        text = get_text_near_position(x, y)
        if text:
            break
        time.sleep(_RETRY_INTERVAL)

    print(f"[DEBUG] text={repr(text[:20]) if text else None}")

    if not text:
        print("[DEBUG] テキスト取得失敗 — 送信を続行します")
        _do_repost(x, y)
        return

    matched = [kw for kw in WARN_KEYWORDS if kw in text]
    if matched:
        print(f"[INFO] キーワード検出: {matched} — 送信をブロック")
        _copy_to_clipboard(text)
        _show_osascript_alert(matched)
    else:
        _copy_to_clipboard(text)
        print("[INFO] クリップボードにコピー済み — 送信を続行します")
        _do_repost(x, y)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_slack_frontmost() -> bool:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app is not None and app.bundleIdentifier() == SLACK_BUNDLE_ID


def _do_repost(x: float, y: float) -> None:
    global _repost_pending
    _repost_pending = (x, y)
    point = Quartz.CGPointMake(x, y)
    down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, point, Quartz.kCGMouseButtonLeft)
    up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, point, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)


def _show_osascript_alert(matched: list[str]) -> None:
    keywords = "、".join(f"「{kw}」" for kw in matched)
    script = (
        f'display alert "送信をブロックしました" '
        f'message "{keywords} が含まれています。\\nメッセージを修正して再度送信してください。" '
        f'buttons {{"OK"}} default button "OK"'
    )
    subprocess.run(["osascript", "-e", script], check=False)
    subprocess.run(["osascript", "-e", 'tell application "Slack" to activate'], check=False)


def _copy_to_clipboard(text: str) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    preview = text[:_PREVIEW_MAX_LEN] + ("…" if len(text) > _PREVIEW_MAX_LEN else "")
    print(f"[COPY] {preview}")
