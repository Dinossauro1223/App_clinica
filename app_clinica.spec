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

PASTA_CAMADAS = os.path.join(SPECPATH, 'assets', 'identidade', 'renderizados')
if not os.path.isfile(os.path.join(PASTA_CAMADAS, 'folhas.json')):
    raise SystemExit(
        "Camadas da tela inicial ausentes. Execute: python tools\\\\gerar_identidade_visual.py."
    )

ARQUIVO_LMS_OMS = os.path.join('dados', 'oms_lms_pediatricos.csv')
if not os.path.isfile(os.path.join(SPECPATH, ARQUIVO_LMS_OMS)):
    raise SystemExit("Tabela LMS oficial OMS ausente: dados\\oms_lms_pediatricos.csv")
ARQUIVO_CLASSIFICACOES_OMS = os.path.join('dados', 'oms_classificacoes_pediatricas.json')
if not os.path.isfile(os.path.join(SPECPATH, ARQUIVO_CLASSIFICACOES_OMS)):
    raise SystemExit("Pontos de corte OMS ausentes: dados\\oms_classificacoes_pediatricas.json")

CUSTOMTKINTER_PATH = os.path.dirname(customtkinter.__file__)

# Os componentes SVG são renderizados em camadas RGBA antes da compilação,
# tanto no CI quanto pelo inicializador local.
ARQUIVOS_DATA = [
    (CUSTOMTKINTER_PATH, 'customtkinter'),
    ('welcome_nutrilab.png', '.'),
    (os.path.join(SPECPATH, 'assets', 'identidade', 'nutrilab_identidade.png'), '.'),
    (os.path.join(SPECPATH, 'assets', 'escalas_visita'), 'assets/escalas_visita'),
    (os.path.join(SPECPATH, 'assets', 'escalas_visita'), 'assets/escalas_visita'),
    (PASTA_CAMADAS, 'identidade_camadas'),
    (os.path.join(SPECPATH, 'mobile', 'servidor.py'), 'mobile'),
    (os.path.join(SPECPATH, 'mobile', 'static'), 'mobile/static'),
    (MODELO_BANCO, 'modelo_banco'),
    ('regras_exames_complementares.json', '.'),
    ('exames_internos', 'exames_internos'),
    ('condutas_internas', 'condutas_internas'),
    ('sintomas_internos', 'sintomas_internos'),
    ('prescricoes_internas', 'prescricoes_internas'),
    ('condutas_alta', 'condutas_alta'),
    (ARQUIVO_LMS_OMS, 'dados'),
    (ARQUIVO_CLASSIFICACOES_OMS, 'dados'),
]
DATAS = [
    (origem, destino)
    for origem, destino in ARQUIVOS_DATA
    if os.path.exists(os.path.join(SPECPATH, origem))
]

CAMINHO_ICONE = os.path.join(SPECPATH, 'assets', 'identidade', 'nutrilab.ico')
ICONE = CAMINHO_ICONE if os.path.isfile(CAMINHO_ICONE) else None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=DATAS,
    hiddenimports=[
        'mapa_export', 'mapa_graficos', 'graficos_ui', 'graficos_layout', 'graficos_nativos', 'graficos_pintor',
        'configuracoes_ui', 'mobile_ui', 'almox_ui', 'gestao_alimentar_ui',
        'nrs_ui', 'avaliacao_ui', 'pediatria_oms',
        'openpyxl', 'matplotlib.backends.backend_agg', 'matplotlib.backends.backend_tkagg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_update_check.py'],
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
    icon=ICONE,
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
