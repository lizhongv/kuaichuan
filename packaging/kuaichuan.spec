# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：单文件、无控制台窗口，内置网页资源、图标与版本信息。
# 用法（在仓库根目录）：pyinstaller --noconfirm packaging/kuaichuan.spec

import os

from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "src")
ASSETS = os.path.join(SRC, "kuaichuan", "assets")

a = Analysis(
    [os.path.join(SRC, "kuaichuan", "__main__.py")],
    pathex=[SRC],
    datas=[(ASSETS, "kuaichuan/assets")] + collect_data_files("customtkinter"),
    hiddenimports=["kuaichuan.ui.app"],
    excludes=["numpy", "pandas", "matplotlib", "scipy", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="KuaiChuan",
    icon=os.path.join(ASSETS, "icon.ico"),
    version=os.path.join(SPECPATH, "version_info.txt"),
    console=False,
    upx=False,
)
