"""Testes de tools/auditar_repositorio.py.

Usa repositórios Git temporários e arquivos 100% sintéticos. Valores com aparência de CPF, e-mail,
telefone, chave ou token são MONTADOS EM TEMPO DE EXECUÇÃO para o próprio repositório não se auto-sinalizar.
"""
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import auditar_repositorio as aud

GITIGNORE_COMPLETO = "\n".join([
    "*.db", "*.db-*", "*.sqlite", "*.sqlite3", "*.sqlite-*", "*.backup", "*.backup_*", "*.bak",
    "/arquivos_pacientes/", "**/arquivos_pacientes/", "/backups/",
    ".env", ".env.*", "!.env.example", "*.pem", "*.key", "*.p12", "*.pfx",
    "/CONTROLE DE REFEIÇÕES*.xlsx", "/CONTROLE DE FICHAS*.xlsx", "/Controle da Nutrição*.xlsx",
    "/Mapa_externo*.xlsx", "/Evolucao_nutricional_pacientes*.pdf", "/logs/",
]) + "\n"

CPF_VALIDO_DIGITOS = "12345678909"    # exemplo clássico de CPF com dígitos verificadores corretos
CPF_INVALIDO_DIGITOS = "12345678900"


def _formatar_cpf(d):
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def _git(raiz, *args):
    return subprocess.run(["git", "-C", str(raiz), "-c", "commit.gpgsign=false", *args],
                          check=True, capture_output=True, text=True)


class RepoTemporario:
    """Repositório Git descartável para os testes."""

    def __init__(self, gitignore=GITIGNORE_COMPLETO):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.raiz = Path(self._tmp.name)
        _git(self.raiz, "init", "-q")
        _git(self.raiz, "config", "user.email", "teste@example.com")
        _git(self.raiz, "config", "user.name", "Teste")
        if gitignore is not None:
            self.escrever(".gitignore", gitignore)

    def escrever(self, rel, conteudo="x\n"):
        caminho = self.raiz / rel
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(conteudo, bytes):
            caminho.write_bytes(conteudo)
        else:
            caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def commit(self, mensagem="teste"):
        _git(self.raiz, "add", "-A")
        _git(self.raiz, "commit", "-q", "-m", mensagem)

    def remover_e_commitar(self, rel):
        _git(self.raiz, "rm", "-q", "--", rel)
        _git(self.raiz, "commit", "-q", "-m", f"remove {rel}")

    def limpar(self):
        self._tmp.cleanup()


class BaseRepo(unittest.TestCase):
    def novo_repo(self, **kw):
        repo = RepoTemporario(**kw)
        self.addCleanup(repo.limpar)
        return repo

    @staticmethod
    def achados(repo, **kw):
        kw.setdefault("historico", False)
        return aud.auditar(repo.raiz, **kw)

    @staticmethod
    def categorias(achados, nivel=None):
        return {(a.nivel, a.categoria) for a in achados if nivel in (None, a.nivel)}


class TestClassificarCaminho(unittest.TestCase):
    def test_bloqueios_por_caminho(self):
        casos = {
            "clinica.db": "banco-sqlite",
            "dados/clinica.DB-wal": "banco-sqlite",
            "x/clinica.sqlite3": "banco-sqlite",
            "clinica.db.backup_20261109": "backup",
            "copia.bak": "backup",
            "arquivos_pacientes/a.txt": "pasta-de-pacientes",
            "sub/Arquivos_Pacientes/a.txt": "pasta-de-pacientes",
            "backups/qualquer.txt": "pasta-de-dados-locais",
            ".env": "segredo",
            ".env.producao": "segredo",
            "certs/CHAVE.PEM": "segredo",
            "CONTROLE_DE_REFEIÇÕES_-_Outubro_2026__1_.xlsx": "planilha-hospitalar",
            "CONTROLE_DE_FICHAS_ALMOÇO_E_JANTAR_-_OUTBRO_2026__1_.xlsx": "planilha-hospitalar",
            "Controle da Nutrição - Outubro 2026.xlsx": "planilha-hospitalar",
            "Mapa_externo_novo_layout__1_.xlsx": "planilha-hospitalar",
            "CÁLCULOS_ESTIMATIVA_DE_PESO_E_ESTATURA__2_.xlsx": "planilha-hospitalar",
            "Evolucao_nutricional_pacientes_docx.pdf": "planilha-hospitalar",
        }
        for caminho, categoria in casos.items():
            with self.subTest(caminho=caminho):
                self.assertIn((aud.BLOQUEIO, categoria), aud.classificar_caminho(caminho))

    def test_documentos_genericos_pedem_revisao(self):
        for caminho, categoria in {"docs/modelo.xlsx": "documento-binario", "dados/pacote.zip": "documento-binario",
                                   "credentials.json": "possivel-credencial"}.items():
            with self.subTest(caminho=caminho):
                self.assertEqual(aud.classificar_caminho(caminho), [(aud.REVISAR, categoria)])

    def test_caminhos_inofensivos(self):
        for caminho in ("README.md", "main.py", ".env.example", "src/backups/util.py", "tests/test_x.py",
                        "docs/imagem.png", "dados/referencias/oms_lms.csv"):
            with self.subTest(caminho=caminho):
                self.assertEqual(aud.classificar_caminho(caminho), [])


