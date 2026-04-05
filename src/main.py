from __future__ import annotations

import time

import ApplicationServices as AS
import Quartz

from event_tap import EventTapHandler
from screen_capture import check_screen_recording, request_screen_recording


def _wait_for_accessibility() -> None:
    options = {AS.kAXTrustedCheckOptionPrompt: True}
    if AS.AXIsProcessTrustedWithOptions(options):
        print("[INFO] アクセシビリティ権限: 許可済み")
        return

    print("[WAIT] アクセシビリティ権限を待機中...")
    print("       システム設定 > プライバシーとセキュリティ > アクセシビリティ で本ツールを許可してください")

    while not AS.AXIsProcessTrusted():
        time.sleep(0.5)

    print("[INFO] アクセシビリティ権限が付与されました")


def _ensure_screen_recording() -> None:
    if check_screen_recording():
        print("[INFO] 画面収録権限: 許可済み")
        return

    print("[WAIT] 画面収録権限をリクエスト中...")
    print("       システム設定 > プライバシーとセキュリティ > 画面収録 で本ツールを許可してください")
    request_screen_recording()

    while not check_screen_recording():
        time.sleep(0.5)

    print("[INFO] 画面収録権限が付与されました")


def main() -> None:
    print("Slack Post Interceptor")
    print("======================")

    _wait_for_accessibility()
    _ensure_screen_recording()

    handler = EventTapHandler()
    handler.start()

    try:
        Quartz.CFRunLoopRun()
    except KeyboardInterrupt:
        print("\n[INFO] 終了します")


if __name__ == "__main__":
    main()
