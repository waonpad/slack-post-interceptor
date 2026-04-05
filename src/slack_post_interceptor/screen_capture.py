from __future__ import annotations

import ctypes

import Quartz

_BTN_COLOR: tuple[int, int, int] = (22, 133, 103)
_OUTSIDE_COLOR_MAX: int = 120  # ボタン外の暗い背景色の最大輝度値
_SCAN_RADIUS: int = 16


def is_send_button_at(x: float, y: float) -> bool:
    """クリック座標がSlack送信ボタン上かを1回のキャプチャで判定する。

    中央ピクセルがボタン外の暗い色なら即 False。
    周囲にボタン色があれば True。
    """
    size = _SCAN_RADIUS * 2
    rect = Quartz.CGRectMake(x - _SCAN_RADIUS, y - _SCAN_RADIUS, size, size)
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

    # 中央ピクセルがボタン外の暗い色なら即リターン
    ci = (h // 2) * bpr + (w // 2) * 4
    cr, cg, cb = int(buf[ci]), int(buf[ci + 1]), int(buf[ci + 2])
    if cr < _OUTSIDE_COLOR_MAX and cg < _OUTSIDE_COLOR_MAX and cb < _OUTSIDE_COLOR_MAX:
        return False

    for row in range(h):
        for col in range(w):
            idx = row * bpr + col * 4
            if (int(buf[idx]), int(buf[idx + 1]), int(buf[idx + 2])) == _BTN_COLOR:
                return True
    return False


def check_screen_recording() -> bool:
    return bool(Quartz.CGPreflightScreenCaptureAccess())


def request_screen_recording() -> None:
    Quartz.CGRequestScreenCaptureAccess()
