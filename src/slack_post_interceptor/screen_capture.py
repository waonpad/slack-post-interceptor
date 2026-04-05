from __future__ import annotations

import ctypes
import json
from pathlib import Path

import Quartz

_CONFIG_PATH = Path.home() / ".config" / "slack-post-interceptor" / "button_color.json"

# デフォルト: Slack 送信ボタンの緑系色 (未キャリブレーション時)
_DEFAULT_RANGE = {"r": (0, 160), "g": (130, 255), "b": (50, 220), "g_minus_r_min": 30}


_OUTSIDE_COLOR_MAX: int = 120  # ボタン外の暗い背景色の最大輝度値


def get_pixel_color(x: float, y: float) -> tuple[int, int, int] | None:
    """指定座標中心 3x3 px の平均色を返す。Screen Recording 権限が必要。"""
    rect = Quartz.CGRectMake(x - 1, y - 1, 3, 3)
    image = Quartz.CGWindowListCreateImage(
        rect,
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )
    if image is None:
        return None

    w = Quartz.CGImageGetWidth(image)
    h = Quartz.CGImageGetHeight(image)
    if w == 0 or h == 0:
        return None

    bpr = w * 4
    buf = (ctypes.c_uint8 * (h * bpr))()
    cs = Quartz.CGColorSpaceCreateDeviceRGB()
    ctx = Quartz.CGBitmapContextCreate(buf, w, h, 8, bpr, cs, Quartz.kCGImageAlphaPremultipliedLast)
    if ctx is None:
        return None

    Quartz.CGContextDrawImage(ctx, Quartz.CGRectMake(0, 0, w, h), image)

    idx = 1 * bpr + 1 * 4  # 中央ピクセル
    return (int(buf[idx]), int(buf[idx + 1]), int(buf[idx + 2]))


def has_send_button_nearby(x: float, y: float, radius: int = 16) -> bool:
    """指定座標を中心とした領域内に送信ボタンの色があるか判定する。"""
    size = radius * 2
    rect = Quartz.CGRectMake(x - radius, y - radius, size, size)
    image = Quartz.CGWindowListCreateImage(
        rect,
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )
    if image is None:
        return False

    w = Quartz.CGImageGetWidth(image)
    h = Quartz.CGImageGetHeight(image)
    if w == 0 or h == 0:
        return False

    bpr = w * 4
    buf = (ctypes.c_uint8 * (h * bpr))()
    cs = Quartz.CGColorSpaceCreateDeviceRGB()
    ctx = Quartz.CGBitmapContextCreate(buf, w, h, 8, bpr, cs, Quartz.kCGImageAlphaPremultipliedLast)
    if ctx is None:
        return False

    Quartz.CGContextDrawImage(ctx, Quartz.CGRectMake(0, 0, w, h), image)

    cr = _load_color_range()
    for row in range(h):
        for col in range(w):
            idx = row * bpr + col * 4
            r, g, b = int(buf[idx]), int(buf[idx + 1]), int(buf[idx + 2])
            if (
                cr["r"][0] <= r <= cr["r"][1]
                and cr["g"][0] <= g <= cr["g"][1]
                and cr["b"][0] <= b <= cr["b"][1]
                and (g - r) >= cr["g_minus_r_min"]
            ):
                return True
    return False


def is_send_button(r: int, g: int, b: int) -> bool:
    """ピクセル色が Slack 送信ボタンの色かを判定する。"""
    cr = _load_color_range()
    return (
        cr["r"][0] <= r <= cr["r"][1]
        and cr["g"][0] <= g <= cr["g"][1]
        and cr["b"][0] <= b <= cr["b"][1]
        and (g - r) >= cr["g_minus_r_min"]
    )


def is_button_outside_color(r: int, g: int, b: int) -> bool:
    """ボタン外(Slack ダークテーマの背景・ツールバー等)の色かを判定する。

    ボタン周囲はすべて低輝度の暗い色。ボタン内は緑または白(▶アイコン)なので除外できる。
    """
    return r < _OUTSIDE_COLOR_MAX and g < _OUTSIDE_COLOR_MAX and b < _OUTSIDE_COLOR_MAX


def check_screen_recording() -> bool:
    return bool(Quartz.CGPreflightScreenCaptureAccess())


def request_screen_recording() -> None:
    Quartz.CGRequestScreenCaptureAccess()


def calibrate(x: float, y: float) -> tuple[int, int, int] | None:
    """指定座標のピクセル色をキャリブレーションデータとして保存する。"""
    color = get_pixel_color(x, y)
    if color is None:
        return None

    r, g, b = color
    margin = 40
    data = {
        "r": (max(0, r - margin), min(255, r + margin)),
        "g": (max(0, g - margin), min(255, g + margin)),
        "b": (max(0, b - margin), min(255, b + margin)),
        "g_minus_r_min": max(0, (g - r) - 20),
    }

    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data))
    print(f"[CALIBRATE] 色 RGB({r},{g},{b}) を保存しました → {_CONFIG_PATH}")
    return color


def _load_color_range() -> dict:  # type: ignore[type-arg]
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text())  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass
    return _DEFAULT_RANGE
