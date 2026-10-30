"""设计规范：配色（浅色, 深色）、字号与间距。所有界面颜色只从这里取。"""

import customtkinter as ctk

FONT_FAMILY = "Microsoft YaHei UI"

BRAND = "#2563EB"
BRAND_HOVER = "#1D4ED8"
BRAND_SOFT = ("#EFF6FF", "#1E2A4A")

BG = ("#F1F5F9", "#0B1220")
CARD = ("#FFFFFF", "#151E30")
CARD_BORDER = ("#E2E8F0", "#253047")
INPUT_BG = ("#F8FAFC", "#0F172A")

SIDEBAR = ("#0F1E3D", "#070D1A")
SIDEBAR_HOVER = ("#1B2E57", "#121C33")
SIDEBAR_ACTIVE = ("#2563EB", "#2563EB")
SIDEBAR_TEXT = ("#C7D2E5", "#AEB9CC")

TEXT = ("#0F172A", "#E2E8F0")
TEXT_MUTED = ("#64748B", "#94A3B8")

SUCCESS = "#16A34A"
SUCCESS_SOFT = ("#DCFCE7", "#12341F")
DANGER = "#DC2626"
DANGER_SOFT = ("#FEE2E2", "#3A1717")
NEUTRAL_SOFT = ("#E2E8F0", "#253047")

SECONDARY_BTN = ("#E2E8F0", "#253047")
SECONDARY_BTN_HOVER = ("#CBD5E1", "#334155")

RADIUS = 14
PAD = 20


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)
