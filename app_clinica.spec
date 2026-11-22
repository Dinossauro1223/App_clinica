# -*- mode: python ; coding: utf-8 -*-

import os
import customtkinter

# O banco-modelo é criado a partir do esquema + migrações do código, sem exigir
# clinica.db local e sem incluir dados de pacientes.
MODELO_BANCO = os.path.join(SPECPATH, 'modelo_banco', 'clinica.db')
if not os.path.isfile(MODELO_BANCO):
    raise SystemExit(
        "Banco inicial ausente. Execute: python tools\\gerar_banco_modelo.py "
        "(nao e necessario possuir clinica.db)."
    )

CUSTOMTKINTER_PATH = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (CUSTOMTKINTER_PATH, 'customtkinter'),
        ('welcome_nutrilab.png', '.'),
        (MODELO_BANCO, '.'),
        ('regras_exames_complementares.json', '.'),
        ('exames_internos', 'exames_internos'),
        ('condutas_internas', 'condutas_internas'),
        ('sintomas_internos', 'sintomas_internos'),
        ('prescricoes_internas', 'prescricoes_internas'),
        ('condutas_alta', 'condutas_alta'),
    ],
    hiddenimports=[
        'mapa_export', 'mapa_graficos', 'graficos_ui', 'graficos_layout',
        'openpyxl', 'matplotlib.backends.backend_agg',
    ],
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
    name='NutriLab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name='NutriLab',
)