class TestEscanearTexto(unittest.TestCase):
    def test_cpf_so_com_digitos_verificadores_corretos(self):
        valido = _formatar_cpf(CPF_VALIDO_DIGITOS)
        invalido = _formatar_cpf(CPF_INVALIDO_DIGITOS)
        self.assertEqual(aud.escanear_texto(f"a\nCPF {valido}\n"), [(aud.BLOQUEIO, "cpf-valido", 2)])
        self.assertEqual(aud.escanear_texto(f"CPF {invalido}"), [])
        self.assertEqual(aud.escanear_texto("protocolo 111.111.111-11"), [])   # sequência repetida não é CPF

    def test_email_telefone_e_dominios_permitidos(self):
        externo = "fulano" + "@" + "hospital-exemplo.org.br"
        telefone = "(81) " + "99999-9999"
        texto = "\n".join([f"contato {externo}", "ok a" + "@" + "example.com", "noreply" + "@" + "anthropic.com", f"tel {telefone}"])
        self.assertEqual(aud.escanear_texto(texto), [(aud.REVISAR, "email", 1), (aud.REVISAR, "telefone", 4)])

    def test_segredos_e_chaves(self):
        chave = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"
        token = "ghp" + "_" + "A" * 36
        aws = "AKIA" + "ABCDEFGHIJKLMNOP"
        senha = "pass" + 'word = "S3nh4Real123"'
        placeholder = "pass" + 'word = "changeme"'
        achados = aud.escanear_texto("\n".join([chave, token, aws, senha, placeholder]))
        self.assertEqual(achados, [(aud.BLOQUEIO, "chave-privada", 1), (aud.BLOQUEIO, "token-github", 2),
                                   (aud.BLOQUEIO, "chave-aws", 3), (aud.REVISAR, "segredo-atribuido", 4)])

    def test_limita_achados_repetidos_por_arquivo(self):
        texto = "\n".join(_formatar_cpf(CPF_VALIDO_DIGITOS) for _ in range(50))
        self.assertEqual(len(aud.escanear_texto(texto)), aud.MAX_ACHADOS_POR_CATEGORIA_E_ARQUIVO)


