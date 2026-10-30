"""线条图标：用 Pillow 在 4 倍尺寸下绘制后缩小，保证高分屏清晰，无需外部图片资源。"""

import functools

import customtkinter as ctk
from PIL import Image, ImageDraw

_S = 96             # 绘制画布边长
_W = 7              # 线宽


def _canvas():
    img = Image.new("RGBA", (_S, _S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _arrow(d, color, x, y0, y1, up):
    d.line([(x, y0), (x, y1)], fill=color, width=_W)
    tip, back = (y0, y0 + 20) if up else (y1, y1 - 20)
    d.line([(x - 18, back), (x, tip), (x + 18, back)], fill=color, width=_W, joint="curve")


def _tray(d, color):
    d.line([(16, 58), (16, 80), (80, 80), (80, 58)], fill=color, width=_W, joint="curve")


def _draw(name, color):
    img, d = _canvas()
    if name == "recv":
        _arrow(d, color, 48, 14, 62, up=False)
        _tray(d, color)
    elif name == "send":
        _arrow(d, color, 48, 14, 62, up=True)
        _tray(d, color)
    elif name == "phone":
        d.rounded_rectangle([28, 10, 68, 86], radius=10, outline=color, width=_W)
        d.line([(42, 74), (54, 74)], fill=color, width=_W)
    elif name == "history":
        d.ellipse([12, 12, 84, 84], outline=color, width=_W)
        d.line([(48, 28), (48, 50), (64, 60)], fill=color, width=_W, joint="curve")
    elif name == "folder":
        d.line([(12, 26), (38, 26), (46, 34), (84, 34), (84, 78), (12, 78), (12, 26)], fill=color, width=_W,
               joint="curve")
    elif name == "file":
        d.line([(24, 10), (58, 10), (74, 26), (74, 86), (24, 86), (24, 10)], fill=color, width=_W, joint="curve")
        d.line([(58, 10), (58, 26), (74, 26)], fill=color, width=_W)
    elif name == "search":
        d.ellipse([14, 14, 62, 62], outline=color, width=_W)
        d.line([(56, 56), (82, 82)], fill=color, width=_W + 2)
    elif name == "plus":
        d.line([(48, 18), (48, 78)], fill=color, width=_W)
        d.line([(18, 48), (78, 48)], fill=color, width=_W)
    elif name == "close":
        d.line([(26, 26), (70, 70)], fill=color, width=_W)
        d.line([(70, 26), (26, 70)], fill=color, width=_W)
    elif name == "check":
        d.line([(18, 50), (40, 72), (80, 28)], fill=color, width=_W + 2, joint="curve")
    elif name == "power":
        d.arc([14, 18, 82, 86], start=-60, end=240, fill=color, width=_W)
        d.line([(48, 10), (48, 46)], fill=color, width=_W)
    return img


@functools.lru_cache(maxsize=None)
def icon(name, size=18, light="#334155", dark="#CBD5E1"):
    """取图标；light / dark 分别为浅色与深色主题下的颜色。"""
    return ctk.CTkImage(light_image=_draw(name, light), dark_image=_draw(name, dark), size=(size, size))


def logo_image(size=256):
    """应用图标：品牌渐变圆角方块 + 上下双箭头，打包时用于生成 .ico。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):           # 竖向渐变 #3B82F6 → #4F46E5
        t = y / size
        gd.line([(0, y), (size, y)], fill=(int(59 + (79 - 59) * t), int(130 + (70 - 130) * t), int(246 + (229 - 246) * t)))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 4.5, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    w = max(size // 14, 2)
    s = size / 256
    # 左侧向上箭头、右侧向下箭头，表示双向互传
    d.line([(96 * s, 196 * s), (96 * s, 64 * s)], fill="white", width=w)
    d.line([(60 * s, 100 * s), (96 * s, 62 * s), (132 * s, 100 * s)], fill="white", width=w, joint="curve")
    d.line([(160 * s, 60 * s), (160 * s, 192 * s)], fill="white", width=w)
    d.line([(124 * s, 156 * s), (160 * s, 194 * s), (196 * s, 156 * s)], fill="white", width=w, joint="curve")
    return img
