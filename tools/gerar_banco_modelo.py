"""Gera o banco inicial vazio e completo que acompanha o NutriLab.

O banco é construído a partir do esquema atual do próprio código (baseline + migrações +
inicialização do Mapa). Não depende de um clinica.db local e NUNCA lê/empacota dados reais.

Uso: python tools/gerar_banco_modelo.py [--destino modelo_banco/clinica.db] [--sobrescrever]
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

TABELAS_QUE_DEVEM_FICAR_VAZIAS = (
    "Pacientes", "Consultas", "Exames_Solicitados", "Arquivos_Paciente",
    "Resultados_Exames", "Mapa_Registros", "Mapa_Registro_Suplementos",
    "Condutas_Alta_Docs", "Condutas_Alta_Itens", "Pep_Evolucoes",
)


class ErroModelo(Exception):
    """Erro ao gerar ou validar o banco inicial."""


def _gerar_em(caminho: Path) -> dict:
    # Imports tardios: o script pode ser importado pelos testes sem iniciar a interface.
    import db_migracoes
    import mapa_db
    import main

    # Cria o esquema-base em banco novo e aplica exatamente as migrações do aplicativo.
    db_migracoes.aplicar_migracoes(
        caminho,
        inicializador_legado=main.garantir_esquema_legado,
        backup=False,
    )
    # O Mapa possui tabelas e catálogos próprios, inicializados na primeira abertura do programa.
    mapa_db.inicializar(str(caminho))

    conn = sqlite3.connect(str(caminho))
    try:
        integridade = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integridade != "ok":
            raise ErroModelo(f"banco-modelo reprovado no integrity_check: {integridade}")

        tabelas = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        ausentes = [nome for nome in ("Pacientes", "Consultas", "Exames_Catalogo", "Mapa_Registros",
                                      "schema_migrations") if nome not in tabelas]
        if ausentes:
            raise ErroModelo("esquema incompleto; tabela(s) ausente(s): " + ", ".join(ausentes))

        resumo = {}
        for tabela in TABELAS_QUE_DEVEM_FICAR_VAZIAS:
            if tabela in tabelas:
                total = conn.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
                if total:
                    raise ErroModelo(f"a tabela clínica {tabela} deveria estar vazia, mas contém {total} registro(s)")
                resumo[tabela] = 0

        versao = conn.execute("SELECT MAX(versao) FROM schema_migrations").fetchone()[0]
        resumo["versao_migracoes"] = int(versao or 0)
        resumo["exames_catalogo"] = conn.execute("SELECT COUNT(*) FROM Exames_Catalogo").fetchone()[0]
        resumo["mapa_modulos"] = conn.execute("SELECT COUNT(*) FROM Mapa_Modulos").fetchone()[0]
        resumo["mapa_suplementos"] = conn.execute("SELECT COUNT(*) FROM Mapa_Suplementos").fetchone()[0]
        return resumo
    finally:
        conn.close()


def gerar(destino="modelo_banco/clinica.db", *, sobrescrever: bool = False) -> dict:
    """Gera um banco inicial limpo, sem depender de arquivo de banco externo."""
    destino = Path(destino)
    if destino.exists() and not sobrescrever:
        raise ErroModelo(f"o destino já existe: {destino} (use --sobrescrever para substituí-lo)")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".gerando")
    for sufixo in ("", "-wal", "-shm"):
        sobra = Path(str(temporario) + sufixo)
        if sobra.exists():
            sobra.unlink()
    try:
        resumo = _gerar_em(temporario)
        os.replace(temporario, destino)
        return resumo
    except ErroModelo:
        raise
    except Exception as exc:
        raise ErroModelo(f"não foi possível construir o banco-modelo: {type(exc).__name__}: {exc}") from exc
    finally:
        for sufixo in ("", "-wal", "-shm"):
            sobra = Path(str(temporario) + sufixo)
            if sobra.exists():
                sobra.unlink()


def _saida_tolerante() -> None:
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar:
        reconfigurar(errors="replace")


def main_cli(argv=None) -> int:
    _saida_tolerante()
    parser = argparse.ArgumentParser(description="Gera o banco inicial vazio do NutriLab, sem clinica.db de origem.")
    parser.add_argument("--destino", default=os.path.join("modelo_banco", "clinica.db"))
    parser.add_argument("--sobrescrever", action="store_true", help="substitui o banco-modelo já existente")
    args = parser.parse_args(argv)
    try:
        resumo = gerar(args.destino, sobrescrever=args.sobrescrever)
    except ErroModelo as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    print(f"Banco inicial gerado em: {args.destino}")
    print(f"Versão das migrações: {resumo['versao_migracoes']}")
    print(f"Exames do catálogo: {resumo['exames_catalogo']}")
    print(f"Módulos do Mapa: {resumo['mapa_modulos']}; suplementos iniciais: {resumo['mapa_suplementos']}")
    print("Verificado: integrity_check OK; tabelas de pacientes e registros clínicos vazias.")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())
