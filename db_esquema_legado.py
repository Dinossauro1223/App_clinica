"""Criação idempotente do esquema legado e do catálogo inicial de exames."""

def garantir_esquema_legado(conexao):
    """Cria/atualiza, de forma IDEMPOTENTE, as tabelas do esquema legado e a semente de exames.

    Não faz commit nem fecha a conexão: pode rodar dentro da transação da migração baseline
    (db_migracoes) ou, depois dela, numa conexão comum.
    """
    cursor = conexao.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Consultas (
        id_consulta INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER,
        data_consulta TEXT,
        anamnese TEXT,
        peso TEXT,
        altura TEXT,
        gordura TEXT,
        conduta TEXT
    )
    ''')

    cursor.execute("PRAGMA table_info(Consultas)")
    colunas = [col[1] for col in cursor.fetchall()]
    if 'tmb' not in colunas:
        cursor.execute("ALTER TABLE Consultas ADD COLUMN tmb TEXT")
        cursor.execute("ALTER TABLE Consultas ADD COLUMN vet TEXT")
        cursor.execute("ALTER TABLE Consultas ADD COLUMN naf TEXT")
        cursor.execute("ALTER TABLE Consultas ADD COLUMN metodo_tmb TEXT")
    if 'analise_exames' not in colunas:
        cursor.execute("ALTER TABLE Consultas ADD COLUMN analise_exames TEXT")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Exames_Solicitados (
        id_solicitacao INTEGER PRIMARY KEY AUTOINCREMENT,
        id_consulta INTEGER,
        id_exame TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Arquivos_Paciente (
        id_arquivo INTEGER PRIMARY KEY AUTOINCREMENT,
        id_paciente INTEGER,
        nome_arquivo TEXT,
        caminho_arquivo TEXT,
        data_upload TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Exames_Catalogo (
        id_exame TEXT PRIMARY KEY,
        nome_amigavel TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Regras_Complementares (
        id_regra INTEGER PRIMARY KEY AUTOINCREMENT,
        exame_gatilho TEXT,
        exame_sugerido TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Resultados_Exames (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_consulta INTEGER,
        id_exame TEXT,
        valor REAL,
        status TEXT
    )
    ''')

    cursor.execute("SELECT COUNT(*) FROM Exames_Catalogo")
    if cursor.fetchone()[0] == 0:
        exames_basicos = [
            ('EXM-GLICEMIA-DE-JEJUM', 'GLICEMIA DE JEJUM'),
            ('EXM-HOMA-IR', 'HOMA IR'),
            ('EXM-HBA1C', 'HBA1C'),
            ('EXM-TOTG-2H', 'TOTG 2H'),
            ('EXM-COLESTEROL-TOTAL', 'COLESTEROL TOTAL'),
            ('EXM-HDL-COLESTEROL', 'HDL COLESTEROL'),
            ('EXM-LDL-COLESTEROL', 'LDL COLESTEROL'),
            ('EXM-TRIGLICERIDEOS', 'TRIGLICERIDEOS'),
            ('EXM-FERRO-SERICO', 'FERRO SERICO'),
            ('EXM-FERRITINA-SERICA', 'FERRITINA SERICA'),
            ('EXM-SATURACAO-DE-TRANSFERRINA', 'SATURACAO DE TRANSFERRINA'),
            ('EXM-TIBC', 'TIBC'),
            ('EXM-B12-SERICA', 'B12 SERICA'),
            ('EXM-ACIDO-METILMALONICO', 'ACIDO METILMALONICO'),
            ('EXM-HOMOCISTEINA-SERICA', 'HOMOCISTEINA SERICA')
        ]
        cursor.executemany("INSERT OR IGNORE INTO Exames_Catalogo (id_exame, nome_amigavel) VALUES (?, ?)", exames_basicos)

    cursor.execute('''
        INSERT INTO Regras_Complementares (exame_gatilho, exame_sugerido)
        SELECT 'EXM-GLICEMIA-DE-JEJUM', 'EXM-HOMA-IR'
        WHERE NOT EXISTS (SELECT 1 FROM Regras_Complementares WHERE exame_gatilho = 'EXM-GLICEMIA-DE-JEJUM')
    ''')

