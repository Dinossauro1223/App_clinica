"""Integração do serviço único de banco ao aplicativo (Fase 0, ADR-0004): main.py, setup_db.py e mapa_db.py.

`main` é importado com customtkinter/tkinter SUBSTITUÍDOS por stubs (como em test_ui_smoke.py): nenhuma janela é aberta.
Todos os bancos são SINTÉTICOS e temporários; nenhum dado real é usado.
"""
import importlib
import importlib.util
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


class _Falso:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, nome):
        return mock.MagicMock()


def stub_gui():
    """Módulos falsos de customtkinter/tkinter: nomes com inicial maiúscula viram CLASSES; o resto, MagicMock."""
    def modulo(nome):
        m = types.ModuleType(nome)
        m.__getattr__ = lambda attr: type(attr, (_Falso,), {}) if attr[:1].isupper() else mock.MagicMock()
        return m
    ctk, tk = modulo("customtkinter"), modulo("tkinter")
    ttk, mb, fd = modulo("tkinter.ttk"), modulo("tkinter.messagebox"), modulo("tkinter.filedialog")
    tk.ttk, tk.messagebox, tk.filedialog = ttk, mb, fd
    return {"customtkinter": ctk, "tkinter": tk, "tkinter.ttk": ttk,
            "tkinter.messagebox": mb, "tkinter.filedialog": fd}


def tabelas(caminho):
    with sqlite3.connect(str(caminho)) as c:
        return {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def consulta(caminho, sql):
    conn = sqlite3.connect(str(caminho))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


DEPENDENCIAS_DO_APP = ("fpdf", "PIL", "openpyxl", "matplotlib")
FALTANDO = [m for m in DEPENDENCIAS_DO_APP if importlib.util.find_spec(m) is None]


@unittest.skipIf(FALTANDO, "faltam bibliotecas do projeto neste Python: " + ", ".join(FALTANDO)
                 + " (python -m pip install -r requirements.txt)")
class BaseApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._modulos = mock.patch.dict(sys.modules, stub_gui())
        cls._modulos.start()
        for nome in ("main", "mapa_ui"):
            sys.modules.pop(nome, None)
        cls.main = importlib.import_module("main")

    @classmethod
    def tearDownClass(cls):
        cls._modulos.stop()      # restaura sys.modules (remove main/mapa_ui importados com stubs)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("NUTRILAB_DB_PATH", None)
        os.environ.pop("NUTRILAB_DATA_DIR", None)
        self.app = types.SimpleNamespace()

    def usar_banco(self, nome="clinica.db"):
        caminho = self.tmp / nome
        os.environ["NUTRILAB_DB_PATH"] = str(caminho)
        return caminho


class TestCodigoFonte(unittest.TestCase):
    ARQUIVOS = ("main.py", "setup_db.py", "mapa_db.py", "mapa_ui.py", "mapa_export.py", "mapa_graficos.py",
                "nutri_calculos.py")

    def test_nenhum_ponto_monta_o_caminho_do_banco_fora_do_servico_unico(self):
        padroes = (r"get_base_path\(\)\s*,\s*['\"]clinica\.db['\"]",
                   r"get_writable_path\(\s*['\"]clinica\.db['\"]\s*\)",
                   r"sqlite3\.connect\(\s*['\"]clinica\.db['\"]\s*\)")
        for nome in self.ARQUIVOS:
            texto = (RAIZ / nome).read_text(encoding="utf-8")
            for padrao in padroes:
                with self.subTest(arquivo=nome, padrao=padrao):
                    self.assertIsNone(re.search(padrao, texto))

    def test_anexos_de_pacientes_nao_usam_a_pasta_de_recursos(self):
        texto = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r'os\.path\.join\(\s*base_dir,\s*"arquivos_pacientes"', texto))
        # Os pontos de acesso a arquivos do paciente incluem agora a verificação de
        # existência/contagem para bloquear exclusão se houver arquivos persistidos.
        # Os locais que gravam anexos continuam usando a pasta externa ao bundle.
        self.assertEqual(texto.count('get_writable_path("arquivos_pacientes")'), 4)


