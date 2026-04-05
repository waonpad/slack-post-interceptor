from __future__ import annotations

from typing import Any

import ApplicationServices as AS
from AppKit import NSWorkspace

_AX_SUCCESS = 0
_SLACK_BUNDLE_ID = "com.tinyspeck.slackmacgap"

_MAX_SEARCH_DEPTH: int = 8
_MAX_PARENT_DEPTH: int = 12

_cached_app_el: Any = None


def get_text_near_position(x: float, y: float) -> str | None:
    """クリック座標付近のテキストエリアからテキストを取得する。フォーカス状態に依存しない。"""
    app_el = _slack_app_element()
    if app_el is None:
        return None

    # まずクリック座標で試み、失敗したらボタン左側(テキスト入力エリア方向)をプローブする
    for probe_x in [x] + [x - offset for offset in (60, 120, 200, 300)]:
        text = _get_text_from_ax_position(app_el, probe_x, y)
        if text:
            return text

    return None


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _get_text_from_ax_position(app_el: Any, x: float, y: float) -> str | None:
    """指定座標のAX要素から親を遡ってテキストエリアを探す。"""
    AS.AXUIElementCopyElementAtPosition(app_el, x, y, None)
    err, element = AS.AXUIElementCopyElementAtPosition(app_el, x, y, None)
    if err != _AX_SUCCESS or element is None:
        return None

    current = element
    for _ in range(_MAX_PARENT_DEPTH):
        err, parent = AS.AXUIElementCopyAttributeValue(current, "AXParent", None)
        if err != _AX_SUCCESS or parent is None:
            break
        current = parent
        err2, role = AS.AXUIElementCopyAttributeValue(current, "AXRole", None)
        # メッセージ履歴側のブランチには入らない
        if err2 == _AX_SUCCESS and role in ("AXWebArea", "AXScrollArea"):
            break
        text = _search_text_area_value(current, depth=0)
        if text:
            return text

    return None


def _search_text_area_value(element: Any, depth: int) -> str | None:
    """AXTextArea を再帰探索して AXValue を返す。"""
    if depth >= _MAX_SEARCH_DEPTH:
        return None
    err, role = AS.AXUIElementCopyAttributeValue(element, "AXRole", None)
    if err == _AX_SUCCESS and role == "AXTextArea":
        err, value = AS.AXUIElementCopyAttributeValue(element, "AXValue", None)
        if err == _AX_SUCCESS and value:
            text = str(value).strip()
            return text or None
    err, children = AS.AXUIElementCopyAttributeValue(element, "AXChildren", None)
    if err != _AX_SUCCESS or not children:
        return None
    for child in children:
        result = _search_text_area_value(child, depth + 1)
        if result is not None:
            return result
    return None


def _slack_app_element() -> Any | None:
    global _cached_app_el
    if _cached_app_el is not None:
        return _cached_app_el
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        if app.bundleIdentifier() == _SLACK_BUNDLE_ID:
            app_el = AS.AXUIElementCreateApplication(app.processIdentifier())
            AS.AXUIElementSetAttributeValue(app_el, "AXEnhancedUserInterface", True)
            _cached_app_el = app_el
            return app_el
    return None
