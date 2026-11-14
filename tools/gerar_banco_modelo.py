"""Gera o banco-MODELO SANITIZADO que o executável embute (Fase 0, ADR-0005).

Uso (na raiz do projeto):
    python tools/gerar_banco_modelo.py [--origem clinica.db] [--destino modelo_banco/clinica.db]
                                       [--copiar-linhas TABELA ...] [--sobrescrever]

Copia do banco de origem a ESTRUTURA (tabelas, índices, views e gatilhos) e as LINHAS apenas das tabelas de catálogo
informadas (padrão: Exames_Catalogo e Regras_Complementares). Pacientes, consultas, exames solicitados, resultados e
anexos ficam VAZIOS. O arquivo de destino é construído do zero (nunca é cópia de bytes do original), logo não carrega
páginas livres nem resíduos de dados apagados. Imprime somente contagens, nunca conteúdo de linhas.

Código de saída: 0 = ok; 1 = falha de verificação; 2 = erro de uso.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

TABELAS_CATALOGO_PADRAO = ("Exames_Catalogo", "Regras_Complementares")


class ErroModelo(Exception):
    pass


def _aspas(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _contar(conexao, tabela: str) -> int:
    return conexao.execute(f"SELECT COUNT(*) FROM {_aspas(tabela)}").fetchone()[0]


def gerar(origem, destino, copiar_linhas=TABELAS_CATALOGO_PADRAO, sobrescrever: bool = False) -> dict:
    """Gera o banco-modelo e devolve {tabela: {'linhas': n, 'copiadas': bool}} (já verificado)."""
    origem, destino = Path(origem), Path(destino)
    if not origem.is_file():
        raise ErroModelo(f"banco de origem não encontrado: {origem}")
    if destino.exists() and origem.resolve() == destino.resolve():
        raise ErroModelo("origem e destino são o mesmo arquivo")
    if destino.exists() and not sobrescrever:
        raise ErroModelo(f"o destino já existe: {destino} (use --sobrescrever para substituí-lo)")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".gerando")
    if temporario.exists():
        temporario.unlink()
    try:
        src = sqlite3.connect(origem.resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise ErroModelo(f"não foi possível abrir a origem: {type(exc).__name__}") from exc
    try:
        try:
            objetos = src.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name").fetchall()
        except sqlite3.DatabaseError as exc:
            raise ErroModelo(f"a origem não parece ser um banco SQLite válido: {exc}") from exc
        tabelas = [(n, sql) for t, n, sql in objetos if t == "table"]
        nomes = {n for n, _ in tabelas}
        faltando = [t for t in copiar_linhas if t not in nomes]
        if faltando:
            raise ErroModelo("tabela(s) de catálogo inexistente(s) na origem: " + ", ".join(faltando))
        dst = sqlite3.connect(str(temporario))
        try:
            dst.execute("BEGIN")
            for _, sql in tabelas:
                dst.execute(sql)
            for tabela in copiar_linhas:                      # linhas SÓ das tabelas de catálogo
                cursor = src.execute(f"SELECT * FROM {_aspas(tabela)} ORDER BY rowid")
                marcas = ", ".join("?" * len(cursor.description))
                dst.executemany(f"INSERT INTO {_aspas(tabela)} VALUES ({marcas})", cursor)
            for tipo, _, sql in objetos:                       # índices, views e gatilhos DEPOIS (gatilho não dispara na cópia)
                if tipo != "table":
                    dst.execute(sql)
            dst.execute("COMMIT")
            resumo = {}
            for nome, _ in tabelas:
                n = _contar(dst, nome)
                copiada = nome in copiar_linhas
                if copiada and n != _contar(src, nome):
                    raise ErroModelo(f"contagem divergente na tabela {nome}")
                if not copiada and n != 0:
                    raise ErroModelo(f"a tabela {nome} deveria estar vazia, mas tem {n} linha(s)")
                resumo[nome] = {"linhas": n, "copiadas": copiada}
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ErroModelo("o banco-modelo gerado não passou na verificação de integridade")
        finally:
            dst.close()
        os.replace(temporario, destino)
        return resumo
    except BaseException:
        if temporario.exists():
            temporario.unlink()
        raise
    finally:
        src.close()


def _saida_tolerante() -> None:
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar:
        reconfigurar(errors="replace")


def main(argv=None) -> int:
    _saida_tolerante()
    ap = argparse.ArgumentParser(description="Gera o banco-modelo sanitizado embutido no executável.")
    ap.add_argument("--origem", default="clinica.db")
    ap.add_argument("--destino", default=os.path.join("modelo_banco", "clinica.db"))
    ap.add_argument("--copiar-linhas", nargs="+", default=list(TABELAS_CATALOGO_PADRAO), metavar="TABELA",
                    help="tabelas de catálogo cujas LINHAS serão copiadas (padrão: %(default)s)")
    ap.add_argument("--sobrescrever", action="store_true", help="substitui o destino se já existir")
    args = ap.parse_args(argv)
    try:
        resumo = gerar(args.origem, args.destino, args.copiar_linhas, args.sobrescrever)
    except ErroModelo as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    print(f"Banco-modelo gerado em: {args.destino}")
    for nome, info in sorted(resumo.items()):
        print(f"  {nome}: {info['linhas']} linha(s) " + ("(catálogo copiado)" if info["copiadas"] else "(somente estrutura)"))
    print("Verificado: integridade ok; tabelas que não são de catálogo estão vazias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