class TestCaminhoDoBanco(BaseApp):
    def test_desenvolvimento_usa_a_pasta_do_projeto(self):
        self.assertEqual(Path(self.main.caminho_do_banco()), RAIZ / "clinica.db")

    def test_executavel_usa_a_pasta_do_exe_e_nunca_a_interna(self):
        exe = self.tmp / "app" / "app_clinica.exe"
        interna = exe.parent / "_internal"
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", str(exe)), \
                mock.patch.object(sys, "_MEIPASS", str(interna), create=True):
            caminho = Path(self.main.caminho_do_banco())
        self.assertEqual(caminho, exe.parent.resolve() / "clinica.db")
        self.assertNotIn("_internal", caminho.parts)

    def test_executavel_copia_o_modelo_embutido_so_na_primeira_execucao(self):
        exe = self.tmp / "app" / "app_clinica.exe"
        interna = exe.parent / "_internal"
        interna.mkdir(parents=True)
        modelo = interna / "modelo_banco" / "clinica.db"
        modelo.parent.mkdir(parents=True)
        with sqlite3.connect(str(modelo)) as c:
            c.execute("CREATE TABLE Modelo (x TEXT)")
            c.execute("INSERT INTO Modelo VALUES ('do-modelo')")
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", str(exe)), \
                mock.patch.object(sys, "_MEIPASS", str(interna), create=True):
            primeiro = Path(self.main.caminho_do_banco())
            self.assertEqual(consulta(primeiro, "SELECT x FROM Modelo"), [("do-modelo",)])
            with sqlite3.connect(str(primeiro)) as c:
                c.execute("INSERT INTO Modelo VALUES ('do-usuario')")
            segundo = Path(self.main.caminho_do_banco())
        self.assertEqual(primeiro, segundo)
        self.assertEqual(consulta(segundo, "SELECT x FROM Modelo ORDER BY rowid"), [("do-modelo",), ("do-usuario",)])


