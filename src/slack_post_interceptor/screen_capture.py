from __future__ import annotations

import ctypes

import Quartz

_BTN_R = (0, 60)       # 実測値: 22
_BTN_G = (110, 160)    # 実測値: 133
_BTN_B = (80, 130)     # 実測値: 103
_BTN_G_MINUS_R_MIN: int = 80  # 実測値: 133-22=111
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

    for row in range(h):
        for col in range(w):
            idx = row * bpr + col * 4
            r, g, b = int(buf[idx]), int(buf[idx + 1]), int(buf[idx + 2])
            if (
                _BTN_R[0] <= r <= _BTN_R[1]
                and _BTN_G[0] <= g <= _BTN_G[1]
                and _BTN_B[0] <= b <= _BTN_B[1]
                and (g - r) >= _BTN_G_MINUS_R_MIN
            ):
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
