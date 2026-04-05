from __future__ import annotations

import time
from typing import Any

import Quartz
from AppKit import NSPasteboard, NSPasteboardTypeString, NSWorkspace

from slack_post_interceptor.accessibility import SLACK_BUNDLE_ID, get_text_near_position
from slack_post_interceptor.screen_capture import is_send_button_at

_PREVIEW_MAX_LEN: int = 60
_RETRY_INTERVAL = 0.05
_RETRY_COUNT = 3


class EventTapHandler:
    def __init__(self) -> None:
        self._tap: Any = None

    def start(self) -> None:
        mask = Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)

        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
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
        if event_type == Quartz.kCGEventLeftMouseDown:
            self._handle_mouse_down(event)
        return event

    def _handle_mouse_down(self, event: Any) -> None:
        if not _is_slack_frontmost():
            return

        loc = Quartz.CGEventGetLocation(event)
        x, y = float(loc.x), float(loc.y)

        if not is_send_button_at(x, y):
            return

        text = None
        for _ in range(_RETRY_COUNT):
            text = get_text_near_position(x, y)
            if text:
                break
            time.sleep(_RETRY_INTERVAL)

        if not text:
            print("[DEBUG] テキスト取得失敗")
            return

        _copy_to_clipboard(text)
        print("[INFO] クリップボードにコピー済み — 送信を続行します")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_slack_frontmost() -> bool:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app is not None and app.bundleIdentifier() == SLACK_BUNDLE_ID


def _copy_to_clipboard(text: str) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    preview = text[:_PREVIEW_MAX_LEN] + ("…" if len(text) > _PREVIEW_MAX_LEN else "")
    print(f"[COPY] {preview}")
