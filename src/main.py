from __future__ import annotations

import signal
import time

import ApplicationServices as AS
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

from event_tap import WARN_KEYWORDS, EventTapHandler
from log import logger
from screen_capture import check_screen_recording, request_screen_recording

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_RED = "\033[31m"


def _print_banner() -> None:
    keywords = "、".join(f"「{kw}」" for kw in WARN_KEYWORDS)
    print(f"""
{_BOLD}{_CYAN}╭─────────────────────────────────────╮
│       Slack Post Interceptor        │
╰─────────────────────────────────────╯{_RESET}
  {_DIM}送信ボタン / Cmd+Enter をインターセプトし{_RESET}
  {_DIM}キーワードを検出したら送信をブロックします{_RESET}

  {_BOLD}監視キーワード:{_RESET} {_YELLOW}{keywords}{_RESET}
""")


def _status(*, ok: bool, label: str) -> None:
    mark = f"{_GREEN}✓{_RESET}" if ok else f"{_RED}✗{_RESET}"
    print(f"  {mark}  {label}")


def _wait_for_accessibility() -> None:
    options = {AS.kAXTrustedCheckOptionPrompt: True}
    if AS.AXIsProcessTrustedWithOptions(options):
        _status(ok=True, label="アクセシビリティ権限")
        return

    print(f"  {_YELLOW}⏳ アクセシビリティ権限を待機中...{_RESET}")
    print(f"     {_DIM}システム設定 > プライバシーとセキュリティ > アクセシビリティ で許可してください{_RESET}")
    while not AS.AXIsProcessTrusted():
        time.sleep(0.5)
    _status(ok=True, label="アクセシビリティ権限")


def _ensure_screen_recording() -> None:
    if check_screen_recording():
        _status(ok=True, label="画面収録権限")
        return

    print(f"  {_YELLOW}⏳ 画面収録権限をリクエスト中...{_RESET}")
    print(f"     {_DIM}システム設定 > プライバシーとセキュリティ > 画面収録 で許可してください{_RESET}")
    request_screen_recording()
    while not check_screen_recording():
        time.sleep(0.5)
    _status(ok=True, label="画面収録権限")


def main() -> None:
    _print_banner()

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    def _on_sigint(*_: object) -> None:
        app.stop_(None)

    signal.signal(signal.SIGINT, _on_sigint)

    _wait_for_accessibility()
    _ensure_screen_recording()

    handler = EventTapHandler()
    handler.start()

    print(f"\n  {_BOLD}{_GREEN}🚀 監視中 — Ctrl+C で終了{_RESET}\n")

    app.run()
    print(f"\n  {_DIM}終了しました{_RESET}\n")
    logger.debug("終了します")


if __name__ == "__main__":
    main()
