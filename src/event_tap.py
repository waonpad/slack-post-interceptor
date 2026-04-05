from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

import Quartz
from AppKit import NSWorkspace

from accessibility import SLACK_BUNDLE_ID, get_focused_text, get_text_near_position
from log import logger
from screen_capture import is_send_button_at

_RETRY_INTERVAL = 0.05
_RETRY_COUNT = 3
_REPOST_TOLERANCE: float = 2.0
_REPOST_TIMEOUT: float = 0.5

WARN_KEYWORDS: tuple[str, ...] = ("確認", "対応")

_KEYCODE_RETURN = 36
_KEYCODE_NUMPAD_ENTER = 76
_FLAG_SHIFT = Quartz.kCGEventFlagMaskShift
_FLAG_CMD = Quartz.kCGEventFlagMaskCommand

_repost_pending: tuple[float, float] | None = None
_enter_repost_pending: bool = False


class EventTapHandler:
    def __init__(self) -> None:
        self._tap: Any = None

    def start(self) -> None:
        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseUp)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
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
            logger.error("CGEventTap の作成に失敗しました。アクセシビリティ権限を確認してください。")
            raise SystemExit(1)

        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetMain(), source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)
        logger.info("監視開始 — Slack 送信ボタンをクリックするとキーワードをチェックします")

    def _callback(self, _proxy: Any, event_type: int, event: Any, _refcon: Any) -> Any:
        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            logger.warning("EventTap タイムアウト — 再有効化します")
            Quartz.CGEventTapEnable(self._tap, True)
            return None

        if event_type == Quartz.kCGEventKeyDown:
            return self._handle_key(event)

        loc = Quartz.CGEventGetLocation(event)
        x, y = float(loc.x), float(loc.y)
        return self._handle_mouse(event_type, event, x, y)

    def _handle_key(self, event: Any) -> Any:
        global _enter_repost_pending
        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        flags = Quartz.CGEventGetFlags(event)
        is_enter = keycode in (_KEYCODE_RETURN, _KEYCODE_NUMPAD_ENTER)
        is_cmd_enter = is_enter and bool(flags & _FLAG_CMD) and not (flags & _FLAG_SHIFT)
        if is_cmd_enter:
            if _enter_repost_pending:
                _enter_repost_pending = False
                return event
            if _is_slack_frontmost():
                threading.Thread(target=_process_send_keyboard, daemon=True).start()
                return None
        return event

    def _handle_mouse(self, event_type: int, event: Any, x: float, y: float) -> Any:
        global _repost_pending
        if event_type == Quartz.kCGEventLeftMouseUp:
            if _repost_pending is not None:
                px, py = _repost_pending
                if abs(x - px) < _REPOST_TOLERANCE and abs(y - py) < _REPOST_TOLERANCE:
                    return None
            return event

        # mouseDown: repost のものはそのまま通す
        if _repost_pending is not None:
            px, py = _repost_pending
            if abs(x - px) < _REPOST_TOLERANCE and abs(y - py) < _REPOST_TOLERANCE:
                _repost_pending = None
                return event

        if not _is_slack_frontmost():
            return event

        # Slack 内の全 mouseDown をインターセプトし、バックグラウンドでボタン判定
        threading.Thread(target=_process_send, args=(x, y), daemon=True).start()
        return None


# ---------------------------------------------------------------------------
# 送信処理 (バックグラウンドスレッド)
# ---------------------------------------------------------------------------


def _process_send(x: float, y: float) -> None:
    # まずボタン判定 — 非ボタンクリックは即 repost して終了
    if not is_send_button_at(x, y):
        _do_repost(x, y)
        return

    text = None
    for _ in range(_RETRY_COUNT):
        text = get_text_near_position(x, y)
        if text:
            break
        time.sleep(_RETRY_INTERVAL)

    if not text:
        logger.debug("テキスト取得失敗 — 送信を続行します")
        _do_repost(x, y)
        return

    matched = [kw for kw in WARN_KEYWORDS if kw in text]
    if matched:
        logger.info("キーワード検出: %s — 送信をブロック", matched)
        _show_osascript_alert(matched)
    else:
        logger.info("キーワードなし — 送信を続行します")
        _do_repost(x, y)


def _process_send_keyboard() -> None:
    text = None
    for _ in range(_RETRY_COUNT):
        text = get_focused_text()
        if text:
            break
        time.sleep(_RETRY_INTERVAL)

    if not text:
        logger.debug("テキスト取得失敗 — 送信を続行します")
        _repost_enter()
        return

    matched = [kw for kw in WARN_KEYWORDS if kw in text]
    if matched:
        logger.info("キーワード検出: %s — 送信をブロック", matched)
        _show_osascript_alert(matched)
    else:
        logger.info("キーワードなし — 送信を続行します")
        _repost_enter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_slack_frontmost() -> bool:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app is not None and app.bundleIdentifier() == SLACK_BUNDLE_ID


def _do_repost(x: float, y: float) -> None:
    global _repost_pending
    _repost_pending = (x, y)
    threading.Timer(_REPOST_TIMEOUT, _clear_repost_pending).start()
    point = Quartz.CGPointMake(x, y)
    down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, point, Quartz.kCGMouseButtonLeft)
    up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, point, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)


def _clear_repost_pending() -> None:
    global _repost_pending
    _repost_pending = None


def _repost_enter() -> None:
    global _enter_repost_pending
    _enter_repost_pending = True
    threading.Timer(_REPOST_TIMEOUT, _clear_enter_repost_pending).start()
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    down = Quartz.CGEventCreateKeyboardEvent(src, _KEYCODE_RETURN, True)
    up = Quartz.CGEventCreateKeyboardEvent(src, _KEYCODE_RETURN, False)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)


def _clear_enter_repost_pending() -> None:
    global _enter_repost_pending
    _enter_repost_pending = False


def _show_osascript_alert(matched: list[str]) -> None:
    keywords = "、".join(f"「{kw}」" for kw in matched)
    script = (
        f'display alert "送信をブロックしました" '
        f'message "{keywords} が含まれています。\\nメッセージを修正して再度送信してください。" '
        f'buttons {{"OK"}} default button "OK"'
    )
    subprocess.run(["osascript", "-e", script], check=False)
    subprocess.run(["osascript", "-e", 'tell application "Slack" to activate'], check=False)

