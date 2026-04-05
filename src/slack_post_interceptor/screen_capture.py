from __future__ import annotations

import ctypes

import Quartz

_BTN_COLOR: tuple[int, int, int] = (22, 133, 103)
_OUTSIDE_COLOR_MAX: int = 120  # ボタン外の暗い背景色の最大輝度値


def get_pixel_color(x: float, y: float) -> tuple[int, int, int] | None:
    """指定座標のピクセル色を返す。Screen Recording 権限が必要。"""
    rect = Quartz.CGRectMake(x, y, 1, 1)
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

    return (int(buf[0]), int(buf[1]), int(buf[2]))


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

    for row in range(h):
        for col in range(w):
            idx = row * bpr + col * 4
            r, g, b = int(buf[idx]), int(buf[idx + 1]), int(buf[idx + 2])
            if (r, g, b) == _BTN_COLOR:
                return True
    return False


def is_button_outside_color(r: int, g: int, b: int) -> bool:
    """ボタン外(Slack ダークテーマの背景・ツールバー等)の色かを判定する。

    ボタン周囲はすべて低輝度の暗い色。ボタン内は緑または白(▶アイコン)なので除外できる。
    """
    return r < _OUTSIDE_COLOR_MAX and g < _OUTSIDE_COLOR_MAX and b < _OUTSIDE_COLOR_MAX


def check_screen_recording() -> bool:
    return bool(Quartz.CGPreflightScreenCaptureAccess())


def request_screen_recording() -> None:
    Quartz.CGRequestScreenCaptureAccess()