class TestAuditoriaDeRepositorio(BaseRepo):
    def test_repositorio_limpo_nao_tem_achados(self):
        repo = self.novo_repo()
        repo.escrever("main.py", "print('ok')\n")
        repo.escrever("README.md", "# Projeto\n")
        repo.commit()
        self.assertEqual(self.achados(repo), [])

    def test_banco_rastreado_e_bloqueio(self):
        repo = self.novo_repo(gitignore=None)
        repo.escrever("clinica.db", b"SQLite format 3\x00")
        repo.commit()
        achados = self.achados(repo)
        self.assertIn(aud.Achado(aud.BLOQUEIO, "banco-sqlite", "clinica.db", "rastreado"), achados)

    def test_arquivo_nao_rastreado_e_nao_ignorado_e_sinalizado(self):
        repo = self.novo_repo(gitignore=None)
        repo.escrever("clinica.db", b"SQLite format 3\x00")
        achados = self.achados(repo)
        self.assertIn(aud.Achado(aud.BLOQUEIO, "banco-sqlite", "clinica.db", "nao-rastreado"), achados)

    def test_arquivo_ignorado_pelo_gitignore_nao_e_sinalizado(self):
        repo = self.novo_repo()
        repo.escrever("clinica.db", b"SQLite format 3\x00")
        repo.escrever("main.py", "x = 1\n")
        repo.commit()
        self.assertEqual(self.achados(repo), [])

    def test_cpf_no_conteudo_e_bloqueio_e_nunca_aparece_no_relatorio(self):
        cpf = _formatar_cpf(CPF_VALIDO_DIGITOS)
        repo = self.novo_repo()
        repo.escrever("dados/exemplo.json", json.dumps({"documento": cpf}))
        repo.commit()
        achados = self.achados(repo)
        cpfs = [a for a in achados if a.categoria == "cpf-valido"]
        self.assertEqual(len(cpfs), 1)
        self.assertEqual((cpfs[0].nivel, cpfs[0].caminho, cpfs[0].linha), (aud.BLOQUEIO, "dados/exemplo.json", 1))
        relatorio = aud.formatar_relatorio(achados)
        self.assertNotIn(cpf, relatorio)
        self.assertNotIn(CPF_VALIDO_DIGITOS, relatorio.replace(".", "").replace("-", ""))

    def test_historico_detecta_arquivo_sensivel_ja_removido(self):
        repo = self.novo_repo(gitignore=None)
        repo.escrever("clinica.db", b"SQLite format 3\x00")
        repo.escrever("main.py", "x = 1\n")
        repo.commit("adiciona banco por engano")
        repo.remover_e_commitar("clinica.db")
        repo.escrever(".gitignore", GITIGNORE_COMPLETO)
        repo.commit("ignora bancos")
        achados = aud.auditar(repo.raiz, historico=True)
        historicos = [a for a in achados if a.origem == "historico"]
        self.assertEqual([(a.nivel, a.categoria, a.caminho) for a in historicos],
                         [(aud.BLOQUEIO, "banco-sqlite", "clinica.db")])
        self.assertTrue(historicos[0].detalhe.startswith("commit "))
        self.assertEqual([a for a in aud.auditar(repo.raiz, historico=False) if a.origem == "historico"], [])

    def test_repositorio_sem_commits_nao_quebra_o_historico(self):
        repo = self.novo_repo()
        self.assertEqual(aud.auditar(repo.raiz, historico=True), [])

    def test_gitignore_incompleto_gera_revisao_por_sonda(self):
        repo = self.novo_repo(gitignore="# vazio\n")
        achados = self.achados(repo)
        sondas = [a for a in achados if a.categoria == "gitignore-sem-padrao"]
        self.assertEqual(len(sondas), len(aud.SONDAS_GITIGNORE))
        self.assertTrue(all(a.nivel == aud.REVISAR for a in sondas))

    def test_lista_de_permissao_libera_revisar_mas_nunca_bloqueio(self):
        repo = self.novo_repo(gitignore=None)
        repo.escrever("docs/modelo.xlsx", b"PK\x03\x04")
        repo.escrever("clinica.db", b"SQLite format 3\x00")
        repo.escrever(".gitignore", GITIGNORE_COMPLETO)
        _git(repo.raiz, "add", "-f", "clinica.db", "docs/modelo.xlsx", ".gitignore")
        _git(repo.raiz, "commit", "-q", "-m", "x")
        sem = self.categorias(self.achados(repo))
        self.assertIn((aud.REVISAR, "documento-binario"), sem)
        com = self.categorias(self.achados(repo, permitir=["*"]))
        self.assertNotIn((aud.REVISAR, "documento-binario"), com)
        self.assertIn((aud.BLOQUEIO, "banco-sqlite"), com)

    def test_arquivo_de_permissoes_do_repositorio(self):
        repo = self.novo_repo()
        repo.escrever("tools/auditoria_permitidos.txt", "# modelos sintéticos\ndocs/*.xlsx   # planilha vazia\n\n")
        self.assertEqual(aud.ler_permitidos(repo.raiz, ["extra/*"]), ["extra/*", "docs/*.xlsx"])


class TestMain(BaseRepo):
    def _executar(self, *argv):
        saida, erro = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = aud.main(list(argv))
        return codigo, saida.getvalue(), erro.getvalue()

    def test_codigos_de_saida(self):
        repo = self.novo_repo()
        repo.escrever("docs/modelo.xlsx", b"PK\x03\x04")
        repo.commit()
        raiz = str(repo.raiz)
        self.assertEqual(self._executar("--raiz", raiz)[0], 0)                      # só REVISAR
        self.assertEqual(self._executar("--raiz", raiz, "--estrito")[0], 1)         # REVISAR reprova no estrito
        self.assertEqual(self._executar("--raiz", raiz, "--estrito", "--permitir", "docs/*.xlsx")[0], 0)
        repo.escrever(".env", "A=1\n")
        _git(repo.raiz, "add", "-f", ".env")
        _git(repo.raiz, "commit", "-q", "-m", "segredo por engano")
        codigo, saida, _ = self._executar("--raiz", raiz)
        self.assertEqual(codigo, 1)
        self.assertIn("[BLOQUEIO] segredo", saida)
        self.assertIn("NÃO faça push", saida)

    def test_fora_de_repositorio_retorna_2(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            codigo, _, erro = self._executar("--raiz", d)
        self.assertEqual(codigo, 2)
        self.assertIn("Erro:", erro)

    def test_saida_json_nao_contem_conteudo(self):
        cpf = _formatar_cpf(CPF_VALIDO_DIGITOS)
        repo = self.novo_repo()
        repo.escrever("dados/x.txt", f"doc {cpf}\n")
        repo.commit()
        destino = repo.raiz.parent / (repo.raiz.name + "-achados.json")
        self.addCleanup(lambda: destino.unlink(missing_ok=True))
        self._executar("--raiz", str(repo.raiz), "--json", str(destino))
        bruto = destino.read_text(encoding="utf-8")
        self.assertNotIn(CPF_VALIDO_DIGITOS, bruto.replace(".", "").replace("-", ""))
        self.assertEqual(json.loads(bruto)[0]["categoria"], "cpf-valido")


if __name__ == "__main__":
    unittest.main()
