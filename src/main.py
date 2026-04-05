from __future__ import annotations

import signal
import time

import ApplicationServices as AS
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

from event_tap import EventTapHandler
from log import logger
from screen_capture import check_screen_recording, request_screen_recording


def _wait_for_accessibility() -> None:
    options = {AS.kAXTrustedCheckOptionPrompt: True}
    if AS.AXIsProcessTrustedWithOptions(options):
        logger.info("アクセシビリティ権限: 許可済み")
        return

    logger.info("アクセシビリティ権限を待機中...")
    logger.info("システム設定 > プライバシーとセキュリティ > アクセシビリティ で本ツールを許可してください")

    while not AS.AXIsProcessTrusted():
        time.sleep(0.5)

    logger.info("アクセシビリティ権限が付与されました")


def _ensure_screen_recording() -> None:
    if check_screen_recording():
        logger.info("画面収録権限: 許可済み")
        return

    logger.info("画面収録権限をリクエスト中...")
    logger.info("システム設定 > プライバシーとセキュリティ > 画面収録 で本ツールを許可してください")
    request_screen_recording()

    while not check_screen_recording():
        time.sleep(0.5)

    logger.info("画面収録権限が付与されました")


def main() -> None:
    print("Slack Post Interceptor")
    print("======================")

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    def _on_sigint(*_: object) -> None:
        app.stop_(None)

    signal.signal(signal.SIGINT, _on_sigint)

    _wait_for_accessibility()
    _ensure_screen_recording()

    handler = EventTapHandler()
    handler.start()

    app.run()
    logger.info("終了します")


if __name__ == "__main__":
    main()
