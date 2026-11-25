# Copyright (c) 2026 Neis Bila de Alencar. Todos os direitos reservados.
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import os
import math
import threading
import socket
import importlib.util
import json
import shutil
import sys
import platform
import re
from datetime import datetime
from fpdf import FPDF
from PIL import Image
import mapa_db
import integracao_mobile as im
import db_service
import pacientes_integridade
import db_migracoes
from db_esquema_legado import garantir_esquema_legado
import atalhos_edicao
import tema
from mapa_ui import MapaUI, DialogCurvasOMS
from tela_boas_vindas import TelaBoasVindas
from navegacao_ui import BarraLateral, PilhaAbasLaterais
from condutas_alta_ui import PainelCondutasAlta, lembrar_condutas_pendentes
import ambulatorial
import pediatria_oms as oms
import atualizador
import ui_motion
from backup_manager import BackupManager
from ambulatorial_ui import PainelConsultaEstruturada, DialogoAssociacoesExames


def get_base_path():
    """Retorna o diretório de recursos da aplicação.

    Em executável PyInstaller (--onedir), os arquivos embutidos via
    datas=[] ficam em sys._MEIPASS (pasta _internal); caso contrário,
    o diretório do próprio script.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_writable_path(filename):
    """Retorna um caminho gravável para arquivos como o banco de dados.

    No executável, copia o arquivo embutido (_MEIPASS) para ao lado do
    .exe na primeira execução, permitindo escrita sem tocar no bundle.
    """
    if getattr(sys, 'frozen', False):
        base_exe = os.path.dirname(sys.executable)
        destino = os.path.join(base_exe, filename)
        if not os.path.exists(destino):
            embutido = os.path.join(get_base_path(), filename)
            if os.path.exists(embutido):
                try:
                    shutil.copy2(embutido, destino)
                except OSError:
                    return embutido
        return destino
    return os.path.join(get_base_path(), filename)


def caminho_do_banco():
    """Caminho ÚNICO do banco (db_service.caminho_banco; ADR-0001).

    Em desenvolvimento é a pasta do projeto; no executável, a pasta do .exe — nunca `_internal`/`_MEIPASS`.
    Na primeira execução do executável, se houver um banco-modelo embutido (em `_MEIPASS`), ele é copiado para o local
    gravável; depois disso o banco do usuário nunca é sobrescrito.
    """
    destino = db_service.caminho_banco()
    if db_service.esta_empacotado() and not destino.exists():
        embutido = os.path.join(get_base_path(), "modelo_banco", destino.name)
        if os.path.exists(embutido):
            try:
                shutil.copy2(embutido, destino)
            except OSError:
                pass  # sem permissão de escrita: o SQLite criará um banco novo (vazio) no destino
    return str(destino)


tema.configurar_ctk()

def banco_interno_com_dados(destino):
    """Executável: devolve o caminho de OUTRO banco (em `_MEIPASS`/`_internal`) que contenha pacientes, ou None.

    Versões anteriores gravavam pacientes em `_internal/clinica.db`; o programa agora usa só `destino`. Esta checagem
    apenas DETECTA a divisão (somente leitura): nada é copiado, movido ou apagado.
    """
    if not db_service.esta_empacotado():
        return None
    interno = os.path.join(get_base_path(), os.path.basename(str(destino)))
    if not os.path.exists(interno) or not os.path.exists(destino) or os.path.samefile(interno, destino):
        return None
    try:
        conexao = sqlite3.connect(db_service.Path(interno).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            return interno if conexao.execute("SELECT COUNT(*) FROM Pacientes").fetchone()[0] > 0 else None
        finally:
            conexao.close()
    except sqlite3.Error:
        return None


def _criar_tabview_compat(master, fonte_abas=None, **kwargs):
    """Cria CTkTabview sem depender de argumentos exclusivos do CustomTkinter 6.x."""
    tab = ctk.CTkTabview(master, **kwargs)
    if fonte_abas is not None:
        try:
            tab._segmented_button.configure(font=fonte_abas)
        except (AttributeError, tk.TclError):
            pass
    return tab


class AppClinica(ctk.CTk):
    def __init__(self):
        super().__init__()
        tema.aplicar_tema_ttk(self)

        # Atalhos de edição no estilo do Google Planilhas (Ctrl+Z, Ctrl+Y, F4, colar de planilha, Ctrl+C nas tabelas).
        # Vale para todos os campos e tabelas de todas as janelas; a lista aparece com F1 (docs/desenvolvimento/ATALHOS_DE_TECLADO.md).
        atalhos_edicao.instalar(self)

        self.title("Sistema de Gestão Clínica")
        self.geometry("950x750")
        try:
            self.state("zoomed")
        except tk.TclError:
            self.geometry("1280x800")
        self.attributes("-fullscreen", False)
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.configurar_banco_dados()

        # Mapa Nutricional: usa o mesmo banco da tela Pacientes (get_base_path) para unificar os dados.
        db_mapa = caminho_do_banco()
        mapa_db.inicializar(db_mapa)
        self.mapa = MapaUI(self, db_mapa, get_base_path())

        self.paciente_atual_id = None
        self.paciente_atual_nome = None
        self.paciente_atual_nasc = None
        self.paciente_atual_sexo = None
        self.exames_selecionados_lista = []
        self.opcoes_exames = []
        self.resultados_lancados = {}  # {id_exame: (valor, status)} preenchido no modal
        
        self.tmb_atual = ""
        self.vet_atual = ""
        self.calculos_ambulatoriais = {}
        self.painel_consulta_estruturada = None

        # --- NAVEGAÇÃO PRINCIPAL + PAINEL DE EDIÇÃO REDIMENSIONÁVEL ---
        self.area_principal_host = ctk.CTkFrame(self, corner_radius=10, fg_color=tema.FUNDO)
        self.area_principal_host.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self._layout_principal = ttk.Panedwindow(self.area_principal_host, orient=tk.HORIZONTAL)
        self._layout_principal.pack(fill="both", expand=True)
        self._pagina_host = ctk.CTkFrame(self._layout_principal, fg_color="transparent")
        self._painel_edicao_host = ctk.CTkFrame(self._layout_principal, fg_color=tema.FUNDO, width=380)
        self._painel_edicao_host.pack_propagate(False)
        self._pilha_abas_laterais = PilhaAbasLaterais(self._pagina_host)
        self._pilha_abas_laterais.pack(fill="both", expand=True)
        self._layout_principal.add(self._pagina_host, weight=1)
        self._painel_edicao_frame = None
        self._painel_edicao_shell = None
        self._painel_edicao_pilha = []
        self._largura_painel_edicao = 380
        self._layout_principal.bind("<ButtonRelease-1>", self._guardar_largura_painel_edicao, add="+")
        self.area_principal = self._pilha_abas_laterais.pagina_atual

        secoes_menu = [
            ("CLÍNICA", [
                ("👥", "Pacientes", lambda: self.abrir_pagina_principal("Pacientes", self.tela_pacientes)),
                ("🧪", "Catálogo de Exames", lambda: self.abrir_pagina_principal("Catálogo de Exames", self.tela_exames)),
            ]),
            ("MAPA NUTRICIONAL", [
                ("🗺", "Mapa Nutricional", lambda: self.abrir_pagina_principal("Mapa Nutricional", self.tela_mapa)),
                ("📊", "Gráficos do Mês", lambda: self.abrir_pagina_principal("Gráficos do Mês", self.tela_mapa_graficos)),
                ("🥣", "Suplementos", lambda: self.abrir_pagina_principal("Suplementos", self.tela_suplementos)),
                ("📦", "Almoxarifado", lambda: self.abrir_pagina_principal("Almoxarifado", self.tela_almoxarifado)),
                ("📱", "Mobile (copa)", lambda: self.abrir_pagina_principal("Mobile (copa)", self.tela_mobile)),
            ]),
            ("GESTÃO", [
                ("🍲", "Fichas e consumo da cozinha", lambda: self.abrir_pagina_principal("Fichas e consumo", self.tela_gestao_alimentar_fichas)),
            ]),
        ]
        self.menu_lateral = BarraLateral(
            self, secoes=secoes_menu,
            config=("⚙️", "Configurações", lambda: self.abrir_pagina_principal("Configurações", self.tela_configuracoes)),
            rodape="© 2026 Neis Bila de Alencar. Todos os direitos reservados."
        )
        self.bind("<Escape>", self._fechar_ultima_aba_lateral, add="+")
        self.tela_inicial()
        self._iniciar_backups()
        self._iniciar_servidor_mobile()
        # Consulta GitHub em segundo plano; indisponibilidade não bloqueia a abertura nem altera dados.
        self.after(1200, lambda: atualizador.iniciar_verificacao(self, self._resultado_atualizacao))


    def _iniciar_servidor_mobile(self):
        """Inicia o servidor local uma única vez; não assume propriedade de processo preexistente."""
        self._servidor_mobile = None
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=0.35):
                # O BAT/manual ou outra instância já atende a porta: não iniciar nem encerrar esse processo.
                return
        except OSError:
            pass

        caminho_servidor = os.path.join(get_base_path(), "mobile", "servidor.py")
        if not os.path.isfile(caminho_servidor):
            caminho_servidor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile", "servidor.py")
        try:
            spec = importlib.util.spec_from_file_location("nutrilab_servidor_mobile", caminho_servidor)
            if spec is None or spec.loader is None:
                raise RuntimeError("Não foi possível carregar mobile/servidor.py.")
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)

            # O servidor, o painel desktop e a integração devem apontar para o mesmo banco.
            caminho_db = im.caminho_mobile_db(caminho_do_banco(), get_base_path())
            senha_inicial = modulo.preparar_banco(caminho_db, False)
            # Suba a API antes de exibir o aviso modal da primeira senha: a janela não deve
            # atrasar o servidor nem impedir que o celular alcance a tela de login.
            servidor = modulo.criar_servidor(caminho_db, 8765, "0.0.0.0")
            thread = threading.Thread(target=servidor.serve_forever, name="NutriLabMobile", daemon=True)
            thread.start()
            self._servidor_mobile = servidor
            self._thread_servidor_mobile = thread
            if senha_inicial:
                messagebox.showinfo(
                    "Acesso inicial ao NutriLab Mobile",
                    "Foi criado o usuário administrador do servidor mobile.\n\n"
                    f"Usuário: admin\nSenha inicial: {senha_inicial}\n\n"
                    "Altere a senha após o primeiro acesso e guarde-a em local seguro."
                )
        except OSError as erro:
            messagebox.showwarning(
                "Servidor mobile indisponível",
                "Não foi possível iniciar o servidor mobile na porta 8765. "
                "Os módulos que não dependem dele continuarão disponíveis.\n\n"
                f"Detalhe: {erro}"
            )
        except Exception as erro:
            messagebox.showwarning(
                "Servidor mobile indisponível",
                "O NutriLab continuará funcionando, mas a integração mobile não foi iniciada.\n\n"
                f"Detalhe: {erro}"
            )

    def _encerrar_servidor_mobile(self):
        """Encerra somente o servidor criado por esta instância do desktop."""
        servidor = getattr(self, "_servidor_mobile", None)
        if servidor is not None:
            try:
                servidor.shutdown()
            except Exception:
                pass
            try:
                servidor.server_close()
            except Exception:
                pass
            self._servidor_mobile = None

    def _encerrar_e_destruir(self):
        self._encerrando_app = True
        self._encerrar_servidor_mobile()
        self.destroy()

    def _iniciar_backups(self):
        """Ativa snapshots periódicos e backup obrigatório no encerramento normal."""
        self._gerenciador_backups = BackupManager(
            self, caminho_do_banco(), on_error=self._erro_backup_automatico
        )
        self._gerenciador_backups.iniciar()

    def _erro_backup_automatico(self, erro):
        """Informa falhas sem ocultar que a proteção não foi concluída."""
        messagebox.showerror(
            "Falha no backup de segurança",
            "Não foi possível concluir o backup automático do banco de dados. "
            "O programa permanecerá aberto para evitar um encerramento sem a cópia de segurança.\n\n"
            f"Detalhe: {erro}"
        )

    def _ao_fechar(self):
        """Só encerra a interface depois de criar e validar o backup final."""
        gerenciador = getattr(self, "_gerenciador_backups", None)
        if gerenciador is None:
            self._encerrar_e_destruir()
            return
        gerenciador.fechar(ao_concluir=self._encerrar_e_destruir)

    def _resultado_atualizacao(self, resultado):
        """Exibe comparação de versões sem executar alterações automáticas no banco de dados."""
        if resultado.get("status") == "erro":
            # Sem conexão ou falha na API: não assumir que o programa está atualizado.
            print("NutriLab: não foi possível consultar atualizações:", resultado.get("erro"))
            return
        if resultado.get("status") != "atualizacao":
            return
        url = resultado.get("url", "")
        tem_pacote = bool(resultado.get("pacote_windows"))
        texto = ("Versão instalada: {local}\nÚltima versão no GitHub: {remota}\n\n".format(**resultado))
        texto += ("Há um pacote Windows publicado. A atualização deverá preservar o banco e os arquivos locais."
                  if tem_pacote else
                  "A release existe, mas ainda não há pacote Windows publicado. Nenhum arquivo será alterado.")
        if messagebox.askyesno("Atualização do NutriLab disponível", texto + "\n\nAbrir a página da atualização?"):
            import webbrowser
            if url:
                webbrowser.open(url)

    def tela_mapa(self):
        self.mapa.mostrar_mapa()

    def tela_mapa_graficos(self):
        self.mapa.mostrar_graficos()

    def tela_suplementos(self):
        self.mapa.mostrar_suplementos()

    def tela_mobile(self):
        from mobile_ui import MobileUI
        MobileUI(self, caminho_do_banco(), get_base_path()).mostrar()

    def tela_almoxarifado(self):
        """Abre o controle de itens, estoque, movimentações e programação de custos."""
        from almox_ui import AlmoxUI
        AlmoxUI(self, caminho_do_banco(), get_base_path()).mostrar()

    def tela_gestao_alimentar_fichas(self):
        """Abre fichas técnicas e a análise observacional de retiradas da cozinha."""
        from gestao_alimentar_ui import GestaoAlimentarUI
        GestaoAlimentarUI(self, caminho_do_banco(), get_base_path()).mostrar()

    def tela_configuracoes(self):
        from configuracoes_ui import ConfiguracoesUI
        ConfiguracoesUI(self).mostrar()

    def tela_nrs(self):
        from nrs_ui import NRSUI
        NRSUI(self, self.mapa.db).mostrar()

    def tela_avaliacao(self):
        from avaliacao_ui import AvaliacaoUI
        AvaliacaoUI(self, self.mapa.db).mostrar()

    def alternar_menu(self):
        """Fixa ou solta a barra lateral v4."""
        return self.menu_lateral.alternar()

    def _guardar_largura_painel_edicao(self, _evento=None):
        """Guarda a largura escolhida ao arrastar a divisória do painel."""
        try:
            if self._painel_edicao_frame is not None:
                largura = int(self._layout_principal.sashpos(0))
                if largura >= 320:
                    self._largura_painel_edicao = min(760, largura)
        except (tk.TclError, ValueError, AttributeError):
            pass

    def _descartar_paineis_edicao(self):
        """Descarta o editor atual e qualquer diálogo pai suspenso, sem manter histórico visível."""
        shells = []
        if self._painel_edicao_shell is not None:
            shells.append(self._painel_edicao_shell)
        shells.extend(item[0] for item in self._painel_edicao_pilha)
        self._painel_edicao_shell = None
        self._painel_edicao_frame = None
        self._painel_edicao_pilha.clear()
        for shell in shells:
            try:
                shell.destroy()
            except tk.TclError:
                pass
        try:
            self._layout_principal.forget(self._painel_edicao_host)
        except tk.TclError:
            pass

    def _mostrar_falha_tela(self, titulo, erro):
        detalhe = f"{type(erro).__name__}: {erro}"
        try:
            import traceback
            pasta_logs = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)), "logs")
            os.makedirs(pasta_logs, exist_ok=True)
            with open(os.path.join(pasta_logs, "erros_interface.log"), "a", encoding="utf-8") as registro:
                registro.write(f"\\n[{datetime.now().isoformat(timespec='seconds')}] Falha ao abrir {titulo}\\n")
                registro.write(traceback.format_exc())
                registro.write("\\n")
        except OSError:
            pass
        messagebox.showerror(
            "Não foi possível abrir a tela",
            f'A tela "{titulo}" não pôde ser aberta.\\n\\n{detalhe}\\n\\n'
            "O erro técnico foi registrado em logs/erros_interface.log, quando possível."
        )

    def abrir_pagina_principal(self, titulo, comando):
        """Troca a tela central sem criar histórico lateral."""
        self._descartar_paineis_edicao()
        frame = self._pilha_abas_laterais.abrir(titulo)
        self.area_principal = frame
        try:
            comando()
        except Exception as erro:
            self.area_principal = self._pilha_abas_laterais.fechar(frame)
            self._mostrar_falha_tela(titulo, erro)
            return None
        return frame

    def abrir_painel_lateral(self, titulo, comando, _preservar_pai=False):
        """Abre um único editor; novas edições substituem o anterior, sem barra de histórico."""
        if not _preservar_pai:
            self._descartar_paineis_edicao()

        shell = ctk.CTkFrame(self._painel_edicao_host, fg_color=tema.FUNDO, corner_radius=0)
        shell.pack(fill="both", expand=True)
        topo = ctk.CTkFrame(shell, fg_color="transparent", height=42)
        topo.pack(fill="x", padx=12, pady=(8, 4))
        topo.pack_propagate(False)
        ctk.CTkLabel(topo, text=str(titulo), anchor="w",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=tema.TEXTO).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(topo, text="×", width=30, height=28, fg_color="transparent",
                      hover_color=tema.VERDE_CLARO, text_color=tema.TEXTO,
                      command=lambda: self.fechar_painel_lateral(self._painel_edicao_frame)
                      ).pack(side="right")
        frame = ctk.CTkFrame(shell, fg_color="transparent", corner_radius=0)
        frame.pack(fill="both", expand=True)
        self._painel_edicao_shell = shell
        self._painel_edicao_frame = frame
        try:
            self._layout_principal.insert(0, self._painel_edicao_host, weight=0)
            self._layout_principal.pane(self._painel_edicao_host, minsize=320, weight=0)
            self.update_idletasks()
            self._layout_principal.sashpos(0, self._largura_painel_edicao)
        except tk.TclError:
            self._layout_principal.add(self._painel_edicao_host, weight=0)
        area_anterior = self.area_principal
        try:
            # Telas legadas que recebem o app constroem seus widgets em area_principal.
            # Durante a montagem, essa referência aponta para o painel; ao retornar,
            # a tela principal volta a ser a referência ativa sem perder seus widgets.
            self.area_principal = frame
            comando()
        except Exception as erro:
            self.area_principal = area_anterior
            self.fechar_painel_lateral(frame)
            self._mostrar_falha_tela(titulo, erro)
            return None
        finally:
            self.area_principal = area_anterior
        return frame

    def abrir_painel_modal(self, titulo, comando):
        """Abre um diálogo temporário e restaura o formulário pai ao fechá-lo."""
        if self._painel_edicao_shell is not None:
            self._painel_edicao_shell.pack_forget()
            self._painel_edicao_pilha.append(
                (self._painel_edicao_shell, self._painel_edicao_frame, self._largura_painel_edicao)
            )
            self._painel_edicao_shell = None
            self._painel_edicao_frame = None
            try:
                self._layout_principal.forget(self._painel_edicao_host)
            except tk.TclError:
                pass
        return self.abrir_painel_lateral(titulo, comando, _preservar_pai=True)

    def fechar_painel_lateral(self, frame):
        """Fecha o diálogo atual e, se houver, restaura o formulário pai suspenso."""
        if frame is not None and frame is not self._painel_edicao_frame:
            return self.area_principal
        shell = self._painel_edicao_shell
        self._painel_edicao_frame = None
        self._painel_edicao_shell = None
        if shell is not None:
            try:
                shell.destroy()
            except tk.TclError:
                pass
        try:
            self._layout_principal.forget(self._painel_edicao_host)
        except tk.TclError:
            pass
        if self._painel_edicao_pilha:
            anterior, frame_anterior, largura = self._painel_edicao_pilha.pop()
            self._painel_edicao_shell = anterior
            self._painel_edicao_frame = frame_anterior
            self._largura_painel_edicao = largura
            anterior.pack(fill="both", expand=True)
            try:
                self._layout_principal.insert(0, self._painel_edicao_host, weight=0)
                self._layout_principal.pane(self._painel_edicao_host, minsize=320, weight=0)
                self.update_idletasks()
                self._layout_principal.sashpos(0, largura)
            except tk.TclError:
                self._layout_principal.add(self._painel_edicao_host, weight=0)
        return self.area_principal

    def _fechar_ultima_aba_lateral(self, event=None):
        """ESC fecha o editor lateral atual sem trocar a tela principal."""
        if getattr(self, "_tela_inicial_ativa", False):
            return None
        try:
            foco = self.focus_get()
            if foco is not None and foco.winfo_toplevel() is not self:
                return None
        except (tk.TclError, AttributeError):
            pass
        if self._painel_edicao_frame is None:
            return None
        self.fechar_painel_lateral(self._painel_edicao_frame)
        return "break"

    def configurar_banco_dados(self):
        caminho = caminho_do_banco()
        interno = banco_interno_com_dados(caminho)
        if interno:
            messagebox.showwarning(
                "Dois bancos de dados encontrados",
                f"Este programa agora usa SOMENTE este banco:\n{caminho}\n\n"
                f"Mas existe outro banco COM PACIENTES em:\n{interno}\n\n"
                "Nada foi apagado nem copiado. Se você usava o programa antes desta atualização, seus dados podem estar "
                "nesse outro arquivo. NÃO apague nenhum dos dois: faça uma cópia de ambos e consulte "
                "docs/desenvolvimento/GUIA_DESENVOLVIMENTO_WINDOWS.md (seção 6) antes de registrar novos pacientes.")
        # Controle de versão do esquema (ADR-0001). Em banco NOVO a baseline cria o esquema legado numa transação; em banco
        # legado já existente apenas ADOTA a baseline (nenhuma tabela é alterada) depois de um backup verificado em backups/.
        try:
            db_migracoes.aplicar_migracoes(caminho, inicializador_legado=garantir_esquema_legado)
        except Exception as erro:
            messagebox.showwarning(
                "Banco de dados",
                "Não foi possível registrar a versão do banco de dados (nenhuma alteração foi feita nos seus dados).\n\n"
                f"Detalhe técnico: {erro}")
        conexao = sqlite3.connect(caminho)
        garantir_esquema_legado(conexao)
        conexao.commit()
        conexao.close()

    def limpar_area_principal(self):
        for widget in self.area_principal.winfo_children():
            widget.destroy()

    def tela_inicial(self):
        """Apresentação inicial em camadas; a navegação é exibida após a escolha da área."""
        self._descartar_paineis_edicao()
        self._pilha_abas_laterais.limpar()
        self.area_principal = self._pilha_abas_laterais.pagina_atual
        self._layout_principal.pack_forget()
        self.limpar_area_principal()
        self._tela_inicial_ativa = True
        self._timer_areas_iniciais = None
        self.menu_lateral.place_forget()
        self.area_principal_host.grid_configure(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.area_principal_host.configure(corner_radius=0)
        self.grid_columnconfigure(0, weight=1, minsize=0)
        self.grid_columnconfigure(1, weight=0, minsize=0)
        self._tela_boas_vindas = TelaBoasVindas(
            self.area_principal_host, self._entrar_na_area_inicial
        )
        self._tela_boas_vindas.frame.pack(fill="both", expand=True)
        self._binding_esc_inicial = self.bind(
            "<Escape>", self._confirmar_saida_inicial, add="+"
        )

    def _mostrar_areas_iniciais(self):
        if not getattr(self, "_tela_inicial_ativa", False) or self._areas_iniciais_visiveis:
            return
        self._areas_iniciais_visiveis = True
        if self._timer_areas_iniciais:
            try:
                self.after_cancel(self._timer_areas_iniciais)
            except Exception:
                pass
            self._timer_areas_iniciais = None
        self.label_instrucao_inicial.place_forget()
        painel = ctk.CTkFrame(
            self._tela_boas_vindas, fg_color=tema.FUNDO,
            border_color=tema.BORDA, border_width=1, corner_radius=18
        )
        painel.place(relx=0.5, rely=0.82, relwidth=0.78, anchor="center")
        ctk.CTkLabel(
            painel, text="Escolha por onde deseja começar",
            text_color=tema.VERDE_ESC, font=ctk.CTkFont(size=23, weight="bold")
        ).pack(pady=(14, 10))
        opcoes = (
            ("Gestão Clínica", "Pacientes, consultas, exames e avaliações", self.tela_pacientes),
            ("Nutrição", "Mapa nutricional, gráficos e suplementos", self.tela_mapa),
            ("Gestão Alimentar", "Almoxarifado, copa e fichas de consumo", self.tela_almoxarifado),
        )
        linha = ctk.CTkFrame(painel, fg_color="transparent")
        linha.pack(fill="x", padx=14, pady=(0, 14))
        for titulo, descricao, comando in opcoes:
            cartao = ctk.CTkFrame(linha, fg_color=tema.BRANCO, border_color=tema.BORDA,
                                  border_width=1, corner_radius=12)
            cartao.pack(side="left", fill="both", expand=True, padx=7)
            ctk.CTkLabel(cartao, text=titulo, text_color=tema.VERDE,
                         font=ctk.CTkFont(size=17, weight="bold")).pack(padx=12, pady=(14, 5))
            ctk.CTkLabel(cartao, text=descricao, text_color=tema.SUAVE,
                         font=ctk.CTkFont(size=12), wraplength=220).pack(padx=12, pady=(0, 12))
            ctk.CTkButton(
                cartao, text="Entrar", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
                command=lambda fn=comando: self._entrar_na_area_inicial(fn)
            ).pack(fill="x", padx=12, pady=(0, 14))

    def _entrar_na_area_inicial(self, destino):
        if not getattr(self, "_tela_inicial_ativa", False):
            return
        self._tela_inicial_ativa = False
        if getattr(self, "_binding_esc_inicial", None):
            self.unbind("<Escape>", self._binding_esc_inicial)
            self._binding_esc_inicial = None
        if getattr(self, "_tela_boas_vindas", None):
            self._tela_boas_vindas.parar()
            self._tela_boas_vindas.frame.destroy()
            self._tela_boas_vindas = None

        self.menu_lateral.place(x=0, y=0, relheight=1.0)
        self.area_principal_host.grid_configure(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.area_principal_host.configure(corner_radius=10)
        self.grid_columnconfigure(
            0, weight=0,
            minsize=self.menu_lateral.EXPANDIDA if self.menu_lateral.fixa else self.menu_lateral.RECOLHIDA
        )
        self.grid_columnconfigure(1, weight=1, minsize=0)
        self._layout_principal.pack(fill="both", expand=True)

        destinos = {
            "clinica": ("Pacientes", self.tela_pacientes),
            "nutricao": ("Mapa Nutricional", self.tela_mapa),
            "alimentar": ("Almoxarifado", self.tela_almoxarifado),
        }
        titulo, comando = destinos.get(destino, destinos["clinica"])
        self.abrir_pagina_principal(titulo, comando)

    def _confirmar_saida_inicial(self, event=None):
        if getattr(self, "_tela_inicial_ativa", False):
            if messagebox.askyesno("Sair do NutriLab", "Deseja realmente sair do NutriLab?"):
                self._ao_fechar()
            return "break"

    # --- MÓDULO DE PACIENTES ---
    def tela_pacientes(self):
        self.limpar_area_principal()

        ctk.CTkLabel(self.area_principal, text="Gestão de Pacientes", font=ctk.CTkFont(size=24, weight="bold"), text_color=tema.TEXTO).pack(pady=(20, 10))
        self.tabview = _criar_tabview_compat(self.area_principal, fonte_abas=ctk.CTkFont(size=15, weight="bold"),
                                      fg_color=tema.FUNDO,
                                      segmented_button_selected_color=tema.VERDE, segmented_button_selected_hover_color=tema.TEXTO,
                                      segmented_button_unselected_color=tema.VERDE, segmented_button_unselected_hover_color=tema.VERDE_HOVER,
                                      text_color=tema.BRANCO, text_color_disabled=tema.BORDA)
        self.tabview.pack(padx=20, pady=10, fill="both", expand=True)
        aba_cadastro = self.tabview.add("Novo Cadastro")
        aba_lista = self.tabview.add("Pacientes Cadastrados")

        self.entry_nome = ctk.CTkEntry(aba_cadastro, placeholder_text="Nome Completo", width=300, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_nome.pack(pady=10)
        self.entry_nasc = tema.CampoData(aba_cadastro, placeholder_text="Data de Nascimento (DD/MM/AAAA)", width=300,
                                         font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.VERDE_ESC,
                                         placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_nasc.pack(pady=10)
        self.combo_sexo = ctk.CTkComboBox(aba_cadastro, values=["Feminino", "Masculino"], width=300, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, button_color=tema.VERDE, button_hover_color=tema.VERDE_HOVER, dropdown_fg_color=tema.BRANCO, dropdown_hover_color=tema.VERDE_CLARO, dropdown_text_color=tema.TEXTO)
        self.combo_sexo.set("Feminino")
        self.combo_sexo.pack(pady=10)
        botoes_cadastro = ctk.CTkFrame(aba_cadastro, fg_color="transparent")
        botoes_cadastro.pack(pady=18)
        ctk.CTkButton(
            botoes_cadastro, text="Salvar Cadastro", command=self.salvar_paciente,
            fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO,
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            botoes_cadastro, text="Salvar e iniciar consulta",
            command=lambda: self.salvar_paciente(iniciar_consulta=True),
            fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO,
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(side="left", padx=5)
        self.lbl_mensagem = ctk.CTkLabel(aba_cadastro, text="", text_color=tema.VERDE, font=ctk.CTkFont(size=15))
        self.lbl_mensagem.pack()

        tema.aplicar_tema_ttk(self)

        barra_lista = ctk.CTkFrame(aba_lista, fg_color="transparent")
        barra_lista.pack(fill="x", padx=10, pady=(8, 2))
        self.btn_consulta_paciente = ctk.CTkButton(
            barra_lista, text="Nova consulta do paciente selecionado",
            command=self.iniciar_consulta_paciente, state="disabled",
            fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.btn_consulta_paciente.pack(side="left")
        self.lbl_paciente_selecionado = ctk.CTkLabel(
            barra_lista, text="Selecione um paciente para iniciar uma consulta.",
            text_color=tema.SUAVE, font=ctk.CTkFont(size=12)
        )
        self.lbl_paciente_selecionado.pack(side="left", padx=12)

        tree_frame = ctk.CTkFrame(aba_lista, fg_color=tema.FUNDO)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(tree_frame, columns=("ID", "Nome", "Nascimento", "Sexo"), show="headings", style="Treeview")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Nome", text="Nome")
        self.tree.heading("Nascimento", text="Nascimento")
        self.tree.heading("Sexo", text="Sexo")
        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Nome", width=300)
        self.tree.column("Nascimento", width=120, anchor="center")
        self.tree.column("Sexo", width=100, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.abrir_perfil_paciente)
        self.tree.bind("<<TreeviewSelect>>", self._atualizar_acao_consulta_paciente)
        self.carregar_tabela_pacientes()

        self.fab_paciente = ctk.CTkButton(
            self.area_principal, text="+ Adicionar paciente",
            command=self._abrir_cadastro_paciente, width=190, height=44,
            corner_radius=22, fg_color=tema.LARANJA, hover_color=tema.LARANJA_TEXTO,
            text_color=tema.BRANCO, font=ctk.CTkFont(size=14, weight="bold")
        )
        self.fab_paciente.place(relx=0.98, rely=0.98, anchor="se")

        # Botão de exclusão debajo de la tabla (acción destructiva em vermelho)
        ctk.CTkButton(
            aba_lista,
            text="🗑️ Excluir Paciente",
            fg_color=tema.ERRO,
            hover_color=tema.ERRO_HOVER,
            text_color=tema.BRANCO,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.eliminar_paciente,
        ).pack(fill="x", padx=10, pady=10)

    def _abrir_cadastro_paciente(self):
        """Abre a aba de cadastro pelo botão flutuante."""
        self.tabview.set("Novo Cadastro")
        self.entry_nome.focus_set()

    def _atualizar_acao_consulta_paciente(self, _evento=None):
        selecionados = self.tree.selection()
        habilitado = bool(selecionados)
        self.btn_consulta_paciente.configure(state="normal" if habilitado else "disabled")
        if habilitado:
            valores = self.tree.item(selecionados[0], "values")
            self.lbl_paciente_selecionado.configure(text=f"Paciente: {valores[1]}")
        else:
            self.lbl_paciente_selecionado.configure(text="Selecione um paciente para iniciar uma consulta.")

    def iniciar_consulta_paciente(self):
        """Inicia consulta somente a partir de um paciente explicitamente selecionado."""
        selecionados = self.tree.selection()
        if not selecionados:
            messagebox.showinfo("Nova consulta", "Selecione um paciente na lista.")
            return
        valores = self.tree.item(selecionados[0], "values")
        self.paciente_atual_id, self.paciente_atual_nome, self.paciente_atual_nasc, self.paciente_atual_sexo = valores
        self.abrir_painel_lateral("Nova consulta", self.tela_consultas)

    def salvar_paciente(self, iniciar_consulta=False):
        nome = self.entry_nome.get()
        nasc = self.entry_nasc.get()
        sexo = self.combo_sexo.get()
        if nome.strip() == "":
            self.lbl_mensagem.configure(text="Erro: O nome é obrigatório.", text_color=tema.ERRO)
            return
        if nasc.strip() and not tema.data_valida(nasc):
            self.lbl_mensagem.configure(text="Erro: informe uma data de nascimento válida (DD/MM/AAAA).", text_color=tema.ERRO)
            return
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute('INSERT INTO Pacientes (nome, data_nascimento, sexo) VALUES (?, ?, ?)', (nome, nasc, sexo))
        id_novo = cursor.lastrowid
        conexao.commit()
        conexao.close()
        self.entry_nome.delete(0, 'end')
        self.entry_nasc.delete(0, 'end')
        self.carregar_tabela_pacientes()
        self.tabview.set("Pacientes Cadastrados")
        if iniciar_consulta:
            self.paciente_atual_id = id_novo
            self.paciente_atual_nome = nome
            self.paciente_atual_nasc = nasc
            self.paciente_atual_sexo = sexo
            self.abrir_painel_lateral("Nova consulta", self.tela_consultas)

    def carregar_tabela_pacientes(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute("SELECT id_paciente, nome, data_nascimento, sexo FROM Pacientes")
        linhas = cursor.fetchall()
        conexao.close()
        for linha in linhas:
            self.tree.insert("", "end", values=linha)

    def eliminar_paciente(self):
        """Elimina definitivamente el paciente seleccionado en la tabla."""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Excluir Paciente", "Selecione um paciente na tabela para excluir.")
            return

        valores = self.tree.item(seleccion[0])['values']
        id_paciente = valores[0]
        nome_paciente = valores[1]

        confirmar = messagebox.askyesno(
            "Confirmar Exclusão",
            f"⚠️ Esta ação eliminará DEFINITIVAMENTE o paciente:\n\n"
            f"{nome_paciente} (ID: {id_paciente})\n\n"
            f"Deseja continuar?",
        )
        if not confirmar:
            return

        # Antes de excluir, verifica referências clínicas e arquivos armazenados.
        pasta_paciente = os.path.join(
            get_writable_path("arquivos_pacientes"), f"paciente_{id_paciente}"
        )
        conexao = sqlite3.connect(caminho_do_banco())
        try:
            vinculados = pacientes_integridade.registros_vinculados(
                conexao, int(id_paciente), pasta_paciente
            )
            if vinculados:
                resumo = "\n".join(f"• {nome}: {quantidade}" for nome, quantidade in vinculados.items())
                messagebox.showwarning(
                    "Exclusão bloqueada",
                    "Este paciente possui histórico clínico ou arquivos vinculados. "
                    "Para proteger os dados, a exclusão definitiva foi bloqueada.\n\n"
                    f"Registros encontrados:\n{resumo}\n\n"
                    "Não apague manualmente esses dados. Considere manter o cadastro."
                )
                return
            cursor = conexao.cursor()
            cursor.execute("DELETE FROM Pacientes WHERE id_paciente = ?", (id_paciente,))
            conexao.commit()
        finally:
            conexao.close()

        self.carregar_tabela_pacientes()

    # --- PERFIL DO PACIENTE ---
    def abrir_perfil_paciente(self, event=None, _painel_aberto=False, _valores=None):
        if not _painel_aberto:
            selecao = self.tree.selection()
            if not selecao:
                return
            # Capture os dados antes de trocar a página: a tabela de origem será destruída.
            valores = self.tree.item(selecao[0])['values']
            self.abrir_pagina_principal(
                "Perfil do paciente",
                lambda: self.abrir_perfil_paciente(event, _painel_aberto=True, _valores=valores)
            )
            return
        valores = _valores
        if valores is None:
            selecao = self.tree.selection()
            if not selecao:
                return
            valores = self.tree.item(selecao[0])['values']
        self.paciente_atual_id, self.paciente_atual_nome, nasc, sexo = valores
        self.paciente_atual_nasc = nasc
        self.paciente_atual_sexo = sexo
        
        self.limpar_area_principal()
        ctk.CTkButton(self.area_principal, text="← Voltar", width=80, fg_color=tema.VERDE_CLARO, hover_color=tema.BORDA, text_color=tema.TEXTO, border_width=1, border_color=tema.VERDE, font=ctk.CTkFont(size=15), command=lambda: self.abrir_pagina_principal("Pacientes", self.tela_pacientes)).pack(anchor="nw", pady=10, padx=10)
        ctk.CTkLabel(self.area_principal, text=f"Perfil Clínico: {self.paciente_atual_nome}", font=ctk.CTkFont(size=26, weight="bold"), text_color=tema.TEXTO).pack(pady=(0, 5))
        ctk.CTkLabel(self.area_principal, text=f"ID: {self.paciente_atual_id}  |  Nascimento: {nasc}  |  Sexo: {sexo}", font=ctk.CTkFont(size=17), text_color=tema.TEXTO).pack(pady=5)

        tabview_perfil = _criar_tabview_compat(self.area_principal, fonte_abas=ctk.CTkFont(size=15, weight="bold"),
                                        fg_color=tema.FUNDO,
                                        segmented_button_selected_color=tema.VERDE, segmented_button_selected_hover_color=tema.TEXTO,
                                        segmented_button_unselected_color=tema.VERDE, segmented_button_unselected_hover_color=tema.VERDE_HOVER,
                                        text_color=tema.BRANCO, text_color_disabled=tema.BORDA)
        tabview_perfil.pack(padx=20, pady=10, fill="both", expand=True)
        
        aba_hist = tabview_perfil.add("Histórico de Consultas")
        aba_exm = tabview_perfil.add("Exames e Arquivos")
        
        ctk.CTkButton(aba_hist, text="Iniciar Nova Consulta", command=lambda: self.abrir_painel_lateral("Nova consulta", self.tela_consultas), fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        scroll_hist = ctk.CTkScrollableFrame(aba_hist, fg_color="transparent")
        scroll_hist.pack(fill="both", expand=True, padx=10, pady=10)

        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute('''
            SELECT id_consulta, data_consulta, anamnese, peso, altura, gordura, conduta, tmb, vet, naf, metodo_tmb, analise_exames
            FROM Consultas
            WHERE id_paciente = ?
            ORDER BY id_consulta DESC
        ''', (self.paciente_atual_id,))
        consultas = cursor.fetchall()

        if not consultas:
            ctk.CTkLabel(scroll_hist, text="Nenhuma consulta registada ainda.", text_color=tema.SUAVE, font=ctk.CTkFont(size=15)).pack(pady=20)
        else:
            for consulta in consultas:
                id_cons, data_cons, anamnese, peso, altura, gordura, conduta, tmb, vet, naf, metodo, analise_exames = consulta

                card = ctk.CTkFrame(scroll_hist, corner_radius=8, fg_color=tema.BRANCO, border_width=1, border_color=tema.VERDE_CLARO)
                card.pack(fill="x", pady=10, ipady=10)

                ctk.CTkLabel(card, text=f"📅 Data: {data_cons}", font=ctk.CTkFont(weight="bold", size=19), text_color=tema.TEXTO).pack(anchor="w", padx=15, pady=(10, 5))

                if anamnese:
                    ctk.CTkLabel(card, text=f"Anamnese: {anamnese}", justify="left", wraplength=700, font=ctk.CTkFont(size=15)).pack(anchor="w", padx=15, pady=2)

                antro_texto = []
                if peso: antro_texto.append(f"Peso: {peso}kg")
                if altura: antro_texto.append(f"Altura: {altura}m")
                if gordura: antro_texto.append(f"Gordura: {gordura}%")
                if tmb and vet:
                    antro_texto.append(f"TMB: {float(tmb):.2f} kcal ({metodo})")
                    antro_texto.append(f"VET: {float(vet):.2f} kcal (NAF: {naf})")

                if antro_texto:
                    ctk.CTkLabel(card, text=f"Antropometria e Gasto:\n" + "\n".join(antro_texto), justify="left", font=ctk.CTkFont(size=15)).pack(anchor="w", padx=15, pady=2)

                if conduta:
                    ctk.CTkLabel(card, text=f"Conduta: {conduta}", justify="left", wraplength=700, font=ctk.CTkFont(size=15)).pack(anchor="w", padx=15, pady=2)

                if analise_exames:
                    ctk.CTkLabel(card, text=f"Análise e Valores de Referência: {analise_exames}", justify="left", wraplength=700, font=ctk.CTkFont(size=15)).pack(anchor="w", padx=15, pady=2)

                cursor.execute('''
                    SELECT E.nome_amigavel
                    FROM Exames_Solicitados S
                    JOIN Exames_Catalogo E ON S.id_exame = E.id_exame
                    WHERE S.id_consulta = ?
                ''', (id_cons,))
                exames = cursor.fetchall()

                exames_str = ""
                if exames:
                    ctk.CTkLabel(card, text="Exames Solicitados:", font=ctk.CTkFont(weight="bold", size=16), text_color=tema.TEXTO).pack(anchor="w", padx=15, pady=(5,0))
                    exames_str = ", ".join([ex[0] for ex in exames])
                    ctk.CTkLabel(card, text=exames_str, justify="left", wraplength=700, text_color=tema.VERDE, font=ctk.CTkFont(size=15)).pack(anchor="w", padx=15, pady=(0, 10))
                
                ctk.CTkButton(card, text="Gerar PDF", width=120, fg_color=tema.VERDE, hover_color=tema.VERDE, text_color=tema.BRANCO, font=ctk.CTkFont(size=15, weight="bold"), 
                              command=lambda c=consulta, e=exames_str: self.gerar_pdf_evolucao(c, e)).pack(anchor="e", padx=15, pady=10)

        ctk.CTkButton(aba_exm, text="Anexar Documento / Imagem", command=self.anexar_arquivo_paciente, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=10)
        self.scroll_arquivos = ctk.CTkScrollableFrame(aba_exm, fg_color="transparent")
        self.scroll_arquivos.pack(fill="both", expand=True, padx=10, pady=10)
        self.carregar_lista_arquivos()
        conexao.close()

    def gerar_pdf_evolucao(self, consulta_dados, exames_str):
        try:
            # ------------------------------------------------------------------
            # 1) Desempacotamento seguro da tupla da consulta.
            #    O SELECT traz 12 colunas (incluindo analise_exames), então
            #    precisamos receber todas — e tolerar tuplas maiores/menores
            #    caso o schema evolua.
            # ------------------------------------------------------------------
            esperado = (
                "id_consulta", "data_consulta", "anamnese", "peso", "altura",
                "gordura", "conduta", "tmb", "vet", "naf", "metodo_tmb",
                "analise_exames",
            )
            if not consulta_dados or len(consulta_dados) < len(esperado):
                raise ValueError(
                    f"Tupla de consulta inválida (esperado {len(esperado)} "
                    f"campos, recebi {len(consulta_dados) if consulta_dados else 0})."
                )
            id_cons = consulta_dados[0]
            data_cons = consulta_dados[1] or ""
            anamnese = consulta_dados[2] or ""
            peso = consulta_dados[3]
            altura = consulta_dados[4]
            gordura = consulta_dados[5]
            conduta = consulta_dados[6] or ""
            tmb = consulta_dados[7]
            vet = consulta_dados[8]
            naf = consulta_dados[9]
            metodo = consulta_dados[10] or ""
            analise_exames = consulta_dados[11] or ""

            # ------------------------------------------------------------------
            # 2) Conexão única para ler analise_exames (fallback), exames
            #    solicitados (fonte da verdade) e resultados.
            # ------------------------------------------------------------------
            conexao_pdf = sqlite3.connect(caminho_do_banco())
            cursor_pdf = conexao_pdf.cursor()

            if not analise_exames:
                cursor_pdf.execute(
                    "SELECT analise_exames FROM Consultas WHERE id_consulta = ?",
                    (id_cons,),
                )
                resultado_analise = cursor_pdf.fetchone()
                analise_exames = (resultado_analise[0] or "") if resultado_analise else ""

            # Exames solicitados: fonte da verdade é o banco (id_consulta),
            # não apenas o parâmetro exames_str recebido da interface.
            # Usa LEFT JOIN para não perder itens cujo catálogo foi removido.
            cursor_pdf.execute('''
                SELECT COALESCE(E.nome_amigavel, S.id_exame)
                FROM Exames_Solicitados S
                LEFT JOIN Exames_Catalogo E ON S.id_exame = E.id_exame
                WHERE S.id_consulta = ?
                ORDER BY COALESCE(E.nome_amigavel, S.id_exame)
            ''', (id_cons,))
            exames_banco = [str(r[0]).strip() for r in (cursor_pdf.fetchall() or []) if r and r[0]]
            if exames_banco:
                exames_str = ", ".join(exames_banco)
            elif exames_str:
                exames_str = str(exames_str).strip()

            # Resultados efetivamente lançados para esta consulta
            cursor_pdf.execute('''
                SELECT E.nome_amigavel, R.valor, R.status
                FROM Resultados_Exames R
                JOIN Exames_Catalogo E ON R.id_exame = E.id_exame
                WHERE R.id_consulta = ?
                ORDER BY E.nome_amigavel
            ''', (id_cons,))
            resultados_rows = cursor_pdf.fetchall() or []

            # Data de nascimento e sexo do paciente (para idade e IMC no relatório)
            data_nasc_paciente = ""
            sexo_paciente = ""
            cursor_pdf.execute('''
                SELECT P.data_nascimento, P.sexo
                FROM Consultas C
                JOIN Pacientes P ON C.id_paciente = P.id_paciente
                WHERE C.id_consulta = ?
            ''', (id_cons,))
            linha_paciente_pdf = cursor_pdf.fetchone()
            if linha_paciente_pdf:
                data_nasc_paciente = linha_paciente_pdf[0] or ""
                sexo_paciente = linha_paciente_pdf[1] or ""
            conexao_pdf.close()

            # ------------------------------------------------------------------
            # 3) Helpers de texto seguros (sempre string, nunca None).
            # ------------------------------------------------------------------
            def formatar_texto(texto):
                if texto is None:
                    return ""
                return str(texto).encode('latin-1', 'replace').decode('latin-1')

            def formatar_valor(v):
                if v is None or v == "":
                    return "—"
                try:
                    return f"{float(v):.2f}".rstrip('0').rstrip('.')
                except (TypeError, ValueError):
                    return str(v)

            def rotulo_status_pdf(status):
                """Reduz rótulos técnicos (ex.: '170–285 µmol/L (faixa normal)')
                à classificação simples exibida na coluna Status do PDF.

                Quando o texto entre parênteses traz a classificação
                (ex.: 'faixa normal'), devolve 'Normal'/'Baixo'/'Alto';
                rótulos que já trazem a classificação própria
                (ex.: 'Resistência grave (>4,0)') seguem impressos intactos.
                """
                texto = (status or "").strip()
                if not texto:
                    return ""
                dentro = re.search(r"\(([^)]+)\)", texto)
                if dentro:
                    conteudo = dentro.group(1).lower()
                    if re.search(r"\b(normal|adequado)\b", conteudo):
                        return "Normal"
                    if re.search(r"\bbaixo\b", conteudo):
                        return "Baixo"
                    if re.search(r"\balto\b", conteudo):
                        return "Alto"
                return texto

            # ------------------------------------------------------------------
            # 4) Construção do PDF
            # ------------------------------------------------------------------
            pdf = FPDF()
            pdf.add_page()

            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, formatar_texto("Relatório de Consulta Nutricional"), ln=True, align='C')
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, formatar_texto(f"Paciente: {self.paciente_atual_nome or ''}"), ln=True)
            pdf.cell(0, 8, formatar_texto(f"Data de Atendimento: {data_cons}"), ln=True)
            pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
            pdf.ln(10)

            if anamnese:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, formatar_texto("Anamnese e Queixas:"), ln=True)
                pdf.set_font("Arial", '', 11)
                pdf.multi_cell(0, 6, formatar_texto(anamnese))
                pdf.ln(5)

            antro_texto = []
            if peso not in (None, ""):
                antro_texto.append(f"Peso: {peso}kg")
            if altura not in (None, ""):
                antro_texto.append(f"Altura: {altura}m")
            if gordura not in (None, ""):
                antro_texto.append(f"Gordura: {gordura}%")
            if tmb not in (None, "") and vet not in (None, ""):
                try:
                    tmb_f = float(tmb)
                    vet_f = float(vet)
                    antro_texto.append(
                        f"TMB: {tmb_f:.2f} kcal ({metodo}) | "
                        f"VET: {vet_f:.2f} kcal (NAF: {naf or '-'})"
                    )
                except (TypeError, ValueError):
                    antro_texto.append(
                        f"TMB: {tmb} kcal ({metodo}) | "
                        f"VET: {vet} kcal (NAF: {naf or '-'})"
                    )

            # IMC calculado com classificação oficial por faixa etária
            imc_pdf = None
            try:
                peso_f = float(str(peso).replace(',', '.'))
                altura_f = float(str(altura).replace(',', '.'))
                if peso_f > 0 and altura_f > 0:
                    imc_pdf = peso_f / (altura_f ** 2)
            except (TypeError, ValueError, ZeroDivisionError):
                imc_pdf = None
            if imc_pdf is not None:
                idade_pdf = self._calcular_idade_por_nascimento(data_nasc_paciente)
                classificacao_imc = self._classificar_imc(imc_pdf, idade_pdf)
                idade_txt = f"{idade_pdf} anos" if idade_pdf is not None else "idade não informada"
                antro_texto.append(
                    f"IMC: {imc_pdf:.1f} kg/m² - {classificacao_imc} (idade: {idade_txt})"
                )

            if antro_texto:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, formatar_texto("Dados Antropométricos e Gasto Energético:"), ln=True)
                pdf.set_font("Arial", '', 11)
                for linha in antro_texto:
                    pdf.cell(0, 6, formatar_texto(linha), ln=True)
                pdf.ln(5)

            if conduta:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, formatar_texto("Conduta Dietoterápica / Prescrição:"), ln=True)
                pdf.set_font("Arial", '', 11)
                pdf.multi_cell(0, 6, formatar_texto(conduta))
                pdf.ln(5)

            if exames_str:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, formatar_texto("Exames e Marcadores Solicitados:"), ln=True)
                pdf.set_font("Arial", '', 11)
                pdf.multi_cell(0, 6, formatar_texto(exames_str))
                pdf.ln(5)

            # Tabela de resultados lançados (se houver)
            if resultados_rows:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, formatar_texto("Resultados Laboratoriais Lançados:"), ln=True)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(90, 6, formatar_texto("Exame"), border=1)
                pdf.cell(45, 6, formatar_texto("Valor"), border=1)
                pdf.cell(45, 6, formatar_texto("Status"), border=1, ln=True)
                pdf.set_font("Arial", '', 10)
                for nome_exame, valor, status in resultados_rows:
                    pdf.cell(90, 6, formatar_texto(nome_exame or ""), border=1)
                    pdf.cell(45, 6, formatar_texto(formatar_valor(valor)), border=1)
                    pdf.cell(45, 6, formatar_texto(rotulo_status_pdf(status)), border=1, ln=True)
                pdf.ln(5)

            # Índices metabólicos calculados (pares clínicos presentes na consulta)
            valores_resultados = {}
            for nome_exame, valor, _status in resultados_rows:
                try:
                    valores_resultados[str(nome_exame or '').upper()] = float(str(valor).replace(',', '.'))
                except (TypeError, ValueError):
                    continue
            indices_pdf = self._calcular_indices_para_pdf(valores_resultados)
            if indices_pdf:
                if pdf.get_y() > 240:
                    pdf.add_page()
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, formatar_texto("Índices Metabólicos Calculados:"), ln=True)
                pdf.set_font("Arial", '', 11)
                for linha_indice in indices_pdf:
                    pdf.multi_cell(0, 6, formatar_texto(linha_indice))
                pdf.ln(5)

            # ------------------------------------------------------------------
            # 5) Persistência
            # ------------------------------------------------------------------
            base_dir = get_writable_path("arquivos_pacientes")
            os.makedirs(base_dir, exist_ok=True)
            pasta_paciente = os.path.join(
                base_dir, f"paciente_{self.paciente_atual_id}"
            )
            os.makedirs(pasta_paciente, exist_ok=True)

            data_slug = (data_cons or "sem_data").replace('/', '-').replace(':', 'h').replace(' ', '_')
            nome_arquivo = f"Conduta_{data_slug}.pdf"
            caminho_pdf = os.path.join(pasta_paciente, nome_arquivo)

            pdf.output(caminho_pdf)
            self.abrir_arquivo_externo(caminho_pdf)

        except Exception as exc:
            import traceback
            print(f"[ERRO] Falha ao gerar PDF da consulta {consulta_dados if consulta_dados else '?'}: {exc}")
            traceback.print_exc()
            try:
                messagebox.showerror(
                    "Erro ao gerar PDF",
                    f"Não foi possível gerar o PDF.\n\n{exc}\n\n"
                    f"Detalhes foram impressos no terminal."
                )
            except Exception:
                pass

    def anexar_arquivo_paciente(self):
        caminho_origem = filedialog.askopenfilename(title="Selecione o Exame", filetypes=[("Documentos e Imagens", "*.pdf *.png *.jpg *.jpeg *.doc *.docx")])
        if not caminho_origem: return
        base_dir = get_writable_path("arquivos_pacientes")
        pasta_paciente = os.path.join(base_dir, f"paciente_{self.paciente_atual_id}")
        os.makedirs(pasta_paciente, exist_ok=True)
        nome_arquivo = os.path.basename(caminho_origem)
        caminho_destino = os.path.join(pasta_paciente, nome_arquivo)
        try:
            shutil.copy2(caminho_origem, caminho_destino)
            conexao = sqlite3.connect(caminho_do_banco())
            cursor = conexao.cursor()
            cursor.execute('INSERT INTO Arquivos_Paciente (id_paciente, nome_arquivo, caminho_arquivo, data_upload) VALUES (?, ?, ?, ?)', 
                           (self.paciente_atual_id, nome_arquivo, caminho_destino, datetime.now().strftime("%d/%m/%Y %H:%M")))
            conexao.commit()
            conexao.close()
            self.carregar_lista_arquivos()
        except Exception as e:
            print(f"Erro: {e}")

    def carregar_lista_arquivos(self):
        for widget in self.scroll_arquivos.winfo_children(): widget.destroy()
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute('SELECT nome_arquivo, caminho_arquivo, data_upload FROM Arquivos_Paciente WHERE id_paciente = ? ORDER BY id_arquivo DESC', (self.paciente_atual_id,))
        arquivos = cursor.fetchall()
        conexao.close()
        for nome, caminho, data in arquivos:
            card = ctk.CTkFrame(self.scroll_arquivos, corner_radius=8, fg_color=tema.BRANCO, border_width=1, border_color=tema.VERDE_CLARO)
            card.pack(fill="x", pady=5, ipady=5)
            ctk.CTkLabel(card, text=f"📄 {nome}", font=ctk.CTkFont(size=15)).pack(side="left", padx=(15, 5))
            ctk.CTkButton(card, text="Abrir", width=60, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=14), command=lambda c=caminho: self.abrir_arquivo_externo(c)).pack(side="right", padx=15)

    def abrir_arquivo_externo(self, caminho):
        try:
            if platform.system() == 'Windows': os.startfile(caminho)
            elif platform.system() == 'Darwin': os.system(f'open "{caminho}"')
            else: os.system(f'xdg-open "{caminho}"')
        except Exception as e:
            pass

    # --- MÓDULO DE CONSULTAS ---
    def tela_consultas(self):
        self.limpar_area_principal()
        
        if not self.paciente_atual_id:
            ctk.CTkLabel(self.area_principal, text="Nenhum paciente selecionado.", font=ctk.CTkFont(size=18)).pack(pady=50)
            return

        self.exames_selecionados_lista = []
        self.resultados_lancados = {}
        self.tmb_atual = ""
        self.vet_atual = ""
        self._resultado_pediatria_consulta = {}

        # Cache dos dados do paciente atual (para cálculo de idade e IMC)
        self.paciente_atual_nasc = ""
        self.paciente_atual_sexo = ""
        try:
            conexao_pac = sqlite3.connect(caminho_do_banco())
            cursor_pac = conexao_pac.cursor()
            cursor_pac.execute('SELECT data_nascimento, sexo FROM Pacientes WHERE id_paciente = ?', (self.paciente_atual_id,))
            linha_pac = cursor_pac.fetchone()
            if linha_pac:
                self.paciente_atual_nasc = linha_pac[0] or ""
                self.paciente_atual_sexo = linha_pac[1] or ""
            conexao_pac.close()
        except Exception as e:
            print(f"[AVISO] Não foi possível carregar nascimento do paciente: {e}")

        scroll_frame = ctk.CTkScrollableFrame(self.area_principal, corner_radius=10, fg_color=tema.FUNDO)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(scroll_frame, text=f"Atendimento: {self.paciente_atual_nome}", font=ctk.CTkFont(size=26, weight="bold"), text_color=tema.TEXTO).pack(pady=10)

        frame_anamnese = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        frame_anamnese.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(frame_anamnese, text="Anamnese e Evolução", font=ctk.CTkFont(weight="bold", size=17), text_color=tema.TEXTO).pack(side="left")
        if not getattr(sys, 'frozen', False):
            ctk.CTkButton(frame_anamnese, text="Importar Sintomas", width=120, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=14, weight="bold"), command=lambda: self.abrir_modal_padroes("anamnese")).pack(side="right")
        self.txt_anamnese = ctk.CTkTextbox(scroll_frame, width=600, height=100, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, border_width=1, border_color=tema.BORDA)
        self.txt_anamnese.pack(padx=20, pady=5)

        # Campos guiados, medicamentos/metas separados, recordatório opcional e biblioteca DOCX.
        self.painel_consulta_estruturada = PainelConsultaEstruturada(
            scroll_frame, caminho_do_banco(), os.path.dirname(caminho_do_banco()))
        self.painel_consulta_estruturada.pack(fill="x", padx=20, pady=8)
        frame_softsus = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        frame_softsus.pack(fill="x", padx=20, pady=4)
        ctk.CTkButton(frame_softsus, text="Montar e copiar texto para SoftSus",
                      fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO,
                      command=self.copiar_anamnese_softsus).pack(side="left")

        ctk.CTkLabel(scroll_frame, text="Antropometria e Composição Corporal", font=ctk.CTkFont(weight="bold", size=17), text_color=tema.TEXTO).pack(anchor="w", padx=20, pady=(15, 0))
        frame_antro = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        frame_antro.pack(fill="x", padx=20, pady=5)
        self.entry_peso = ctk.CTkEntry(frame_antro, placeholder_text="Peso (kg)", width=150, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_peso.grid(row=0, column=0, padx=(0, 10))
        self.entry_altura = ctk.CTkEntry(frame_antro, placeholder_text="Altura (m)", width=150, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_altura.grid(row=0, column=1, padx=10)
        self.entry_gordura = ctk.CTkEntry(frame_antro, placeholder_text="% Gordura", width=150, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_gordura.grid(row=0, column=2, padx=10)
        self.entry_peso.bind('<KeyRelease>', self._calcular_imc_dinamico)
        self.entry_altura.bind('<KeyRelease>', self._calcular_imc_dinamico)
        self.lbl_imc = ctk.CTkLabel(frame_antro, text="IMC: -- kg/m²", font=ctk.CTkFont(size=15, weight="bold"), text_color=tema.SUAVE)
        self.lbl_imc.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.lbl_oms_pediatria = ctk.CTkLabel(
            frame_antro, text="OMS pediatria: aguardando peso, altura e data de nascimento.",
            font=ctk.CTkFont(size=12), text_color=tema.SUAVE, wraplength=780, justify="left")
        self.lbl_oms_pediatria.grid(row=2, column=0, columnspan=3, sticky="w", pady=(3, 0))
        self.btn_curvas_oms = ctk.CTkButton(
            frame_antro, text="Ver curvas OMS", width=130, height=28,
            fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO,
            command=self._abrir_curvas_oms_consulta)
        self.btn_curvas_oms.grid(row=3, column=0, sticky="w", pady=(5, 0))

        frame_calculo = ctk.CTkFrame(scroll_frame, fg_color=tema.VERDE_CLARO, corner_radius=8, border_width=1, border_color=tema.BORDA)
        frame_calculo.pack(fill="x", padx=20, pady=10, ipady=5)
        linha_metodos = ctk.CTkFrame(frame_calculo, fg_color="transparent")
        linha_metodos.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(linha_metodos, text="Metodologia TMB:", font=ctk.CTkFont(size=15), text_color=tema.TEXTO).pack(side="left", padx=(0, 10))
        self.combo_metodo_tmb = ctk.CTkComboBox(linha_metodos, values=["Harris-Benedict (1919)", "Mifflin-St Jeor (1990)", "Cunningham (1980)"], width=200, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, button_color=tema.VERDE, button_hover_color=tema.VERDE_HOVER, dropdown_fg_color=tema.BRANCO, dropdown_hover_color=tema.VERDE_CLARO, dropdown_text_color=tema.TEXTO, command=self.atualizar_justificativa_metodologica)
        self.combo_metodo_tmb.set("Mifflin-St Jeor (1990)")
        self.combo_metodo_tmb.pack(side="left", padx=10)
        self.entry_naf = ctk.CTkEntry(linha_metodos, placeholder_text="Fator NAF (ex: 1.55)", width=130, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_naf.pack(side="left", padx=10)
        ctk.CTkButton(linha_metodos, text="Calcular", width=100, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=15, weight="bold"), command=self.calcular_metabolismo).pack(side="right")

        self.lbl_justificativa = ctk.CTkLabel(frame_calculo, text="Justificativa: Mifflin; St Jeor (1990) apresenta maior precisão para adultos saudáveis contemporâneos com sobrepeso ou obesidade, baseando-se no peso total.", text_color=tema.SUAVE, font=ctk.CTkFont(size=15), justify="left", wraplength=600)
        self.lbl_justificativa.pack(anchor="w", padx=10, pady=5)
        self.lbl_resultado_metabolismo = ctk.CTkLabel(frame_calculo, text="Insira os dados acima para calcular a Taxa Metabólica Basal e o VET.", font=ctk.CTkFont(size=17, weight="bold"), text_color=tema.TEXTO)
        self.lbl_resultado_metabolismo.pack(pady=10)

        # Equações DRI 2023 (EER) e fórmula de bolso são exibidas lado a lado, sem substituir a TMB existente.
        frame_dri = ctk.CTkFrame(frame_calculo, fg_color=tema.FUNDO, corner_radius=8)
        frame_dri.pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkLabel(frame_dri, text="Necessidade energética — DRI 2023 e fórmula de bolso",
                     text_color=tema.TEXTO, font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
        linha_dri = ctk.CTkFrame(frame_dri, fg_color="transparent")
        linha_dri.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(linha_dri, text="Atividade física:", text_color=tema.TEXTO).pack(side="left", padx=(0, 5))
        self.combo_dri_atividade = ctk.CTkComboBox(
            linha_dri, values=["Inativo", "Pouco ativo", "Ativo", "Muito ativo"], width=150,
            command=self.calcular_necessidades_dri)
        self.combo_dri_atividade.set("Inativo")
        self.combo_dri_atividade.pack(side="left", padx=5)
        ctk.CTkLabel(linha_dri, text="Fórmula de bolso:", text_color=tema.TEXTO).pack(side="left", padx=(12, 5))
        self.combo_fator_bolso = ctk.CTkComboBox(
            linha_dri, values=[str(v) for v in range(25, 36)], width=65,
            command=self.calcular_necessidades_dri)
        self.combo_fator_bolso.set("25")
        self.combo_fator_bolso.pack(side="left", padx=5)
        ctk.CTkLabel(linha_dri, text="kcal/kg/dia", text_color=tema.TEXTO).pack(side="left")
        self.entry_fator_proteico = ctk.CTkEntry(
            linha_dri, placeholder_text="Proteína g/kg", width=110, fg_color=tema.BRANCO,
            text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_fator_proteico.pack(side="left", padx=(12, 4))
        self.entry_fator_proteico.bind("<KeyRelease>", self.calcular_necessidades_dri)
        self.lbl_resultado_dri = ctk.CTkLabel(
            frame_dri, text="Preencha peso, altura e atividade física para estimar as necessidades.",
            text_color=tema.SUAVE, font=ctk.CTkFont(size=14), justify="left", wraplength=780)
        self.lbl_resultado_dri.pack(anchor="w", padx=8, pady=(4, 8))
        linha_condicao = ctk.CTkFrame(frame_dri, fg_color="transparent")
        linha_condicao.pack(fill="x", padx=8, pady=(2, 4))
        ctk.CTkLabel(linha_condicao, text="Condição reprodutiva:", text_color=tema.TEXTO).pack(side="left", padx=(0, 6))
        self.combo_dri_condicao = ctk.CTkComboBox(
            linha_condicao,
            values=["Não informado", "Não gestante/não lactante", "Gestante", "Lactante", "Não se aplica"],
            width=235, command=self.calcular_necessidades_dri)
        sexo_cadastro = str(self.paciente_atual_sexo or "").strip().casefold()
        self.combo_dri_condicao.set("Não se aplica" if sexo_cadastro in ("masculino", "homem", "male", "h") else "Não informado")
        self.combo_dri_condicao.pack(side="left", padx=5)
        ctk.CTkLabel(frame_dri,
                     text="DRI 2023 implementada para adultos ≥19 anos. Em mulheres, o cálculo exige confirmar 'Não gestante/não lactante'; não usar a equação adulta em gestação, lactação ou pediatria. O fator proteico é definido pelo profissional.",
                     text_color=tema.SUAVE, font=ctk.CTkFont(size=12), wraplength=780,
                     justify="left").pack(anchor="w", padx=8, pady=(0, 6))
        self.calcular_necessidades_dri(silencioso=True)

        frame_conduta = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        frame_conduta.pack(fill="x", padx=20, pady=(15, 0))
        ctk.CTkLabel(frame_conduta, text="Conduta Dietoterápica", font=ctk.CTkFont(weight="bold", size=17), text_color=tema.TEXTO).pack(side="left")
        if not getattr(sys, 'frozen', False):
            ctk.CTkButton(frame_conduta, text="Importar Padrão", width=120, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=14, weight="bold"), command=lambda: self.abrir_modal_padroes("conduta")).pack(side="right")
        self.txt_conduta = ctk.CTkTextbox(scroll_frame, width=600, height=100, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, border_width=1, border_color=tema.BORDA)
        self.txt_conduta.pack(padx=20, pady=5)

        # Condutas de alta: sugeridas pelas doenças relatadas no Mapa; só valem depois de confirmadas pela nutricionista.
        self.painel_condutas_alta = PainelCondutasAlta(
            scroll_frame, caminho_do_banco(), self.paciente_atual_id, self.paciente_atual_nome,
            pasta_saida=self.pasta_condutas_alta(), janela_pai=self)
        self.painel_condutas_alta.pack(fill="x", padx=20, pady=(10, 5))
        ctk.CTkLabel(scroll_frame, text="Solicitação de Exames", font=ctk.CTkFont(weight="bold", size=17), text_color=tema.TEXTO).pack(anchor="w", padx=20, pady=(15, 0))
        frame_exames = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        frame_exames.pack(fill="x", padx=20, pady=5)

        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute("SELECT id_exame, nome_amigavel FROM Exames_Catalogo")
        self.catalogo_exames_dict = {f"{linha[1]} ({linha[0]})": linha[0] for linha in cursor.fetchall()}
        conexao.close()
        
        self.opcoes_exames = list(self.catalogo_exames_dict.keys())

        self.exame_escolhido = None
        self.btn_select_exame = ctk.CTkButton(
            frame_exames,
            text="Seleccionar exame...  ▼",
            width=400,
            fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._abrir_select_exame)
        self.btn_select_exame.grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(frame_exames, text="Adicionar à Solicitação", command=self.adicionar_exame, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=1)
        ctk.CTkButton(scroll_frame, text="Gerenciar associações: exames, diagnósticos clínicos e nutricionais",
                      command=lambda: DialogoAssociacoesExames(self, caminho_do_banco()),
                      fg_color=tema.SUAVE, hover_color=tema.SUAVE, text_color=tema.BRANCO,
                      font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20, pady=(2, 6))

        frame_analise_exames = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        frame_analise_exames.pack(fill="x", padx=20, pady=(15, 0))
        ctk.CTkLabel(frame_analise_exames, text="Análise e Valores de Referência", font=ctk.CTkFont(weight="bold", size=17), text_color=tema.TEXTO).pack(side="left")
        if not getattr(sys, 'frozen', False):
            ctk.CTkButton(frame_analise_exames, text="Importar Referências", width=160, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=14, weight="bold"), command=lambda: self.abrir_modal_padroes("exames")).pack(side="right")
        self.txt_analise_exames = ctk.CTkTextbox(scroll_frame, width=600, height=100, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, border_width=1, border_color=tema.BORDA)
        self.txt_analise_exames.pack(padx=20, pady=5)

        self.frame_lista_exames = ctk.CTkFrame(scroll_frame, fg_color=tema.BRANCO, border_width=1, border_color=tema.VERDE_CLARO)
        self.frame_lista_exames.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(scroll_frame, text="Lançar Resultados", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=16, weight="bold"),
                      command=self.abrir_modal_resultados).pack(pady=(0, 10))
        
        self.frame_sugestoes = ctk.CTkFrame(scroll_frame, fg_color=tema.VERDE, border_width=1, border_color=tema.VERDE)
        self.frame_sugestoes.pack(fill="x", padx=20, pady=10)
        self.frame_sugestoes.pack_forget()

        self.btn_salvar_evolucao = ctk.CTkButton(scroll_frame, text="Salvar Evolução", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=18, weight="bold"), height=44, command=self.salvar_consulta)
        self.btn_salvar_evolucao.pack(pady=(30, 10))
        
        self.lbl_msg_consulta = ctk.CTkLabel(scroll_frame, text="", text_color=tema.VERDE, font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_msg_consulta.pack(pady=5)

    def atualizar_justificativa_metodologica(self, escolha):
        if escolha == "Cunningham (1980)":
            texto = "Justificativa: Cunningham (1980) baseia-se na Massa Livre de Gordura (MLG), sendo o modelo com maior precisão para indivíduos fisicamente ativos e desportistas, prevenindo superestimação."
        elif escolha == "Harris-Benedict (1919)":
            texto = "Justificativa: Harris; Benedict (1919) tende a superestimar o gasto basal em 5% a 15% na população moderna. O uso deve ser cauteloso e acompanhado de anamnese criteriosa."
        elif escolha == "Mifflin-St Jeor (1990)":
            texto = "Justificativa: Mifflin; St Jeor (1990) apresenta maior precisão para adultos saudáveis contemporâneos com sobrepeso ou obesidade, baseando-se no peso total."
        self.lbl_justificativa.configure(text=texto)

    def calcular_metabolismo(self):
        try:
            peso_str = self.entry_peso.get().replace(',', '.')
            altura_str = self.entry_altura.get().replace(',', '.')
            if not peso_str or not altura_str:
                self.lbl_resultado_metabolismo.configure(text="Erro: Preencha Peso e Altura primeiro.", text_color=tema.ERRO)
                return
            peso = float(peso_str)
            altura_cm = float(altura_str) * 100.0
            nasc_date = datetime.strptime(self.paciente_atual_nasc, "%d/%m/%Y")
            hoje = datetime.now()
            idade = hoje.year - nasc_date.year - ((hoje.month, hoje.day) < (nasc_date.month, nasc_date.day))
            if idade < 19:
                self.tmb_atual = ""
                self.vet_atual = ""
                self.lbl_resultado_metabolismo.configure(
                    text="Equações de TMB adultas não se aplicam a menores de 19 anos. Use avaliação pediátrica específica.",
                    text_color=tema.LARANJA_TEXTO)
                return
            metodo = self.combo_metodo_tmb.get()
            sexo = self.paciente_atual_sexo.lower()
            tmb = 0.0
            
            if metodo == "Harris-Benedict (1919)":
                if "fem" in sexo: tmb = 655.0955 + (9.5634 * peso) + (1.8496 * altura_cm) - (4.6756 * idade)
                else: tmb = 66.4730 + (13.7516 * peso) + (5.0033 * altura_cm) - (6.7550 * idade)
            elif metodo == "Mifflin-St Jeor (1990)":
                if "fem" in sexo: tmb = (10.0 * peso) + (6.25 * altura_cm) - (5.0 * idade) - 161.0
                else: tmb = (10.0 * peso) + (6.25 * altura_cm) - (5.0 * idade) + 5.0
            elif metodo == "Cunningham (1980)":
                gordura_str = self.entry_gordura.get().replace(',', '.')
                if not gordura_str:
                    self.lbl_resultado_metabolismo.configure(text="Erro: O método de Cunningham exige o % de Gordura.", text_color=tema.ERRO)
                    return
                gordura = float(gordura_str)
                massa_livre_gordura = peso * (1.0 - (gordura / 100.0))
                tmb = 500.0 + (22.0 * massa_livre_gordura)
            
            naf_str = self.entry_naf.get().replace(',', '.')
            self.tmb_atual = str(tmb)
            if naf_str:
                vet = tmb * float(naf_str)
                self.vet_atual = str(vet)
                self.lbl_resultado_metabolismo.configure(text=f"TMB: {tmb:.2f} kcal  |  VET: {vet:.2f} kcal", text_color=tema.VERDE)
            else:
                self.vet_atual = ""
                self.lbl_resultado_metabolismo.configure(text=f"TMB: {tmb:.2f} kcal  |  (Insira o NAF para calcular VET)", text_color=tema.VERDE)
        except ValueError:
            self.lbl_resultado_metabolismo.configure(text="Erro de formatação: Insira apenas números válidos.", text_color=tema.ERRO)
        except Exception:
            self.lbl_resultado_metabolismo.configure(text=f"Erro no cálculo.", text_color=tema.ERRO)

    def abrir_modal_padroes(self, alvo):
        """Abre a biblioteca de padrões em uma guia lateral, preservando a consulta anterior."""
        titulos = {
            "conduta": "Importar Condutas e Prescrições",
            "anamnese": "Importar Sintomas Clínicos",
            "exames": "Importar Análise e Valores de Referência",
        }
        titulo = titulos.get(alvo, "Importar padrões")
        painel = self.abrir_painel_modal(titulo, lambda: None)
        cabecalho = ctk.CTkFrame(painel, fg_color="transparent")
        cabecalho.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(cabecalho, text=titulo, font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=tema.TEXTO).pack(side="left")
        ctk.CTkButton(cabecalho, text="Fechar guia", width=100,
                      command=lambda: self.fechar_painel_lateral(painel)).pack(side="right")
        tabview_modal = _criar_tabview_compat(
            painel, fonte_abas=ctk.CTkFont(size=15, weight="bold"),
            fg_color=tema.FUNDO,
            segmented_button_selected_color=tema.VERDE,
            segmented_button_selected_hover_color=tema.VERDE_ESC,
            segmented_button_unselected_color=tema.VERDE_CLARO,
            segmented_button_unselected_hover_color=tema.BORDA,
            text_color=tema.TEXTO, text_color_disabled=tema.SUAVE
        )
        tabview_modal.pack(padx=10, pady=10, fill="both", expand=True)
        if alvo == "conduta":
            aba_condutas = tabview_modal.add("Condutas")
            aba_prescricoes = tabview_modal.add("Prescrições")
            self.listar_arquivos_diretorio("condutas_internas", aba_condutas, self.txt_conduta)
            self.listar_arquivos_diretorio("prescricoes_internas", aba_prescricoes, self.txt_conduta)
        elif alvo == "anamnese":
            aba_sintomas = tabview_modal.add("Sintomas")
            self.listar_arquivos_diretorio("sintomas_internos", aba_sintomas, self.txt_anamnese)
        elif alvo == "exames":
            aba_exames_ref = tabview_modal.add("Exames")
            self.listar_arquivos_diretorio("exames_internos", aba_exames_ref, self.txt_analise_exames)

    @staticmethod
    def _normalizar_token(texto):
        """Remove prefixo EXM-, espaços, hífens, underscores e converte para minúsculas."""
        if not texto:
            return ""
        t = str(texto)
        if t.upper().startswith("EXM-"):
            t = t[4:]
        return re.sub(r'[\s\-_]+', '', t).lower()

    @staticmethod
    def _coerce_float(valor):
        """Converte para float quando o valor é numérico; devolve None caso contrário."""
        if isinstance(valor, bool):
            return None
        if isinstance(valor, (int, float)):
            return float(valor)
        if isinstance(valor, str):
            s = valor.strip().replace(',', '.')
            try:
                return float(s)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_num(texto):
        """Extrai o primeiro número de uma string, aceitando vírgula decimal."""
        if not isinstance(texto, str):
            return None
        m = re.search(r'\d+(?:[.,]\d+)?', texto.replace(',', '.'))
        if not m:
            return None
        try:
            return float(m.group(0))
        except ValueError:
            return None

    def _extrair_refs_por_regex(self, texto):
        """Fallback: extrai (ref_min, ref_max) de texto livre usando regex."""
        if not isinstance(texto, str) or not texto:
            return (None, None)
        t = texto.lower()

        # Faixa: 'NUM a NUM', 'NUM - NUM', 'NUM até NUM', 'entre NUM e NUM'
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:a|até|-|–|—)\s*(\d+(?:[.,]\d+)?)', t)
        if m:
            return (self._parse_num(m.group(1)), self._parse_num(m.group(2)))

        m = re.search(r'entre\s*(\d+(?:[.,]\d+)?)\s*(?:e|a|até)\s*(\d+(?:[.,]\d+)?)', t)
        if m:
            return (self._parse_num(m.group(1)), self._parse_num(m.group(2)))

        # Limite superior: '< NUM', '≤ NUM', 'inferior a NUM'
        m = re.search(r'(?:<\s*|≤\s*|inferior\s*a\s*)(\d+(?:[.,]\d+)?)', t)
        if m:
            return (None, self._parse_num(m.group(1)))

        # Limite inferior: '> NUM', '≥ NUM', 'superior a NUM'
        m = re.search(r'(?:>\s*|≥\s*|superior\s*a\s*)(\d+(?:[.,]\d+)?)', t)
        if m:
            return (self._parse_num(m.group(1)), None)

        return (None, None)

    def _procurar_arquivo_exame(self, id_exame):
        """Devolve o caminho absoluto do ficheiro JSON do exame, ou None."""
        base_dir = get_base_path()
        pasta = os.path.join(base_dir, "exames_internos")
        if not os.path.isdir(pasta):
            return None

        alvo = self._normalizar_token(id_exame)
        if not alvo:
            return None

        try:
            for nome in os.listdir(pasta):
                if not nome.lower().endswith(('.json', '.jsonux')):
                    continue
                stem = os.path.splitext(nome)[0]
                if self._normalizar_token(stem) == alvo:
                    return os.path.join(pasta, nome)
        except OSError:
            return None
        return None

    def _carregar_refs_exame(self, id_exame):
        """Localiza o ficheiro JSON do exame e devolve (ref_min, ref_max).

        Estratégia:
          1. Localiza o arquivo (ver _procurar_arquivo_exame).
          2. Tenta ler 'ref_min' e 'ref_max' explícitos do JSON.
          3. Se ausentes, aplica fallback por regex sobre os campos textuais.
        Devolve sempre (ref_min, ref_max) com floats ou None.
        """
        caminho = self._procurar_arquivo_exame(id_exame)
        if not caminho:
            return (None, None)

        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                conteudo = f.read()
        except OSError:
            return (None, None)

        try:
            dados = json.loads(conteudo)
        except json.JSONDecodeError:
            dados = None

        # 1) Chaves explícitas
        ref_min = ref_max = None
        if isinstance(dados, dict):
            if 'ref_min' in dados or 'ref_max' in dados:
                ref_min = self._coerce_float(dados.get('ref_min'))
                ref_max = self._coerce_float(dados.get('ref_max'))
                return (ref_min, ref_max)

        # 2) Fallback por regex sobre todo o texto do ficheiro
        return self._extrair_refs_por_regex(conteudo)

    def _carregar_bandas_exame(self, id_exame):
        """Lê as faixas personalizadas ('bandas') do JSON, normalizadas como lista de dicts:
        {'valor_max': float|None, 'inclusivo': bool, 'rotulo': str}, ou None se não houverem.

        Cada banda representa um intervalo semiaberto/fechado até 'valor_max'
        (inclusivo=True -> valor ≤ valor_max; inclusivo=False -> valor < valor_max).
        A última banda com 'valor_max' nulo cobre todo o resto acima.
        """
        caminho = self._procurar_arquivo_exame(id_exame)
        if not caminho:
            return None
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                conteudo = f.read()
        except OSError:
            return None
        try:
            dados = json.loads(conteudo)
        except json.JSONDecodeError:
            return None
        if not isinstance(dados, dict) or not isinstance(dados.get('bandas'), list):
            return None

        lista = []
        for b in dados['bandas'] if isinstance(dados.get('bandas'), list) else []:
            if not isinstance(b, dict):
                continue
            lista.append({
                'valor_max': self._coerce_float(b.get('valor_max')),
                'inclusivo': bool(b.get('inclusivo', True)),
                'rotulo': (b.get('rotulo') or b.get('rotulo_tecnico') or b.get('classificacao_simplificada') or 'Sem referência'),
            })
        return lista or None

    def _classificar_valor(self, valor, ref_min=None, ref_max=None, bandas=None):
        """Devolve rótulo clínico (faixa personalizada) ou 'Baixo'/'Normal'/'Alto'/'Sem referência'.

        Se 'bandas' (faixas personalizadas do JSON) estiverem disponíveis, usa-as primeiro —
        cada banda usa 'valor_max' (teto do intervalo) e rótulo textual próprio (ex.:
        'Hipoglicemia', 'Risco de pré-diabetes', 'Desejável' etc.), permitindo laudos
        personalizados em vez de forçar apenas Alto/Baixo/Normal.
        """
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            return "Sem referência"

        # 1ª via: faixas personalizadas do JSON
        if bandas:
            for banda in bandas:
                valor_max = banda.get('valor_max')
                rotulo = banda.get('rotulo') or "Sem referência"
                if valor_max is None:
                    return rotulo
                if banda.get('inclusivo', True):
                    if valor <= valor_max:
                        return rotulo
                else:
                    if valor < valor_max:
                        return rotulo
            return "Sem referência"

        # 2ª via (fallback histórico): ref_min / ref_max
        try:
            ref_min_f = float(ref_min) if ref_min is not None else None
        except (TypeError, ValueError):
            ref_min_f = None
        try:
            ref_max_f = float(ref_max) if ref_max is not None else None
        except (TypeError, ValueError):
            ref_max_f = None

        if ref_min_f is None and ref_max_f is None:
            return "Sem referência"
        if ref_min_f is not None and valor < ref_min_f:
            return "Baixo"
        if ref_max_f is not None and valor > ref_max_f:
            return "Alto"
        return "Normal"

    def _cor_status(self, status):
        """Escolhe a cor da label conforme o rótulo clínico do laudo."""
        s = (status or "").lower()
        if "sem referência" in s:
            return tema.SUAVE
        if any(k in s for k in ("normal", "desejável", "desejav", "adequado", "ótimo", "otimo", "protetor", "proteção")):
            return tema.VERDE
        if any(k in s for k in ("limítrofe", "limitrofe", "risco", "pré-diabetes", "pré-diabete", "indica")):
            return tema.LARANJA
        return tema.ERRO

    def _avaliar_entry_resultado(self, entry, lbl_status, id_exame):
        """Callback do <KeyRelease>: lê o valor, classifica e atualiza a label."""
        texto = entry.get().strip().replace(',', '.')
        if not texto:
            lbl_status.configure(text="")
            return
        try:
            valor = float(texto)
        except ValueError:
            lbl_status.configure(text="Valor inválido", text_color=tema.LARANJA)
            return
        ref_min, ref_max = self._carregar_refs_exame(id_exame)
        bandas = self._carregar_bandas_exame(id_exame)
        status = self._classificar_valor(valor, ref_min, ref_max, bandas)
        lbl_status.configure(text=status, text_color=self._cor_status(status))

    def _recalcular_indices_dinamicos(self):
        """Recalcula e atualiza os índices metabólicos dinâmicos na tela de resultados.

        Verifica se os pares de exames necessários estão presentes e preenchidos
        na tela atual (self._entries_resultados). Se sim, mostra/atualiza eles;
        se faltam, oculta os labels correspondentes.
        """
        try:
            entries = getattr(self, '_entries_resultados', {})
            if not entries:
                return

            # DEBUG: verifica as chaves (id_exame) atuais na interface
            print(f"[DEBUG calculo] Chaves ativas na interface: {list(entries.keys())}")

            def _buscar_valor(*possibles):
                """Busca flexible: prueba IDs exactos y luego substring en las keys reales."""
                # 1) Intentar IDs exactos directamente
                for pid in possibles:
                    par = entries.get(pid)
                    if par:
                        entry = par[0]
                        texto = entry.get().strip().replace(',', '.')
                        if texto:
                            try:
                                return float(texto)
                            except ValueError:
                                pass
                # 2) Fallback: substring flexible sobre todas las keys reales
                keys_upper = {k.upper(): k for k in entries.keys()}
                for needle in possibles:
                    nu = (needle or '').upper()
                    for ku, kv in keys_upper.items():
                        if nu in ku or ku in nu:
                            par = entries.get(kv)
                            if par:
                                entry = par[0]
                                texto = entry.get().strip().replace(',', '.')
                                if texto:
                                    try:
                                        return float(texto)
                                    except ValueError:
                                        pass
                return None

            # --- 1. Índice de De Ritis (TGO / TGP) ---
            tgo = _buscar_valor("EXM-AST-TGO", "EXM-TGO", "EXM-AST", "AST", "TGO")
            tgp = _buscar_valor("EXM-ALT-TGP", "EXM-TGP", "EXM-ALT", "ALT", "TGP")
            self._atualizar_label_indice(
                "de_ritis", tgo, tgp, tgo / tgp if (tgo and tgp) else None,
                self._interpretar_de_ritis,
                "Uprota Índice de De Ritis (TGO/TGP): {valor:.2f} | {interp}",
                "TGO (AST) e TGP (ALT) preenchidos para calcular o índice de De Ritis. Limpe um para ocultar.",
            )

            # --- 2. Relação TG / HDL ---
            tg  = _buscar_valor("EXM-TRIGLICERIDEOS", "TRIGLICERIDEOS", "TG", "TRIGLICERIDES")
            hdl = _buscar_valor("EXM-HDL-COLESTEROL", "HDL-COLESTEROL", "HDL")
            self._atualizar_label_indice(
                "tg_hdl", tg, hdl, tg / hdl if (tg and hdl) else None,
                self._interpretar_tg_hdl,
                "Uprota Relação TG/HDL: {valor:.2f} | {interp}",
                "Triglicerídeos e HDL preenchidos para calcular a relação TG/HDL. Limpe um para ocultar.",
            )

            # --- 3. Fração Aterogênica (Não-HDL / Total) ---
            total = _buscar_valor("EXM-COLESTEROL-TOTAL", "COLESTEROL-TOTAL", "COLESTEROLTOTAL", "Colesterol Total")
            hdl2  = _buscar_valor("EXM-HDL-COLESTEROL", "HDL-COLESTEROL", "HDL", "HDL-COLESTEROL")
            nao_hdl_pct = ((total - hdl2) / total * 100) if (total and hdl2) else None
            self._atualizar_label_indice(
                "fracao_atero", total, hdl2, nao_hdl_pct,
                self._interpretar_fracao_atero,
                "Uprota Fração Aterogênica (Não-HDL/Total): {valor:.1f}% | {interp}",
                "Colesterol Total e HDL preenchidos para calcular a fração aterogênica. Limpe um para ocultar.",
            )

            # --- 4. Razão Apo B / Apo A-1 ---
            apo_b = _buscar_valor("EXM-APOLIPOPROTEINA-B", "APOLIPOPROTEINA-B", "EXM-APO-B", "APO-B", "Apo B", "APOLIPOPROTEINA B")
            apo_a = _buscar_valor("EXM-APO-A1", "APO-A1", "Apo A-1", "APOLIPOPROTEINA A-1")
            self._atualizar_label_indice(
                "apo_b_apo_a", apo_b, apo_a, apo_b / apo_a if (apo_b and apo_a) else None,
                lambda v: self._interpretar_apo_ratio(v),
                "Uprota Razão Apo B / Apo A-1: {valor:.2f} | {interp}",
                "Apolipoproteína B e A-1 preenchidas para calcular a razão. Limpe uma para ocultar.",
            )
        except Exception as e:
            print(f"[ERRO CRÍTICO CALCULADORA]: {e}")

    def _atualizar_label_indice(self, chave, val_a, val_b, valor_calc, interp_fn, fmt_str, empty_msg):
        """Mostra/oculta/atualiza un label dinámico de índice en pantalla."""
        if val_a is None or val_b is None or valor_calc is None:
            self._limpar_label_indice(chave)
            return
        try:
            valor = float(valor_calc)
        except (TypeError, ValueError):
            self._limpar_label_indice(chave)
            return
        interp = interp_fn(valor)
        texto = fmt_str.format(valor=valor, interp=interp)
        label = self._labels_calculo.get(chave)
        if label is None:
            label = ctk.CTkLabel(self._frame_indices, text=texto, font=ctk.CTkFont(size=14, weight="bold"),
                                 text_color=tema.AZUL, justify="left")
            label.pack(anchor="w", pady=(6, 2))
            self._labels_calculo[chave] = label
        else:
            label.configure(text=texto)

    def _limpar_label_indice(self, chave):
        """Remove un label dinámico cuando el par deja de estar completo."""
        label = self._labels_calculo.pop(chave, None)
        if label and label.winfo_exists():
            label.destroy()

    @staticmethod
    def _interpretar_de_ritis(valor):
        if valor < 1.0:
            return "Agressão hepatocelular inicial ou esteatose hepática."
        elif valor <= 2.0:
            return "Evolução para fibrose/cirrose hepática crônica."
        else:
            return "Achado altamente específico para hepatite alcoólica."

    @staticmethod
    def _interpretar_tg_hdl(valor):
        if valor > 2.5:
            return "Dislipidemia aterogênica / forte resistência à insulina / síndrome metabólica."
        else:
            return "Dentro do esperado."

    @staticmethod
    def _interpretar_fracao_atero(valor):
        if valor < 30:
            return "Baixa porcentagem de colesterol aterogênico."
        elif valor < 50:
            return "Intermediária."
        else:
            return "Alta porcentagem aterogênica — maior risco cardiovascular."

    @staticmethod
    def _interpretar_apo_ratio(valor):
        return "Consulte a tabela de Wallach (Homens: 0.4 ↓ risco / 1.6 ↑ risco; Mulheres: 0.3 ↓ risco / 1.5 ↑ risco)."

    def abrir_modal_resultados(self):
        if not self.exames_selecionados_lista:
            ctk.CTkLabel(self.area_principal, text="")  # noop (mantém referência)
            # Mensagem simples via lbl_msg_consulta se existir
            if hasattr(self, 'lbl_msg_consulta') and self.lbl_msg_consulta.winfo_exists():
                self.lbl_msg_consulta.configure(text="Adicione exames à solicitação antes de lançar resultados.", text_color=tema.LARANJA)
            return

        modal = self.abrir_painel_modal("Lançar Resultados Laboratoriais", lambda: None)
        cabecalho_resultados = ctk.CTkFrame(modal, fg_color="transparent")
        cabecalho_resultados.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(cabecalho_resultados, text="Lançamento de Resultados",
                     font=ctk.CTkFont(size=20, weight="bold"), text_color=tema.TEXTO).pack(side="left")
        ctk.CTkButton(cabecalho_resultados, text="Fechar guia", width=100,
                      command=lambda: self.fechar_painel_lateral(modal)).pack(side="right")

        scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Contêiner para os labels dinâmicos de índices metabólicos
        self._labels_calculo = {}
        self._frame_indices = ctk.CTkFrame(scroll, fg_color="transparent")
        self._frame_indices.pack(fill="x", pady=(0, 8))

        # Cache id_exame -> nome_amigavel para reusar labels
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute("SELECT id_exame, nome_amigavel FROM Exames_Catalogo")
        mapa_nomes = {row[0]: row[1] for row in cursor.fetchall()}
        conexao.close()

        self._entries_resultados = {}

        for id_exame in self.exames_selecionados_lista:
            linha = ctk.CTkFrame(scroll, fg_color=tema.BRANCO, corner_radius=6, border_width=1, border_color=tema.VERDE_CLARO)
            linha.pack(fill="x", pady=4, padx=4, ipady=4)

            nome = mapa_nomes.get(id_exame, id_exame)
            ctk.CTkLabel(linha, text=nome, width=200, anchor="w", font=ctk.CTkFont(size=15)).pack(side="left", padx=(10, 5), pady=6)

            entry = ctk.CTkEntry(linha, placeholder_text="Resultado", width=140, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
            entry.pack(side="left", padx=5, pady=6)

            lbl_status = ctk.CTkLabel(linha, text="", width=120, anchor="w", font=ctk.CTkFont(size=15))
            lbl_status.pack(side="left", padx=5, pady=6)

            self._entries_resultados[id_exame] = (entry, lbl_status)

            # Gatilho de status individual: actualiza ao perder o foco (FocusOut)
            entry.bind('<FocusOut>', lambda e, ent=entry, lbl=lbl_status, ex=id_exame: self._avaliar_entry_resultado(ent, lbl, ex))

            # Pré-preencher se já houver resultado lançado anteriormente
            if id_exame in self.resultados_lancados:
                valor_anterior, _ = self.resultados_lancados[id_exame]
                entry.insert(0, str(valor_anterior))
                self._avaliar_entry_resultado(entry, lbl_status, id_exame)

        # --- Botão manual para calcular os índices metabólicos ---
        ctk.CTkButton(
            scroll,
            text="Calcular Índices Clínicos",
            fg_color=tema.AZUL,
            hover_color=tema.AZUL_HOVER,
            text_color=tema.BRANCO,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._recalcular_indices_dinamicos
        ).pack(pady=(8, 4), fill="x")

        # --- Container onde os labels dinâmicos de índices aparecerão ---
        self._frame_indices.pack(side="bottom", fill="x", pady=(0, 8))

        def salvar_e_fechar():
            self.resultados_lancados = {}
            for id_exame, (entry, lbl_status) in self._entries_resultados.items():
                texto = entry.get().strip().replace(',', '.')
                if not texto:
                    continue
                try:
                    valor = float(texto)
                except ValueError:
                    continue
                ref_min, ref_max = self._carregar_refs_exame(id_exame)
                bandas = self._carregar_bandas_exame(id_exame)
                status = self._classificar_valor(valor, ref_min, ref_max, bandas)
                self.resultados_lancados[id_exame] = (valor, status)
            # Limpa os labels dinâmicos ao fechar a guia lateral
            self._labels_calculo = {}
            self.fechar_painel_lateral(modal)

        ctk.CTkButton(modal, text="Salvar", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=16, weight="bold"), command=salvar_e_fechar).pack(pady=(0, 10))

    def listar_arquivos_diretorio(self, diretorio, frame_aba, caixa_texto):
        scroll = ctk.CTkScrollableFrame(frame_aba, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        base_dir = get_base_path()
        caminho_dir = os.path.join(base_dir, diretorio)
        if not os.path.exists(caminho_dir):
            ctk.CTkLabel(scroll, text=f"Pasta '{diretorio}' não encontrada.", font=ctk.CTkFont(size=15)).pack(pady=10)
            return
        arquivos_encontrados = [os.path.join(root, f) for root, dirs, files in os.walk(caminho_dir) for f in files if f.lower().endswith(('.jsonux', '.json'))]
        if not arquivos_encontrados:
            ctk.CTkLabel(scroll, text="A pasta está vazia.", font=ctk.CTkFont(size=15)).pack(pady=10)
            return
        for caminho_completo in arquivos_encontrados:
            nome_arquivo = os.path.basename(caminho_completo)
            nome_amigavel = nome_arquivo.replace('.jsonux', '').replace('.json', '').replace('_', ' ')
            btn = ctk.CTkButton(scroll, text=nome_amigavel, anchor="w", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=14), command=lambda c=caminho_completo, t=caixa_texto: self.inserir_texto_padrao(c, t))
            btn.pack(fill="x", pady=2, padx=5)

    def inserir_texto_padrao(self, caminho_completo, caixa_texto):
        try:
            with open(caminho_completo, 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = f.read()
                try:
                    dados_json = json.loads(conteudo)
                    def formatar_dict_para_texto(dicionario):
                        linhas = []
                        if isinstance(dicionario, dict):
                            for chave, valor in dicionario.items():
                                if chave.lower() == "id": continue
                                chave_legivel = str(chave).replace("_", " ").capitalize()
                                if isinstance(valor, list):
                                    linhas.append(f"• {chave_legivel}:")
                                    for item in valor: linhas.append(f"  - {item}")
                                elif isinstance(valor, dict):
                                    linhas.append(f"• {chave_legivel}:")
                                else:
                                    linhas.append(f"• {chave_legivel}: {valor}")
                        return "\n".join(linhas)
                    conteudo = formatar_dict_para_texto(dados_json)
                except json.JSONDecodeError: pass
            texto_atual = caixa_texto.get("1.0", "end-1c")
            if texto_atual.strip(): caixa_texto.insert("end", "\n\n" + conteudo)
            else: caixa_texto.insert("end", conteudo)
        except Exception as e: print(f"Erro: {e}")

    def _abrir_select_exame(self):
        """Abre o catálogo de exames em uma guia lateral com filtro e rolagem."""
        painel = self.abrir_painel_modal("Selecionar exame", lambda: None)
        self._painel_select_exame = painel
        cabecalho = ctk.CTkFrame(painel, fg_color="transparent")
        cabecalho.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(cabecalho, text="Selecione um exame do catálogo",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=tema.TEXTO).pack(side="left")
        ctk.CTkButton(cabecalho, text="Fechar guia", width=100,
                      command=lambda: self.fechar_painel_lateral(painel)).pack(side="right")
        self.entry_filtro_exames = ctk.CTkEntry(
            painel, placeholder_text="Filtrar por nome...", font=ctk.CTkFont(size=15),
            fg_color=tema.BRANCO, text_color=tema.TEXTO,
            placeholder_text_color=tema.SUAVE, border_color=tema.BORDA
        )
        self.entry_filtro_exames.pack(fill="x", padx=15, pady=5)
        self.entry_filtro_exames.bind("<KeyRelease>", lambda _e: self._preencher_lista_exames())
        self.scroll_lista_exames = ctk.CTkScrollableFrame(
            painel, fg_color=tema.FUNDO, corner_radius=6
        )
        self.scroll_lista_exames.pack(fill="both", expand=True, padx=15, pady=10)
        self._preencher_lista_exames()

    def _preencher_lista_exames(self):
        """Reconstruye los botones del scroll según el filtro escrito."""
        for widget in self.scroll_lista_exames.winfo_children():
            widget.destroy()
        texto = self.entry_filtro_exames.get().strip().lower()
        opciones = [o for o in self.opcoes_exames if texto in o.lower()] if texto else self.opcoes_exames
        if not opciones:
            ctk.CTkLabel(self.scroll_lista_exames, text="Nenhum exame encontrado.", font=ctk.CTkFont(size=14), text_color=tema.SUAVE).pack(pady=20)
            return
        for opcion in opciones:
            ctk.CTkButton(self.scroll_lista_exames, text=opcion, anchor="w", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=14), command=lambda o=opcion: self._seleccionar_exame(o)).pack(fill="x", padx=5, pady=2)

    def _seleccionar_exame(self, opcion):
        """Guarda a escolha e fecha somente a guia do seletor de exames."""
        self.exame_escolhido = opcion
        self.btn_select_exame.configure(text=opcion)
        painel = getattr(self, "_painel_select_exame", None)
        if painel is not None:
            self.fechar_painel_lateral(painel)
            self._painel_select_exame = None

    def adicionar_exame(self, id_forcado=None, nome_forcado=None):
        if id_forcado and nome_forcado:
            id_exame = id_forcado
            nome_amigavel = nome_forcado
        else:
            escolha = self.exame_escolhido
            if not escolha or escolha == "Nenhum exame encontrado...": return
            id_exame = self.catalogo_exames_dict.get(escolha)
            if not id_exame: return
            nome_amigavel = escolha.split(" (")[0]
        if id_exame in self.exames_selecionados_lista: return
        self.exames_selecionados_lista.append(id_exame)
        ctk.CTkLabel(self.frame_lista_exames, text=f"• {nome_amigavel}", font=ctk.CTkFont(size=15), text_color=tema.TEXTO).pack(anchor="w", padx=10, pady=2)
        self.exame_escolhido = None
        self.btn_select_exame.configure(text="Seleccionar exame...  ▼")
        self.verificar_regras_inteligentes(id_exame)

    def verificar_regras_inteligentes(self, id_gatilho):
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute('''SELECT E.id_exame, E.nome_amigavel FROM Regras_Complementares R
                          JOIN Exames_Catalogo E ON R.exame_sugerido = E.id_exame
                          WHERE R.exame_gatilho = ?''', (id_gatilho,))
        sugestoes = cursor.fetchall()
        cursor.execute("SELECT id_exame, nome_amigavel FROM Exames_Catalogo")
        nomes_exames = {r[0]: r[1] for r in cursor.fetchall()}
        conexao.close()
        exibidos = set()
        for sug_id, sug_nome in sugestoes:
            if sug_id not in self.exames_selecionados_lista:
                self.exibir_sugestao(sug_id, sug_nome)
                exibidos.add(sug_id)
        # Associações configuráveis: exame recomendado ou relação com diagnóstico.
        try:
            with sqlite3.connect(caminho_do_banco()) as conn:
                associacoes = ambulatorial.associacoes_do_exame(conn, id_gatilho)
            for item in associacoes:
                tipo, valor = item["tipo_associacao"], item["valor_relacionado"]
                if tipo == "exame_recomendado":
                    nome = nomes_exames.get(valor, valor)
                    if valor not in self.exames_selecionados_lista and valor not in exibidos:
                        self.exibir_sugestao(valor, nome)
                        exibidos.add(valor)
                else:
                    self.exibir_sugestao_diagnostico(item)
        except sqlite3.Error as exc:
            print(f"[AVISO] Não foi possível carregar as associações clínicas do exame: {exc}")

    def exibir_sugestao_diagnostico(self, associacao):
        self.frame_sugestoes.pack(fill="x", padx=20, pady=10)
        tipo = {"diagnostico_clinico": "diagnóstico clínico",
                "diagnostico_nutricional": "diagnóstico nutricional"}.get(
                    associacao["tipo_associacao"], "diagnóstico")
        container = ctk.CTkFrame(self.frame_sugestoes, fg_color="transparent")
        container.pack(fill="x", padx=10, pady=5)
        texto = f"Relação para revisão profissional — {tipo}: {associacao['valor_relacionado']}"
        if associacao.get("justificativa"):
            texto += f" | {associacao['justificativa']}"
        ctk.CTkLabel(container, text=texto, text_color=tema.BRANCO,
                     font=ctk.CTkFont(size=13), wraplength=620, justify="left").pack(anchor="w")

    def exibir_sugestao(self, sug_id, sug_nome):
        self.frame_sugestoes.pack(fill="x", padx=20, pady=10)
        container = ctk.CTkFrame(self.frame_sugestoes, fg_color="transparent")
        container.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(container, text=f"💡 Sugestão: O exame '{sug_nome}' é complementar à sua solicitação.", text_color=tema.BRANCO, font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkButton(container, text="Adicionar", width=80, fg_color=tema.BORDA, hover_color=tema.BORDA, text_color=tema.TEXTO, font=ctk.CTkFont(size=14, weight="bold"), command=lambda: [self.adicionar_exame(sug_id, sug_nome), container.destroy()]).pack(side="right")

    def _calcular_idade_por_nascimento(self, data_nasc):
        """Calcula a idade exata (anos completos) a partir da data de nascimento."""
        if not data_nasc:
            return None
        texto = str(data_nasc).strip()
        for formato in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
            try:
                nascimento = datetime.strptime(texto, formato).date()
                hoje = datetime.now().date()
                return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
            except ValueError:
                continue
        return None

    @staticmethod
    def _classificar_imc(imc, idade):
        """Classifica o IMC conforme a faixa etária.

        Idoso (>= 60 anos): < 22.0 Baixo peso | 22.0-27.0 Eutrofia | > 27.0 Sobrepeso
        Adulto (< 60 anos): réguas clássicas da OMS (18.5/25/30/35/40).
        Sem idade informada, aplica-se a régua de adulto (fallback documentado).
        """
        if idade is None:
            idade = 30  # fallback: régua de adulto quando não há data de nascimento
        if idade >= 60:
            if imc < 22.0:
                return "Baixo peso"
            if imc <= 27.0:
                return "Eutrofia"
            return "Sobrepeso"
        if imc < 18.5:
            return "Baixo peso"
        if imc < 25.0:
            return "Eutrofia"
        if imc < 30.0:
            return "Sobrepeso"
        if imc < 35.0:
            return "Obesidade grau I"
        if imc < 40.0:
            return "Obesidade grau II"
        return "Obesidade grau III"

    def calcular_necessidades_dri(self, *args, silencioso=False):
        """Atualiza EER, comparação kcal/kg e proteína quando os dados estão disponíveis."""
        try:
            peso, altura = self.entry_peso.get().strip(), self.entry_altura.get().strip()
            if not peso or not altura:
                self.calculos_ambulatoriais = {}
                if hasattr(self, "lbl_resultado_dri"):
                    self.lbl_resultado_dri.configure(
                        text="Preencha peso e altura para estimar as necessidades.", text_color=tema.SUAVE)
                return None
            idade = self._calcular_idade_por_nascimento(getattr(self, "paciente_atual_nasc", ""))
            if idade is None:
                raise ambulatorial.ErroAmbulatorial("Data de nascimento ausente ou inválida no cadastro do paciente.")
            condicao = self.combo_dri_condicao.get() if hasattr(self, "combo_dri_condicao") else "Não informado"
            if condicao not in ("Não gestante/não lactante", "Não se aplica"):
                raise ambulatorial.ErroAmbulatorial(
                    "A DRI EER adulta só é calculada após confirmar que não há gestação ou lactação. "
                    "Para gestantes/lactantes ou condição não informada, use avaliação específica.")
            pal = {"Inativo": "inativo", "Pouco ativo": "pouco_ativo",
                   "Ativo": "ativo", "Muito ativo": "muito_ativo"}.get(self.combo_dri_atividade.get(), "inativo")
            resumo = ambulatorial.calcular_resumo_nutricional(
                peso, altura, idade, self.paciente_atual_sexo, pal,
                self.combo_fator_bolso.get(), self.entry_fator_proteico.get().strip())
            self.calculos_ambulatoriais = resumo
            texto = (f"IMC: {resumo['imc_kg_m2']:.2f} kg/m²   |   "
                     f"DRI 2023 (EER): {resumo['dri_2023_kcal_dia']:.0f} kcal/dia   |   "
                     f"Bolso ({resumo['formula_bolso_fator_kcal_kg']} kcal/kg): "
                     f"{resumo['formula_bolso_kcal_dia']:.0f} kcal/dia")
            if resumo.get("proteina_g_dia") is not None:
                texto += (f"   |   Proteína ({resumo['proteina_fator_g_kg']} g/kg): "
                          f"{resumo['proteina_g_dia']:.1f} g/dia")
            self.lbl_resultado_dri.configure(text=texto, text_color=tema.TEXTO)
            return resumo
        except ambulatorial.ErroAmbulatorial as exc:
            self.calculos_ambulatoriais = {}
            if hasattr(self, "lbl_resultado_dri"):
                cor = tema.LARANJA_TEXTO if "19 anos" in str(exc) else tema.SUAVE
                self.lbl_resultado_dri.configure(text=str(exc), text_color=cor)
            if not silencioso:
                print(f"[AVISO] Cálculo DRI 2023 não realizado: {exc}")
            return None

    def _dados_anamnese_final(self):
        painel = getattr(self, "painel_consulta_estruturada", None)
        dados = painel.dados() if painel else {
            "anamnese_guiada": {}, "recordatorio_24h": "", "medicamentos": [], "metas": [],
            "recomendacoes_ids": [], "conduta_recomendacao": ""}
        necessidades = self.calcular_necessidades_dri(silencioso=True)
        antropometria = {}
        peso = self.entry_peso.get().strip()
        altura = self.entry_altura.get().strip()
        gordura = self.entry_gordura.get().strip()
        if peso: antropometria["peso_kg"] = peso
        if altura: antropometria["altura_m"] = altura
        if gordura: antropometria["gordura_percentual"] = gordura
        if peso and altura:
            try:
                antropometria["imc_kg_m2"] = ambulatorial.calcular_imc(peso, altura)
            except ambulatorial.ErroAmbulatorial:
                pass
        idade_consulta = self._calcular_idade_por_nascimento(getattr(self, "paciente_atual_nasc", ""))
        if idade_consulta is None or idade_consulta < 20:
            try:
                peso_num = float(peso.replace(",", ".")) if peso else None
                altura_cm = float(altura.replace(",", ".")) * 100 if altura else None
                self._atualizar_oms_pediatria_consulta(
                    antropometria.get("imc_kg_m2"), peso_num, altura_cm)
                antropometria["pediatria_oms"] = self._resultado_pediatria_consulta
            except (TypeError, ValueError):
                antropometria["pediatria_oms"] = {
                    "status": "pendente", "aviso": "Medidas antropométricas inválidas.", "resultados": {}}
        else:
            self._resultado_pediatria_consulta = {}
        texto = ambulatorial.montar_texto_anamnese(
            dados["anamnese_guiada"], dados["recordatorio_24h"], antropometria,
            necessidades, dados["medicamentos"], dados["metas"])
        complemento = self.txt_anamnese.get("1.0", "end-1c").strip()
        if complemento:
            texto += "\n\nANOTAÇÕES/COMPLEMENTO DA CONSULTA\n" + complemento
        return texto, dados, antropometria, necessidades

    def copiar_anamnese_softsus(self):
        try:
            texto, _, _, _ = self._dados_anamnese_final()
            if not texto.strip():
                messagebox.showwarning("Anamnese", "Preencha pelo menos um campo antes de copiar.", parent=self)
                return
            self.clipboard_clear()
            self.clipboard_append(texto)
            self.update()
            messagebox.showinfo("SoftSus", "Texto da anamnese copiado para a área de transferência.", parent=self)
        except Exception as exc:
            messagebox.showerror("Copiar anamnese", str(exc), parent=self)

    def _tabela_referencia_oms(self):
        if not hasattr(self, "_tabela_oms_pediatria"):
            self._tabela_oms_pediatria = None
            self._erro_tabela_oms_pediatria = None
            try:
                self._tabela_oms_pediatria = oms.TabelaReferenciaOMS.carregar_padrao(get_base_path())
            except (OSError, ValueError, TypeError) as exc:
                self._erro_tabela_oms_pediatria = str(exc)
        return self._tabela_oms_pediatria

    def _idade_exata_oms_consulta(self):
        bruto = str(getattr(self, "paciente_atual_nasc", "") or "").strip()
        if not bruto:
            return None, None, None, None, "Data de nascimento ausente no cadastro."
        nascimento = None
        for formato in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                nascimento = datetime.strptime(bruto, formato).date()
                break
            except ValueError:
                continue
        if nascimento is None:
            return None, None, None, None, "Data de nascimento inválida no cadastro."
        hoje = datetime.now().date()
        try:
            dias = oms.calcular_idade_dias(nascimento.isoformat(), hoje.isoformat())
            meses = oms.calcular_idade_meses(nascimento.isoformat(), hoje.isoformat())
        except ValueError as exc:
            return None, None, None, nascimento.isoformat(), str(exc)
        return dias, meses, dias / 30.4375, nascimento.isoformat(), None

    def _atualizar_oms_pediatria_consulta(self, imc, peso, altura_cm):
        sexo_bruto = str(getattr(self, "paciente_atual_sexo", "") or "").strip().casefold()
        if sexo_bruto in ("masculino", "homem", "male", "m", "h"):
            sexo = "H"
        elif sexo_bruto in ("feminino", "mulher", "female", "f"):
            sexo = "M"
        else:
            sexo = None
        tabela = self._tabela_referencia_oms()
        self._resultado_pediatria_consulta = oms.avaliar_paciente(
            sexo, peso, altura_cm, getattr(self, "paciente_atual_nasc", ""),
            datetime.now().date(), tabela, imc=imc)
        resultado = self._resultado_pediatria_consulta
        if resultado.get("status") == "nao_aplicavel":
            texto = "Indicadores OMS pediátricos não se aplicam a partir de 20 anos."
        elif not resultado.get("resultados"):
            texto = "OMS pediatria pendente: " + str(resultado.get("aviso") or "dados insuficientes.")
        else:
            nomes = {"imc_idade": "IMC/idade", "peso_idade": "Peso/idade", "estatura_idade": "Estatura/idade"}
            linhas = []
            for indicador, nome in nomes.items():
                item = (resultado.get("resultados") or {}).get(indicador) or {}
                if item.get("status") == "calculado":
                    linhas.append(f"{nome}: z={item['escore_z']:+.2f} — {item['classificacao']}")
                elif item.get("status") == "fora_faixa":
                    linhas.append(f"{nome}: não aplicável nesta idade")
                else:
                    linhas.append(f"{nome}: pendente")
            if tabela is None:
                linhas.insert(0, "Tabelas LMS oficiais não carregadas.")
            elif resultado.get("idade_meses_completos", 0) <= 59:
                linhas.insert(0, "Referência OMS 2006 — idade exata em dias.")
            elif resultado.get("idade_meses_completos", 0) <= 228:
                linhas.insert(0, "Referência OMS 2007 — interpolação por meses.")
            else:
                linhas.insert(0, "Fora da faixa OMS pediátrica (até 228 meses completos).")
            texto = "OMS pediatria — " + " | ".join(linhas)
        if hasattr(self, "lbl_oms_pediatria"):
            self.lbl_oms_pediatria.configure(text=texto)
        return resultado

    def _abrir_curvas_oms_consulta(self):
        try:
            peso_txt = self.entry_peso.get().strip().replace(",", ".")
            altura_txt = self.entry_altura.get().strip().replace(",", ".")
            peso = float(peso_txt) if peso_txt else None
            altura_cm = float(altura_txt) * 100 if altura_txt else None
            imc = peso / ((altura_cm / 100) ** 2) if peso and altura_cm else None
            resultado = self._atualizar_oms_pediatria_consulta(imc, peso, altura_cm)
        except (ValueError, ZeroDivisionError):
            messagebox.showwarning("Curvas OMS", "Confira peso e altura antes de abrir as curvas.", parent=self)
            return
        if not resultado or resultado.get("idade_meses_decimais") is None:
            messagebox.showwarning("Curvas OMS", "A avaliação pediátrica exige data de nascimento válida.", parent=self)
            return
        tabela = self._tabela_referencia_oms()
        if tabela is None:
            messagebox.showwarning("Curvas OMS", "As tabelas LMS oficiais não foram carregadas.", parent=self)
            return
        sexo = resultado.get("sexo")
        if sexo not in ("H", "M"):
            messagebox.showwarning("Curvas OMS", "O sexo do paciente não está definido no cadastro.", parent=self)
            return
        DialogCurvasOMS(
            self, tabela, sexo, resultado.get("idade_meses_decimais"),
            resultado.get("peso_kg"), resultado.get("altura_cm"), resultado.get("imc"))

    def _calcular_imc_dinamico(self, *args):
        """Atualiza IMC, classificação OMS pediátrica e estimativas energéticas."""
        try:
            peso_str = self.entry_peso.get().strip().replace(",", ".")
            altura_str = self.entry_altura.get().strip().replace(",", ".")
            if not peso_str or not altura_str:
                self.lbl_imc.configure(text="IMC: -- kg/m²", text_color=tema.SUAVE)
                self._atualizar_oms_pediatria_consulta(
                    None, peso_str or None, float(altura_str) * 100 if altura_str else None)
                if hasattr(self, "lbl_resultado_dri"):
                    self.calcular_necessidades_dri(silencioso=True)
                return
            peso, altura = float(peso_str), float(altura_str)
            if peso <= 0 or altura <= 0:
                raise ValueError("peso e altura devem ser maiores que zero")
            imc = peso / (altura ** 2)
            idade = self._calcular_idade_por_nascimento(getattr(self, "paciente_atual_nasc", ""))
            if idade is None:
                self._atualizar_oms_pediatria_consulta(imc, peso, altura * 100)
                self.lbl_imc.configure(text=f"IMC: {imc:.1f} kg/m² — classificação pendente (idade ausente)",
                                       text_color=tema.SUAVE)
            elif idade < 20:
                resultado = self._atualizar_oms_pediatria_consulta(imc, peso, altura * 100)
                imc_oms = (resultado.get("resultados") or {}).get("imc_idade") or {}
                if imc_oms.get("status") == "calculado":
                    texto = f"IMC: {imc:.1f} kg/m² — OMS: {imc_oms['classificacao']} (z={imc_oms['escore_z']:+.2f})"
                    cor = tema.TEXTO
                elif imc_oms.get("status") == "fora_faixa":
                    texto, cor = f"IMC: {imc:.1f} kg/m² — fora da faixa OMS", tema.LARANJA_TEXTO
                else:
                    texto, cor = f"IMC: {imc:.1f} kg/m² — classificação OMS pendente", tema.SUAVE
                self.lbl_imc.configure(text=texto, text_color=cor)
            else:
                self._resultado_pediatria_consulta = {}
                if hasattr(self, "lbl_oms_pediatria"):
                    self.lbl_oms_pediatria.configure(text="Indicadores OMS pediátricos não se aplicam a partir de 20 anos.")
                classificacao = self._classificar_imc(imc, idade)
                sufixo_idade = " (≥60 anos - régua idoso)" if idade >= 60 else ""
                self.lbl_imc.configure(
                    text=f"IMC: {imc:.1f} kg/m² — {classificacao}{sufixo_idade}",
                    text_color=tema.TEXTO)
            if hasattr(self, "lbl_resultado_dri"):
                self.calcular_necessidades_dri(silencioso=True)
        except (ValueError, ZeroDivisionError) as e:
            self.lbl_imc.configure(text="IMC: -- kg/m²", text_color=tema.SUAVE)
            if hasattr(self, "lbl_oms_pediatria"):
                self.lbl_oms_pediatria.configure(text=f"OMS pediatria pendente: {e}")
            self._resultado_pediatria_consulta = {"status": "pendente", "aviso": str(e), "resultados": {}}
            if hasattr(self, "lbl_resultado_dri"):
                self.calcular_necessidades_dri(silencioso=True)
        except Exception as e:
            print(f"[ERRO CRÍTICO IMC/OMS]: {e}")
            self.lbl_imc.configure(text="IMC: -- kg/m²", text_color=tema.SUAVE)
            if hasattr(self, "lbl_oms_pediatria"):
                self.lbl_oms_pediatria.configure(text="OMS pediatria: erro ao calcular; confira os dados do cadastro.")
            self._resultado_pediatria_consulta = {"status": "pendente", "aviso": str(e), "resultados": {}}
            if hasattr(self, "lbl_resultado_dri"):
                self.calcular_necessidades_dri(silencioso=True)

    def _calcular_indices_para_pdf(self, valores):
        """Recebe {NOME_EXAME: valor} e retorna as linhas de laudo dos pares clínicos.

        Usa a mesma lógica matemática e os mesmos interpretadores da calculadora
        da tela de resultados (_interpretar_*), garantindo consistência.
        """
        def busca(*chaves):
            for alvo in chaves:
                for chave, valor in valores.items():
                    if alvo in chave:
                        return valor
            return None

        linhas = []
        try:
            # 1) Índice de De Ritis (TGO / TGP)
            tgo = busca("TGO", "AST")
            tgp = busca("TGP", "ALT")
            if tgo and tgp:
                relacao = tgo / tgp
                linhas.append(
                    f"* Índice de De Ritis (TGO/TGP): {relacao:.2f} - "
                    f"{self._interpretar_de_ritis(relacao).replace(chr(8212), '-')}"
                )
            # 2) Relação TG / HDL
            tg = busca("TRIGLIC")
            hdl = busca("HDL")
            if tg and hdl:
                relacao = tg / hdl
                linhas.append(
                    f"* Relação TG/HDL: {relacao:.2f} - "
                    f"{self._interpretar_tg_hdl(relacao).replace(chr(8212), '-')}"
                )
            # 3) Fração Aterogênica (Não-HDL / Total)
            colesterol_total = None
            for chave, valor in valores.items():
                if "COLESTEROL" in chave and "TOTAL" in chave:
                    colesterol_total = valor
                    break
            if colesterol_total and hdl:
                pct = (colesterol_total - hdl) / colesterol_total * 100
                linhas.append(
                    f"* Fração Aterogênica (Não-HDL/Total): {pct:.1f}% - "
                    f"{self._interpretar_fracao_atero(pct).replace(chr(8212), '-')}"
                )
            # 4) Razão Apo B / Apo A-1
            apo_b = busca("APOLIPOPROTEINA B", "APO B", "APO-B")
            apo_a = busca("APOLIPOPROTEINA A", "APO A", "APO-A1", "APO-A")
            if apo_b and apo_a:
                relacao = apo_b / apo_a
                linhas.append(
                    f"* Razão Apo B / Apo A-1: {relacao:.2f} - "
                    f"{self._interpretar_apo_ratio(relacao)}"
                )
        except ZeroDivisionError:
            pass
        except Exception as e:
            print(f"[ERRO CRÍTICO ÍNDICES PDF]: {e}")
        return linhas

    def pasta_condutas_alta(self, id_paciente=None):
        """Pasta gravável da cópia em PDF da folha de alta: junto dos demais arquivos do paciente (fora do Git)."""
        id_paciente = id_paciente or self.paciente_atual_id
        return os.path.join(get_writable_path("arquivos_pacientes"), f"paciente_{id_paciente}")

    def salvar_consulta(self):
        if not self.paciente_atual_id: return
        anamnese, dados_estruturados, antropometria, necessidades = self._dados_anamnese_final()
        peso = self.entry_peso.get()
        altura = self.entry_altura.get()
        gordura = self.entry_gordura.get()
        naf = self.entry_naf.get()
        metodo = self.combo_metodo_tmb.get()
        conduta = self.txt_conduta.get("1.0", "end-1c")
        analise_exames = self.txt_analise_exames.get("1.0", "end-1c")

        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute('''
            INSERT INTO Consultas (id_paciente, data_consulta, anamnese, peso, altura, gordura, conduta, tmb, vet, naf, metodo_tmb, analise_exames)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.paciente_atual_id, data_atual, anamnese, peso, altura, gordura, conduta, self.tmb_atual, self.vet_atual, naf, metodo, analise_exames))
        
        id_consulta = cursor.lastrowid
        for id_exame in self.exames_selecionados_lista:
            cursor.execute('INSERT INTO Exames_Solicitados (id_consulta, id_exame) VALUES (?, ?)', (id_consulta, id_exame))
        for id_exame, (valor, status) in self.resultados_lancados.items():
            cursor.execute(
                'INSERT INTO Resultados_Exames (id_consulta, id_exame, valor, status) VALUES (?, ?, ?, ?)',
                (id_consulta, id_exame, valor, status)
            )

        # Campos adicionais em tabelas próprias para manter compatibilidade com Consultas legadas.
        dados_db = {
            "anamnese_guiada": dados_estruturados["anamnese_guiada"],
            "recordatorio_24h": dados_estruturados["recordatorio_24h"],
            "antropometria": antropometria,
            "necessidades": necessidades or {},
            "medicamentos": dados_estruturados["medicamentos"],
            "metas": dados_estruturados["metas"],
        }
        ambulatorial.salvar_dados_estruturados(conexao, id_consulta, dados_db)
        ambulatorial.associar_recomendacoes(
            conexao, id_consulta, self.paciente_atual_id,
            dados_estruturados["recomendacoes_ids"],
            dados_estruturados["conduta_recomendacao"])

        conexao.commit()
        conexao.close()
        self.lbl_msg_consulta.configure(text="Evolução salva com sucesso!")
        self.btn_salvar_evolucao.configure(state="disabled")
        # Sempre lembra as condutas de alta que ainda esperam confirmação (e oferece abrir a janela).
        lembrar_condutas_pendentes(getattr(self, "painel_condutas_alta", None), self.lbl_msg_consulta)

    # --- MÓDULO DE EXAMES E REGRAS ---
    def tela_exames(self):
        self.limpar_area_principal()
        
        titulo = ctk.CTkLabel(self.area_principal, text="Catálogo e Regras de Exames", font=ctk.CTkFont(size=24, weight="bold"), text_color=tema.TEXTO)
        titulo.pack(pady=(20, 10))

        tabview_exames = _criar_tabview_compat(self.area_principal, fonte_abas=ctk.CTkFont(size=15, weight="bold"),
                                        fg_color=tema.FUNDO,
                                        segmented_button_selected_color=tema.VERDE, segmented_button_selected_hover_color=tema.TEXTO,
                                        segmented_button_unselected_color=tema.VERDE, segmented_button_unselected_hover_color=tema.VERDE_HOVER,
                                        text_color=tema.BRANCO, text_color_disabled=tema.BORDA)
        tabview_exames.pack(padx=20, pady=10, fill="both", expand=True)

        aba_lista = tabview_exames.add("Lista de Exames")
        aba_regras = tabview_exames.add("Regras Inteligentes")

        # --- ABA 1: LISTA DE EXAMES ---
        frame_add = ctk.CTkFrame(aba_lista, fg_color="transparent")
        frame_add.pack(fill="x", pady=10)
        
        self.entry_id_exame = ctk.CTkEntry(frame_add, placeholder_text="ID (ex: EXM-FERRO)", width=200, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_id_exame.pack(side="left", padx=5)
        
        self.entry_nome_exame = ctk.CTkEntry(frame_add, placeholder_text="Nome do Exame (ex: FERRO SÉRICO)", width=300, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, placeholder_text_color=tema.SUAVE, border_color=tema.BORDA)
        self.entry_nome_exame.pack(side="left", padx=5)
        
        ctk.CTkButton(frame_add, text="Adicionar", width=100, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=15, weight="bold"), command=self.salvar_novo_exame).pack(side="left", padx=10)
        
        self.lbl_msg_exame = ctk.CTkLabel(aba_lista, text="", text_color=tema.VERDE, font=ctk.CTkFont(size=15))
        self.lbl_msg_exame.pack()

        tema.aplicar_tema_ttk(self)

        tree_frame = ctk.CTkFrame(aba_lista, fg_color=tema.FUNDO)
        tree_frame.pack(fill="both", expand=True, pady=10)

        self.tree_exames = ttk.Treeview(tree_frame, columns=("ID", "Nome"), show="headings", style="Treeview")
        self.tree_exames.heading("ID", text="ID do Exame")
        self.tree_exames.heading("Nome", text="Nome Amigável")
        self.tree_exames.column("ID", width=200, anchor="center")
        self.tree_exames.column("Nome", width=400)
        self.tree_exames.pack(side="left", fill="both", expand=True)
        
        scroll_exm = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_exames.yview)
        self.tree_exames.configure(yscrollcommand=scroll_exm.set)
        scroll_exm.pack(side="right", fill="y")
        
        self.carregar_tabela_exames()

        # --- ABA 2: REGRAS INTELIGENTES ---
        ctk.CTkLabel(aba_regras, text="Selecione um exame GATILHO que, quando solicitado, sugerirá o exame COMPLEMENTAR automaticamente.", wraplength=600, font=ctk.CTkFont(size=15), text_color=tema.TEXTO).pack(pady=10)
        
        frame_regras = ctk.CTkFrame(aba_regras, fg_color="transparent")
        frame_regras.pack(pady=20)
        
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute("SELECT id_exame, nome_amigavel FROM Exames_Catalogo ORDER BY nome_amigavel")
        exames_banco = cursor.fetchall()
        conexao.close()
        
        self.lista_exames_regras = [f"{ex[1]} ({ex[0]})" for ex in exames_banco]
        if not self.lista_exames_regras:
            self.lista_exames_regras = ["Nenhum exame cadastrado"]
        
        ctk.CTkLabel(frame_regras, text="Quando solicitar:", font=ctk.CTkFont(size=15), text_color=tema.TEXTO).grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.combo_gatilho = ctk.CTkComboBox(frame_regras, values=self.lista_exames_regras, width=300, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, button_color=tema.VERDE, button_hover_color=tema.VERDE_HOVER, dropdown_fg_color=tema.BRANCO, dropdown_hover_color=tema.VERDE_CLARO, dropdown_text_color=tema.TEXTO)
        self.combo_gatilho.grid(row=0, column=1, padx=10, pady=5)
        
        ctk.CTkLabel(frame_regras, text="Sugerir também:", font=ctk.CTkFont(size=15), text_color=tema.TEXTO).grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.combo_sugerido = ctk.CTkComboBox(frame_regras, values=self.lista_exames_regras, width=300, font=ctk.CTkFont(size=15), fg_color=tema.BRANCO, text_color=tema.TEXTO, button_color=tema.VERDE, button_hover_color=tema.VERDE_HOVER, dropdown_fg_color=tema.BRANCO, dropdown_hover_color=tema.VERDE_CLARO, dropdown_text_color=tema.TEXTO)
        self.combo_sugerido.grid(row=1, column=1, padx=10, pady=5)
        
        ctk.CTkButton(frame_regras, text="Criar Regra de Sugestão", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER, text_color=tema.BRANCO, font=ctk.CTkFont(size=15, weight="bold"), command=self.salvar_nova_regra).grid(row=2, column=0, columnspan=2, pady=20)
        
        self.lbl_msg_regra = ctk.CTkLabel(aba_regras, text="", text_color=tema.VERDE, font=ctk.CTkFont(size=15))
        self.lbl_msg_regra.pack()

    def carregar_tabela_exames(self):
        for item in self.tree_exames.get_children():
            self.tree_exames.delete(item)
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        cursor.execute("SELECT id_exame, nome_amigavel FROM Exames_Catalogo ORDER BY nome_amigavel")
        linhas = cursor.fetchall()
        conexao.close()
        for linha in linhas:
            self.tree_exames.insert("", "end", values=linha)

    def salvar_novo_exame(self):
        id_exame = self.entry_id_exame.get().strip().upper()
        nome = self.entry_nome_exame.get().strip().upper()
        
        if not id_exame or not nome:
            self.lbl_msg_exame.configure(text="Preencha o ID e o Nome.", text_color=tema.ERRO)
            return
            
        try:
            conexao = sqlite3.connect(caminho_do_banco())
            cursor = conexao.cursor()
            cursor.execute("INSERT INTO Exames_Catalogo (id_exame, nome_amigavel) VALUES (?, ?)", (id_exame, nome))
            conexao.commit()
            conexao.close()
            
            self.entry_id_exame.delete(0, 'end')
            self.entry_nome_exame.delete(0, 'end')
            self.lbl_msg_exame.configure(text="Exame adicionado com sucesso!", text_color=tema.VERDE)
            self.carregar_tabela_exames()
        except sqlite3.IntegrityError:
            self.lbl_msg_exame.configure(text="Erro: Este ID já existe no banco de dados.", text_color=tema.ERRO)

    def salvar_nova_regra(self):
        gatilho_full = self.combo_gatilho.get()
        sugerido_full = self.combo_sugerido.get()
        
        if not gatilho_full or not sugerido_full or gatilho_full == "Nenhum exame cadastrado":
            return
            
        # Extrai os IDs de dentro dos parênteses
        id_gatilho = gatilho_full.split("(")[-1].replace(")", "").strip()
        id_sugerido = sugerido_full.split("(")[-1].replace(")", "").strip()
        
        if id_gatilho == id_sugerido:
            self.lbl_msg_regra.configure(text="Erro: O gatilho e a sugestão não podem ser o mesmo exame.", text_color=tema.ERRO)
            return
            
        conexao = sqlite3.connect(caminho_do_banco())
        cursor = conexao.cursor()
        
        # Verifica se a regra já existe
        cursor.execute("SELECT 1 FROM Regras_Complementares WHERE exame_gatilho = ? AND exame_sugerido = ?", (id_gatilho, id_sugerido))
        if cursor.fetchone():
            self.lbl_msg_regra.configure(text="Esta regra já existe no sistema.", text_color=tema.LARANJA)
            conexao.close()
            return
            
        cursor.execute("INSERT INTO Regras_Complementares (exame_gatilho, exame_sugerido) VALUES (?, ?)", (id_gatilho, id_sugerido))
        conexao.commit()
        conexao.close()
        
        self.lbl_msg_regra.configure(text="Regra criada com sucesso! O alerta já está ativo nas consultas.", text_color=tema.VERDE)

if __name__ == "__main__":
    app = AppClinica()
    app.mainloop()
