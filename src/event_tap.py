from __future__ import annotations

import threading
import time
from typing import Any

import Quartz
from AppKit import NSAlert, NSApplication, NSPasteboard, NSPasteboardTypeString, NSWarningAlertStyle, NSWorkspace
from Foundation import NSObject, NSRunLoop, NSRunLoopCommonModes, NSTimer

from accessibility import SLACK_BUNDLE_ID, get_text_near_position
from screen_capture import is_send_button_at

_PREVIEW_MAX_LEN: int = 60
_RETRY_INTERVAL = 0.05
_RETRY_COUNT = 3

WARN_KEYWORDS: tuple[str, ...] = ("確認", "対応")

_click_queue: list[dict[str, Any]] = []
_repost_count: int = 0


def _schedule_timer(target: Any, selector: str) -> None:
    """NSRunLoopCommonModes でタイマーを登録する。"""
    timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
        0.0, target, selector, None, False
    )
    NSRunLoop.mainRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)


class _ClickProcessor(NSObject):
    """NSTimer 経由で次 RunLoop にクリック処理をバックグラウンドスレッドで起動する。"""

    def processClick_(self, _timer: Any) -> None:
        if _click_queue:
            info = _click_queue.pop(0)
            threading.Thread(
                target=_process_click,
                args=(info["x"], info["y"]),
                daemon=True,
            ).start()


class _MainThreadOps(NSObject):
    """バックグラウンドスレッドからメインスレッドのUI操作を呼び出すブリッジ。"""

    def copyAndRepost_(self, info: Any) -> None:
        _copy_to_clipboard(info["text"])
        _repost_click(info["x"], info["y"])

    def copyAndWarn_(self, info: Any) -> None:
        _copy_to_clipboard(info["text"])
        _show_keyword_warning(info["matched"])

    def repost_(self, info: Any) -> None:
        _repost_click(info["x"], info["y"])


_click_processor = _ClickProcessor.alloc().init()
_main_ops = _MainThreadOps.alloc().init()


class EventTapHandler:
    def __init__(self) -> None:
        self._tap: Any = None

    def start(self) -> None:
        mask = Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)

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
        global _repost_count
        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            print("[WARN] EventTap タイムアウト — 再有効化します")
            Quartz.CGEventTapEnable(self._tap, True)
            return None
        if event_type == Quartz.kCGEventLeftMouseDown:
            if _repost_count > 0:
                _repost_count -= 1
                return event
            if _is_slack_frontmost():
                loc = Quartz.CGEventGetLocation(event)
                _click_queue.append({"x": float(loc.x), "y": float(loc.y)})
                _schedule_timer(_click_processor, "processClick:")
                return None  # 抑制してバックグラウンドで判定
        return event


# ---------------------------------------------------------------------------
# Click processing — バックグラウンドスレッドで実行 (RunLoop をブロックしない)
# ---------------------------------------------------------------------------


def _process_click(x: float, y: float) -> None:
    if not is_send_button_at(x, y):
        _main_ops.performSelectorOnMainThread_withObject_waitUntilDone_("repost:", {"x": x, "y": y}, False)
        return

    text = None
    for _ in range(_RETRY_COUNT):
        text = get_text_near_position(x, y)
        if text:
            break
        time.sleep(_RETRY_INTERVAL)

    if not text:
        print("[DEBUG] テキスト取得失敗")
        _main_ops.performSelectorOnMainThread_withObject_waitUntilDone_("repost:", {"x": x, "y": y}, False)
        return

    matched = [kw for kw in WARN_KEYWORDS if kw in text]
    if matched:
        print(f"[INFO] キーワード検出: {matched} — 送信をブロック")
        _main_ops.performSelectorOnMainThread_withObject_waitUntilDone_(
            "copyAndWarn:", {"text": text, "matched": matched}, True
        )
    else:
        _main_ops.performSelectorOnMainThread_withObject_waitUntilDone_(
            "copyAndRepost:", {"text": text, "x": x, "y": y}, False
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repost_click(x: float, y: float) -> None:
    global _repost_count
    _repost_count += 1
    point = Quartz.CGPointMake(x, y)
    down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, point, Quartz.kCGMouseButtonLeft)
    up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, point, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGSessionEventTap, down)
    Quartz.CGEventPost(Quartz.kCGSessionEventTap, up)


def _is_slack_frontmost() -> bool:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app is not None and app.bundleIdentifier() == SLACK_BUNDLE_ID


def _show_keyword_warning(matched: list[str]) -> None:
    keywords = "、".join(f"「{kw}」" for kw in matched)
    alert = NSAlert.alloc().init()
    alert.setAlertStyle_(NSWarningAlertStyle)
    alert.setMessageText_("送信をブロックしました")
    alert.setInformativeText_(f"{keywords} が含まれています。\nメッセージを修正して再度送信してください。")
    alert.addButtonWithTitle_("OK")
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    alert.runModal()


def _copy_to_clipboard(text: str) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    preview = text[:_PREVIEW_MAX_LEN] + ("…" if len(text) > _PREVIEW_MAX_LEN else "")
    print(f"[COPY] {preview}")
