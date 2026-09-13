# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPECPATH).parent
datas = [
    (str(project_root / "dist"), "dist"),
    (str(project_root / "config" / "language_policy.json"), "config"),
    (str(project_root / "config" / ".env.example"), "config"),
]
datas += collect_data_files("webview")

a = Analysis(
    [str(project_root / "packaging" / "launch_app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=["scripts.serve_api"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # These are unrelated to the desktop agent and can make PyInstaller scan
    # hundreds of megabytes of globally installed scientific/test packages.
    excludes=[
        "torch",
        "torchvision",
        "tensorflow",
        "pandas",
        "scipy",
        "sklearn",
        "pytest",
        "langsmith",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WaimaoClientAgentDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
