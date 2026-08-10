# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve()
APP_ROOT = PROJECT_ROOT / "app"
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

core_modules = [
    module
    for module in collect_submodules("modules.core")
    if ".tests" not in module
]
django_app_modules = []
for package in (
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
):
    django_app_modules.extend(collect_submodules(package))

application_hidden_imports = sorted(
    set(
        collect_submodules("config")
        + collect_submodules("qrcode")
        + collect_submodules("reportlab")
        + core_modules
        + django_app_modules
        + [
            "django.core.management.commands.flush",
            "django.core.management.commands.migrate",
            "launcher.backup",
            "launcher.mobile_access",
        ]
    )
)

application_analysis = Analysis(
    [str(PROJECT_ROOT / "launcher" / "launcher.py")],
    pathex=[str(APP_ROOT), str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(APP_ROOT / "templates"), "templates"),
        (str(APP_ROOT / "static"), "static"),
    ],
    hiddenimports=application_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.gis",
        "django.contrib.postgres",
        "django.test",
        "pytest",
    ],
    noarchive=False,
    optimize=1,
)
application_pyz = PYZ(application_analysis.pure)
application_exe = EXE(
    application_pyz,
    application_analysis.scripts,
    [],
    exclude_binaries=True,
    name="GestionFinanciera",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

restorer_analysis = Analysis(
    [str(PROJECT_ROOT / "launcher" / "restorer.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=["launcher.backup"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["django", "pytest"],
    noarchive=False,
    optimize=1,
)
restorer_pyz = PYZ(restorer_analysis.pure)
restorer_exe = EXE(
    restorer_pyz,
    restorer_analysis.scripts,
    [],
    exclude_binaries=True,
    name="Restaurador",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

archive_analysis = Analysis(
    [str(PROJECT_ROOT / "launcher" / "archive_reset.py")],
    pathex=[str(APP_ROOT), str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=application_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.gis",
        "django.contrib.postgres",
        "django.test",
        "pytest",
    ],
    noarchive=False,
    optimize=1,
)
archive_pyz = PYZ(archive_analysis.pure)
archive_exe = EXE(
    archive_pyz,
    archive_analysis.scripts,
    [],
    exclude_binaries=True,
    name="ArchivarYReiniciar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

portable_package = COLLECT(
    application_exe,
    application_analysis.binaries,
    application_analysis.datas,
    restorer_exe,
    restorer_analysis.binaries,
    restorer_analysis.datas,
    archive_exe,
    archive_analysis.binaries,
    archive_analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GestionFinanciera",
)
