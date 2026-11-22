# -*- mode: python ; coding: utf-8 -*-

import os
import customtkinter

# Fase 0 (ADR-0005): o executável NÃO embute mais o `clinica.db` real (ele contém pacientes). Embute um banco-MODELO
# sanitizado (catálogo de exames e regras, sem pacientes), gerado ANTES do build com:  python tools\gerar_banco_modelo.py
MODELO_BANCO = os.path.join(SPECPATH, 'modelo_banco', 'clinica.db')
if not os.path.exists(MODELO_BANCO):
    raise SystemExit("Banco-modelo ausente. Rode primeiro:  python tools\\gerar_banco_modelo.py  "
                     "(o executavel nao embute mais o seu clinica.db real).")


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(os.path.dirname(customtkinter.__file__), 'customtkinter'), ('welcome_nutrilab.png', '.'), (os.path.join(SPECPATH, 'assets', 'identidade', 'nutrilab_identidade.png'), '.'), (MODELO_BANCO, '.'), ('regras_exames_complementares.json', '.'), ('exames_internos', 'exames_internos'), ('condutas_internas', 'condutas_internas'), ('sintomas_internos', 'sintomas_internos'), ('prescricoes_internas', 'prescricoes_internas'), ('condutas_alta', 'condutas_alta')],
    hiddenimports=['mapa_export', 'mapa_graficos', 'graficos_ui', 'graficos_layout', 'openpyxl', 'matplotlib.backends.backend_agg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='app_clinica',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(SPECPATH, 'assets', 'identidade', 'nutrilab.ico'),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app_clinica',
)
