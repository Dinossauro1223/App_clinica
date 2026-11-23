"""Proteção contra exclusão de pacientes que possuem histórico ou documentos.

A função é independente da interface para permitir testes com bancos SQLite temporários.
Não remove, altera ou migra dados.
"""
from pathlib import Path

# Relações diretas por ID do paciente. Consultas também protege os registros de exames
# que se relacionam por id_consulta, bem como anamnese e condutas legadas.
TABELAS_REFERENCIADAS = (
    ("Consultas", "id_paciente"),
    ("Arquivos_Paciente", "id_paciente"),
    ("Mapa_Registros", "id_paciente"),
    ("Condutas_Alta_Docs", "id_paciente"),
    ("Consulta_Recomendacoes", "id_paciente"),
    ("Pep_Evolucoes", "id_paciente"),
)


def registros_vinculados(conn, id_paciente, pasta_anexos=None):
    """Retorna contagens de registros ligados e arquivos físicos, sem alterar o banco."""
    if isinstance(id_paciente, bool) or not isinstance(id_paciente, int) or id_paciente < 1:
        raise ValueError("ID do paciente inválido.")
    tabelas_existentes = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    contagens = {}
    for tabela, coluna in TABELAS_REFERENCIADAS:
        if tabela not in tabelas_existentes:
            continue
        colunas = {row[1] for row in conn.execute(f'PRAGMA table_info("{tabela}")')}
        if coluna not in colunas:
            continue
        quantidade = conn.execute(
            f'SELECT COUNT(*) FROM "{tabela}" WHERE "{coluna}" = ?', (id_paciente,)
        ).fetchone()[0]
        if quantidade:
            contagens[tabela] = quantidade

    if pasta_anexos:
        pasta = Path(pasta_anexos)
        if pasta.is_dir():
            quantidade_arquivos = sum(1 for item in pasta.rglob("*") if item.is_file())
            if quantidade_arquivos:
                contagens["Arquivos físicos"] = quantidade_arquivos
    return contagens


def paciente_pode_ser_excluido(conn, id_paciente, pasta_anexos=None):
    """True apenas quando nenhuma referência clínica nem arquivo físico foi encontrado."""
    return not registros_vinculados(conn, id_paciente, pasta_anexos)