class TestConfigurarBancoDados(BaseApp):
    ESQUEMA = {"Consultas", "Exames_Solicitados", "Arquivos_Paciente", "Exames_Catalogo",
               "Regras_Complementares", "Resultados_Exames"}
    CONDUTAS_ALTA = {"Condutas_Alta_Docs", "Condutas_Alta_Itens"}      # migração 2
    AMBULATORIAL = {
        "Consulta_Dados_Estruturados", "Consulta_Medicamentos", "Consulta_Metas",
        "Recomendacoes_Docs", "Consulta_Recomendacoes", "Exames_Associacoes", "Consulta_Triagens",
    }                                                                    # migração 4
    ALMOX = {
        "Almox_Itens", "Almox_Historico_Preco", "Almox_Movimentos",
        "Almox_Programacoes", "Almox_Programacao_Itens",
    }                                                                    # migração 5
    PEP = {"Pep_Config", "Pep_Usuarios", "Pep_Evolucoes", "Pep_Equipe", "Pep_Rascunhos",
           "Pep_Rascunho_Historico", "Pep_Evolucao_Metadados", "Pep_Rascunho_Equipe",
           "Pep_Evolucao_Equipe", "Mapa_Evolucao_Dados"}                # migrações 6–8

    def test_banco_novo_cria_o_esquema_e_registra_a_baseline_sem_backup(self):
        caminho = self.usar_banco()
        self.main.AppClinica.configurar_banco_dados(self.app)
        self.assertEqual(
            tabelas(caminho),
            self.ESQUEMA | self.CONDUTAS_ALTA | self.AMBULATORIAL | self.ALMOX | self.PEP
            | {"HGT_Registros", "PA_Registros", "Suplemento_Substituicoes", "schema_migrations"},
        )
        self.assertGreater(consulta(caminho, "SELECT COUNT(*) FROM Exames_Catalogo")[0][0], 15)
        self.assertEqual(consulta(caminho, "SELECT COUNT(*) FROM Regras_Complementares"), [(1,)])
        self.assertEqual(consulta(caminho, "SELECT versao, origem FROM schema_migrations"),
                         [(1, "banco-novo")] + [(m.versao, "migracao") for m in self.main.db_migracoes.MIGRACOES[1:]])
        self.assertFalse((self.tmp / "backups").exists())

    def test_executar_de_novo_nao_duplica_nada(self):
        caminho = self.usar_banco()
        for _ in range(3):
            self.main.AppClinica.configurar_banco_dados(self.app)
        self.assertGreater(consulta(caminho, "SELECT COUNT(*) FROM Exames_Catalogo")[0][0], 15)
        self.assertEqual(consulta(caminho, "SELECT COUNT(*) FROM Regras_Complementares"), [(1,)])
        self.assertEqual(consulta(caminho, "SELECT COUNT(*) FROM schema_migrations"),
                         [(len(self.main.db_migracoes.MIGRACOES),)])

    def test_banco_legado_existente_adota_a_baseline_com_backup_e_sem_perder_dados(self):
        caminho = self.usar_banco()
        self.main.AppClinica.configurar_banco_dados(self.app)
        self.main.mapa_db.inicializar(str(caminho))             # cria Pacientes e Mapa_* como no aplicativo
        with sqlite3.connect(str(caminho)) as c:
            c.execute("INSERT INTO Pacientes (nome, data_nascimento, sexo) VALUES ('Paciente Sintético 001', '01/01/1960', 'F')")
            c.execute("INSERT INTO Consultas (id_paciente, data_consulta, anamnese) VALUES (1, '01/11/2026', 'consulta sintética')")
            c.execute("DROP TABLE schema_migrations")             # simula um banco criado ANTES da Fase 0
        antes = {t: consulta(caminho, f"SELECT * FROM {t}") for t in ("Pacientes", "Consultas", "Exames_Catalogo")}
        self.main.AppClinica.configurar_banco_dados(self.app)
        self.assertEqual(consulta(caminho, "SELECT versao, origem FROM schema_migrations"),
                         [(1, "adotada-legado")]
                         + [(m.versao, "migracao") for m in self.main.db_migracoes.MIGRACOES[1:]])
        depois = {t: consulta(caminho, f"SELECT * FROM {t}") for t in antes}
        self.assertEqual(depois, antes)
        ultima = self.main.db_migracoes.MIGRACOES[-1].versao        # o nome do backup usa a versão de destino
        backups = list((self.tmp / "backups").glob(f"clinica.backup_*_pre-migracao-v{ultima}.db"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(consulta(backups[0], "SELECT nome FROM Pacientes"), [("Paciente Sintético 001",)])

    def test_banco_e_um_unico_arquivo_para_telas_de_pacientes_e_mapa(self):
        caminho = self.usar_banco()
        self.main.AppClinica.configurar_banco_dados(self.app)
        self.main.mapa_db.inicializar(self.main.caminho_do_banco())
        todas = tabelas(caminho)
        self.assertTrue({"Pacientes", "Consultas", "Mapa_Leitos", "Mapa_Registros"} <= todas)
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["clinica.db"])

    def test_falha_ao_registrar_a_versao_avisa_mas_nao_impede_o_programa(self):
        caminho = self.usar_banco()
        with mock.patch.object(self.main.db_migracoes, "aplicar_migracoes", side_effect=RuntimeError("falha simulada")), \
                mock.patch.object(self.main.messagebox, "showwarning") as aviso:
            self.main.AppClinica.configurar_banco_dados(self.app)
        aviso.assert_called_once()
        self.assertIn("falha simulada", aviso.call_args[0][1])
        self.assertTrue(self.ESQUEMA <= tabelas(caminho))        # o esquema legado foi criado mesmo assim


class TestBancoDividido(BaseApp):
    """Detecção (somente leitura) de pacientes em `_internal`, herança da 'divisão de banco' do executável."""

    def _cenario(self, pacientes_no_interno):
        exe = self.tmp / "app" / "app_clinica.exe"
        interna = exe.parent / "_internal"
        interna.mkdir(parents=True)
        for pasta in (exe.parent, interna):
            with sqlite3.connect(str(pasta / "clinica.db")) as c:
                c.execute("CREATE TABLE Pacientes (id_paciente INTEGER PRIMARY KEY, nome TEXT)")
        if pacientes_no_interno:
            with sqlite3.connect(str(interna / "clinica.db")) as c:
                c.execute("INSERT INTO Pacientes (nome) VALUES ('Paciente Sintético 001')")
        return exe, interna

    def _frozen(self, exe, interna):
        return mock.patch.multiple(sys, frozen=True, executable=str(exe), _MEIPASS=str(interna), create=True)

    def test_detecta_paciente_no_banco_de_internal_sem_alterar_nada(self):
        exe, interna = self._cenario(pacientes_no_interno=True)
        antes = {p: p.read_bytes() for p in (exe.parent / "clinica.db", interna / "clinica.db")}
        with self._frozen(exe, interna):
            achado = self.main.banco_interno_com_dados(str(exe.parent / "clinica.db"))
        self.assertEqual(Path(achado), interna / "clinica.db")
        self.assertEqual({p: p.read_bytes() for p in antes}, antes)

    def test_modelo_sem_pacientes_em_internal_nao_e_divisao(self):
        exe, interna = self._cenario(pacientes_no_interno=False)
        with self._frozen(exe, interna):
            self.assertIsNone(self.main.banco_interno_com_dados(str(exe.parent / "clinica.db")))

    def test_em_desenvolvimento_nunca_ha_divisao(self):
        self.assertIsNone(self.main.banco_interno_com_dados(str(self.tmp / "clinica.db")))

    def test_configurar_banco_dados_avisa_quando_ha_divisao(self):
        exe, interna = self._cenario(pacientes_no_interno=True)
        with self._frozen(exe, interna), mock.patch.object(self.main.messagebox, "showwarning") as aviso:
            self.main.AppClinica.configurar_banco_dados(self.app)
        titulos = [c[0][0] for c in aviso.call_args_list]
        self.assertIn("Dois bancos de dados encontrados", titulos)
        texto = next(c[0][1] for c in aviso.call_args_list if c[0][0] == "Dois bancos de dados encontrados")
        self.assertIn(str(interna / "clinica.db"), texto)
        self.assertIn("NÃO apague", texto)


class TestSetupDb(BaseApp):
    def test_setup_db_cria_o_banco_no_caminho_unico_e_nao_na_pasta_atual(self):
        caminho = self.usar_banco("setup.db")
        outra_pasta = self.tmp / "outra"
        outra_pasta.mkdir()
        setup_db = importlib.import_module("setup_db")
        atual = os.getcwd()
        os.chdir(outra_pasta)
        try:
            setup_db.inicializar_banco().close()
        finally:
            os.chdir(atual)
        self.assertTrue(caminho.is_file())
        self.assertFalse((outra_pasta / "clinica.db").exists())
        self.assertIn("Pacientes", tabelas(caminho))


if __name__ == "__main__":
    unittest.main()
