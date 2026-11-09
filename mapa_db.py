# -*- coding: utf-8 -*-
"""Banco de dados do Mapa Nutricional (SQLite, mesmo clinica.db do programa).

Sem dependência de interface gráfica. Todas as funções recebem o caminho do banco.
Datas são gravadas em ISO (AAAA-MM-DD); use iso_para_br/data_br_para_iso na interface.
"""
import calendar
import sqlite3
from contextlib import closing
from datetime import datetime, date

import nutri_calculos as nc

# ----------------------------------------------------------------- listas fixas
VIAS = ["Oral", "Enteral"]
CONSISTENCIAS = ["Livre", "Branda", "Pastosa", "Líq/Past", "Líquida"]
# (campo no banco, sigla impressa, nome completo)
CARACTERISTICAS = [
    ("dm", "DM", "Diabetes mellitus"),
    ("has", "HAS", "Hipertensão arterial"),
    ("laxativa", "Lax.", "Laxativa"),
    ("constipante", "Const.", "Constipante"),
    ("drc", "DRC", "Doença renal"),
]
MODULOS_PADRAO = [
    "Fórmula completa",
    "Fórmula para diabetes",
    "Módulo de proteínas",
    "Módulo de aminoácidos",
    "Módulo de carboidratos",
    "Módulo de lipídeos",
    "Módulo de fibras",
    "Módulo probiótico/simbiótico",
    "Módulo de vitaminas e minerais",
    "Espessante",
    "Outro",
]
NOTA_SEED = "Classificação inicial sugerida; confirmar com a ficha técnica."
SUPLEMENTOS_INICIAIS = [
    ("Fresubin", "Fórmula completa"),
    ("Thopic Soya 1,5 kcal/ml", "Fórmula completa"),
    ("Glutamina", "Módulo de aminoácidos"),
    ("Nutrison Energy", "Fórmula completa"),
    ("Simbioflora", "Módulo probiótico/simbiótico"),
    ("Diamax IG", "Fórmula para diabetes"),
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS Mapa_Config (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS Mapa_Setores (
    id_setor INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, ativo INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS Mapa_Leitos (
    id_leito INTEGER PRIMARY KEY AUTOINCREMENT, id_setor INTEGER NOT NULL, codigo TEXT NOT NULL,
    ordem INTEGER DEFAULT 0, ativo INTEGER DEFAULT 1, UNIQUE(id_setor, codigo));
CREATE TABLE IF NOT EXISTS Mapa_Modulos (
    id_modulo INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, ordem INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS Mapa_Suplementos (
    id_suplemento INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, modulo TEXT, preco REAL,
    emb_qtd REAL, emb_un TEXT DEFAULT 'ml', kcal_100 REAL, ptn_100 REAL, lip_100 REAL,
    carb_100 REAL, sod_100 REAL, observacao TEXT, ativo INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS Mapa_Registros (
    id_registro INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, id_leito INTEGER NOT NULL,
    id_paciente INTEGER, nome_paciente TEXT NOT NULL, acompanhante INTEGER DEFAULT 0,
    sexo TEXT, cor TEXT, idade_anos INTEGER, idade_meses INTEGER,
    aj_cm REAL, pp_cm REAL, pb_cm REAL,
    altura_cm REAL, altura_origem TEXT, altura_metodo TEXT,
    peso_kg REAL, peso_origem TEXT, peso_metodo TEXT,
    imc REAL, imc_class TEXT, data_reavaliacao TEXT, via TEXT,
    dm INTEGER DEFAULT 0, has INTEGER DEFAULT 0, laxativa INTEGER DEFAULT 0,
    constipante INTEGER DEFAULT 0, drc INTEGER DEFAULT 0, consistencia TEXT,
    obs_sim TEXT, obs_nao TEXT, fi_estado TEXT, fi_freq REAL, fi_dias_ausente INTEGER,
    criado_em TEXT, atualizado_em TEXT, UNIQUE(data, id_leito));
CREATE TABLE IF NOT EXISTS Mapa_Registro_Suplementos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, id_registro INTEGER NOT NULL, id_suplemento INTEGER,
    nome TEXT NOT NULL, modulo TEXT, qtd_dia REAL, unidade TEXT);
CREATE INDEX IF NOT EXISTS ix_mapa_reg_data ON Mapa_Registros(data);
CREATE INDEX IF NOT EXISTS ix_mapa_reg_pac ON Mapa_Registros(id_paciente);
CREATE INDEX IF NOT EXISTS ix_mapa_regsup_reg ON Mapa_Registro_Suplementos(id_registro);
"""

_CAMPOS_REG = [
    "id_paciente", "nome_paciente", "acompanhante", "sexo", "cor", "idade_anos", "idade_meses",
    "aj_cm", "pp_cm", "pb_cm", "altura_cm", "altura_origem", "altura_metodo",
    "peso_kg", "peso_origem", "peso_metodo", "imc", "imc_class", "data_reavaliacao", "via",
    "dm", "has", "laxativa", "constipante", "drc", "consistencia", "obs_sim", "obs_nao",
    "fi_estado", "fi_freq", "fi_dias_ausente",
]

# --------------------------------------------------------------------- utilidades


def conectar(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def data_br_para_iso(txt):
    """'25/10/2026' -> '2026-10-25'. Vazio -> None. Inválido -> ValueError."""
    if txt is None or not str(txt).strip():
        return None
    return datetime.strptime(str(txt).strip(), "%d/%m/%Y").date().isoformat()


def iso_para_br(iso):
    if not iso:
        return ""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


# --------------------------------------------------------------------- inicialização


def inicializar(db_path):
    """Cria as tabelas do Mapa (se faltarem) e semeia setor, módulos e suplementos iniciais."""
    with closing(conectar(db_path)) as c:
        c.executescript(_SCHEMA)
        # Pacientes pertence ao programa principal; garante existência em bancos novos.
        c.execute("""CREATE TABLE IF NOT EXISTS Pacientes (
            id_paciente INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            data_nascimento TEXT, sexo TEXT)""")
        if c.execute("SELECT COUNT(*) FROM Mapa_Setores").fetchone()[0] == 0:
            c.execute("INSERT INTO Mapa_Setores (nome) VALUES (?)", ("Setor geral",))
        if c.execute("SELECT COUNT(*) FROM Mapa_Modulos").fetchone()[0] == 0:
            for i, nome in enumerate(MODULOS_PADRAO):
                c.execute("INSERT INTO Mapa_Modulos (nome, ordem) VALUES (?, ?)", (nome, i))
        ja = c.execute("SELECT valor FROM Mapa_Config WHERE chave='seed_suplementos'").fetchone()
        if not ja:
            if c.execute("SELECT COUNT(*) FROM Mapa_Suplementos").fetchone()[0] == 0:
                for nome, modulo in SUPLEMENTOS_INICIAIS:
                    c.execute(
                        "INSERT INTO Mapa_Suplementos (nome, modulo, observacao) VALUES (?, ?, ?)",
                        (nome, modulo, NOTA_SEED))
            c.execute("INSERT INTO Mapa_Config (chave, valor) VALUES ('seed_suplementos', '1')")
        c.commit()


def obter_config(db_path, chave, padrao=None):
    with closing(conectar(db_path)) as c:
        r = c.execute("SELECT valor FROM Mapa_Config WHERE chave=?", (chave,)).fetchone()
    return r["valor"] if r else padrao


def salvar_config(db_path, chave, valor):
    with closing(conectar(db_path)) as c:
        c.execute("INSERT INTO Mapa_Config (chave, valor) VALUES (?, ?) "
                  "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, str(valor)))
        c.commit()


# ------------------------------------------------------------------ setores e leitos


def listar_setores(db_path, apenas_ativos=True):
    with closing(conectar(db_path)) as c:
        q = "SELECT * FROM Mapa_Setores" + (" WHERE ativo=1" if apenas_ativos else "") + " ORDER BY nome"
        return _rows(c.execute(q))


def criar_setor(db_path, nome):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome do setor.")
    with closing(conectar(db_path)) as c:
        try:
            cur = c.execute("INSERT INTO Mapa_Setores (nome) VALUES (?)", (nome,))
        except sqlite3.IntegrityError:
            raise ValueError("Já existe um setor com esse nome.")
        c.commit()
        return cur.lastrowid


def listar_leitos(db_path, id_setor=None, apenas_ativos=True):
    sql = ("SELECT L.*, S.nome AS setor FROM Mapa_Leitos L JOIN Mapa_Setores S "
           "ON S.id_setor = L.id_setor WHERE 1=1")
    par = []
    if id_setor:
        sql += " AND L.id_setor=?"
        par.append(id_setor)
    if apenas_ativos:
        sql += " AND L.ativo=1"
    sql += " ORDER BY S.nome, L.ordem, L.codigo"
    with closing(conectar(db_path)) as c:
        return _rows(c.execute(sql, par))


def criar_leito(db_path, id_setor, codigo):
    codigo = (codigo or "").strip()
    if not codigo:
        raise ValueError("Informe o código do leito.")
    with closing(conectar(db_path)) as c:
        ordem = c.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM Mapa_Leitos WHERE id_setor=?",
                          (id_setor,)).fetchone()[0]
        try:
            cur = c.execute("INSERT INTO Mapa_Leitos (id_setor, codigo, ordem) VALUES (?, ?, ?)",
                            (id_setor, codigo, ordem))
        except sqlite3.IntegrityError:
            raise ValueError(f"O leito '{codigo}' já existe neste setor.")
        c.commit()
        return cur.lastrowid


def criar_leitos_sequencia(db_path, id_setor, prefixo, inicio, fim, largura=2):
    """Cria leitos prefixo+número (ex.: 'L', 1..10 -> L01..L10). Devolve quantos foram criados."""
    if fim < inicio or fim - inicio > 500:
        raise ValueError("Intervalo inválido (máximo de 500 leitos por vez).")
    criados = 0
    for n in range(inicio, fim + 1):
        try:
            criar_leito(db_path, id_setor, f"{prefixo}{str(n).zfill(largura)}")
            criados += 1
        except ValueError:
            pass  # já existia
    return criados


def alterar_leito_ativo(db_path, id_leito, ativo):
    with closing(conectar(db_path)) as c:
        c.execute("UPDATE Mapa_Leitos SET ativo=? WHERE id_leito=?", (1 if ativo else 0, id_leito))
        c.commit()


def remover_leito(db_path, id_leito):
    """Remove o leito se nunca foi usado; senão apenas desativa. Retorna True se removeu."""
    with closing(conectar(db_path)) as c:
        usado = c.execute("SELECT COUNT(*) FROM Mapa_Registros WHERE id_leito=?", (id_leito,)).fetchone()[0]
        if usado:
            c.execute("UPDATE Mapa_Leitos SET ativo=0 WHERE id_leito=?", (id_leito,))
            c.commit()
            return False
        c.execute("DELETE FROM Mapa_Leitos WHERE id_leito=?", (id_leito,))
        c.commit()
        return True


# ------------------------------------------------------------- módulos e suplementos


def listar_modulos(db_path):
    with closing(conectar(db_path)) as c:
        return [r["nome"] for r in c.execute("SELECT nome FROM Mapa_Modulos ORDER BY ordem, nome")]


def garantir_modulo(db_path, nome):
    nome = (nome or "").strip()
    if not nome:
        return
    with closing(conectar(db_path)) as c:
        if not c.execute("SELECT 1 FROM Mapa_Modulos WHERE nome=?", (nome,)).fetchone():
            ordem = c.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM Mapa_Modulos").fetchone()[0]
            c.execute("INSERT INTO Mapa_Modulos (nome, ordem) VALUES (?, ?)", (nome, ordem))
            c.commit()


def listar_suplementos(db_path, apenas_ativos=True, modulo=None):
    sql = "SELECT * FROM Mapa_Suplementos WHERE 1=1"
    par = []
    if apenas_ativos:
        sql += " AND ativo=1"
    if modulo:
        sql += " AND modulo=?"
        par.append(modulo)
    sql += " ORDER BY COALESCE(modulo, ''), nome"
    with closing(conectar(db_path)) as c:
        return _rows(c.execute(sql, par))


_NUM_SUP = ["preco", "emb_qtd", "kcal_100", "ptn_100", "lip_100", "carb_100", "sod_100"]


def salvar_suplemento(db_path, d):
    """Insere (sem id_suplemento) ou atualiza. Números aceitam vírgula. Retorna o id."""
    nome = (d.get("nome") or "").strip()
    if not nome:
        raise ValueError("Informe o nome do suplemento.")
    modulo = (d.get("modulo") or "").strip() or "Outro"
    valores = {}
    for k in _NUM_SUP:
        txt = d.get(k)
        v = nc.parse_num(txt)
        if txt not in (None, "") and v is None:
            raise ValueError(f"Valor inválido em '{k}'.")
        if v is not None and v < 0:
            raise ValueError(f"'{k}' não pode ser negativo.")
        valores[k] = v
    un = (d.get("emb_un") or "ml").strip().lower()
    if un not in ("ml", "g"):
        raise ValueError("A unidade da embalagem deve ser ml ou g.")
    garantir_modulo(db_path, modulo)
    with closing(conectar(db_path)) as c:
        base = (nome, modulo, valores["preco"], valores["emb_qtd"], un, valores["kcal_100"],
                valores["ptn_100"], valores["lip_100"], valores["carb_100"], valores["sod_100"],
                (d.get("observacao") or "").strip())
        if d.get("id_suplemento"):
            c.execute("""UPDATE Mapa_Suplementos SET nome=?, modulo=?, preco=?, emb_qtd=?, emb_un=?,
                         kcal_100=?, ptn_100=?, lip_100=?, carb_100=?, sod_100=?, observacao=?
                         WHERE id_suplemento=?""", base + (d["id_suplemento"],))
            novo = d["id_suplemento"]
        else:
            cur = c.execute("""INSERT INTO Mapa_Suplementos (nome, modulo, preco, emb_qtd, emb_un, kcal_100,
                               ptn_100, lip_100, carb_100, sod_100, observacao) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                            base)
            novo = cur.lastrowid
        c.commit()
        return novo


def alterar_suplemento_ativo(db_path, id_suplemento, ativo):
    with closing(conectar(db_path)) as c:
        c.execute("UPDATE Mapa_Suplementos SET ativo=? WHERE id_suplemento=?",
                  (1 if ativo else 0, id_suplemento))
        c.commit()


def remover_suplemento(db_path, id_suplemento):
    """Exclui se nunca foi usado; senão apenas desativa (preserva o histórico). True se excluiu."""
    with closing(conectar(db_path)) as c:
        usado = c.execute("SELECT COUNT(*) FROM Mapa_Registro_Suplementos WHERE id_suplemento=?",
                          (id_suplemento,)).fetchone()[0]
        if usado:
            c.execute("UPDATE Mapa_Suplementos SET ativo=0 WHERE id_suplemento=?", (id_suplemento,))
            c.commit()
            return False
        c.execute("DELETE FROM Mapa_Suplementos WHERE id_suplemento=?", (id_suplemento,))
        c.commit()
        return True


# ------------------------------------------------------------------- registros


def completar_registro(reg, criterio_idoso="lipschitz", lms=None):
    """Calcula IMC e classificação do registro (altera e devolve o dict)."""
    imc = nc.calcular_imc(reg.get("peso_kg"), reg.get("altura_cm"))
    reg["imc"] = round(imc, 1) if imc is not None else None
    if imc is None or reg.get("idade_anos") is None:
        reg["imc_class"] = ""
    else:
        cl = nc.classificar_imc(imc, reg["idade_anos"], reg.get("sexo"), reg.get("idade_meses") or 0,
                                criterio_idoso, lms)
        reg["imc_class"] = nc.texto_classificacao(cl)
    return reg


def validar_registro(reg):
    """Lista de mensagens de erro (vazia = ok)."""
    erros = []
    if not (reg.get("nome_paciente") or "").strip():
        erros.append("Informe o nome do paciente.")
    if not reg.get("id_leito"):
        erros.append("Leito não definido.")
    limites = [("idade_anos", "Idade", 0, 120), ("aj_cm", "AJ", 20, 90), ("pp_cm", "PP", 10, 80),
               ("pb_cm", "PB", 5, 80), ("altura_cm", "Altura", 30, 250), ("peso_kg", "Peso", 1, 400)]
    for campo, rot, lo, hi in limites:
        v = reg.get(campo)
        if v is not None and not lo <= v <= hi:
            erros.append(f"{rot} fora do intervalo plausível ({lo} a {hi}).")
    for campo, rot in (("altura_origem", "a altura"), ("peso_origem", "o peso")):
        if reg.get(campo) not in (None, "", "E", "R"):
            erros.append(f"Origem inválida para {rot}.")
    if reg.get("via") not in (None, "") + tuple(VIAS):
        erros.append("Via de administração inválida.")
    if reg.get("consistencia") not in (None, "") + tuple(CONSISTENCIAS):
        erros.append("Consistência inválida.")
    if reg.get("fi_estado") == "A" and reg.get("fi_dias_ausente") is not None and reg["fi_dias_ausente"] < 0:
        erros.append("Dias de ausência da função intestinal inválidos.")
    return erros


def _paciente_do_registro(c, reg):
    """Garante um paciente em Pacientes e devolve o id (não vincula por nome automaticamente)."""
    if reg.get("id_paciente"):
        return reg["id_paciente"]
    sexo = {"H": "Masculino", "M": "Feminino"}.get(reg.get("sexo"), "")
    cur = c.execute("INSERT INTO Pacientes (nome, data_nascimento, sexo) VALUES (?, ?, ?)",
                    (reg["nome_paciente"].strip(), "", sexo))
    return cur.lastrowid


def salvar_registro(db_path, reg, criterio_idoso="lipschitz", lms=None):
    """Grava (ou atualiza) o registro de um leito num dia. `reg` precisa de data (ISO) e id_leito.
    Retorna o id_registro."""
    if not reg.get("data"):
        raise ValueError("Data do registro ausente.")
    reg = dict(reg)
    completar_registro(reg, criterio_idoso, lms)
    erros = validar_registro(reg)
    if erros:
        raise ValueError("\n".join(erros))
    with closing(conectar(db_path)) as c:
        existente = c.execute("SELECT id_registro, id_paciente, nome_paciente FROM Mapa_Registros "
                              "WHERE data=? AND id_leito=?", (reg["data"], reg["id_leito"])).fetchone()
        # Regravar o mesmo leito/dia com o mesmo nome mantém o paciente (não cria duplicata).
        if (not reg.get("id_paciente") and existente and existente["id_paciente"]
                and (existente["nome_paciente"] or "").strip().lower() == reg["nome_paciente"].strip().lower()):
            reg["id_paciente"] = existente["id_paciente"]
        reg["id_paciente"] = _paciente_do_registro(c, reg)
        valores = [reg.get(k) for k in _CAMPOS_REG]
        if existente:
            id_reg = existente["id_registro"]
            sets = ", ".join(f"{k}=?" for k in _CAMPOS_REG)
            c.execute(f"UPDATE Mapa_Registros SET {sets}, atualizado_em=? WHERE id_registro=?",
                      valores + [_agora(), id_reg])
        else:
            cols = ", ".join(["data", "id_leito"] + _CAMPOS_REG + ["criado_em", "atualizado_em"])
            marc = ", ".join("?" * (2 + len(_CAMPOS_REG) + 2))
            cur = c.execute(f"INSERT INTO Mapa_Registros ({cols}) VALUES ({marc})",
                            [reg["data"], reg["id_leito"]] + valores + [_agora(), _agora()])
            id_reg = cur.lastrowid
        c.execute("DELETE FROM Mapa_Registro_Suplementos WHERE id_registro=?", (id_reg,))
        for s in reg.get("suplementos") or []:
            c.execute("""INSERT INTO Mapa_Registro_Suplementos
                         (id_registro, id_suplemento, nome, modulo, qtd_dia, unidade) VALUES (?,?,?,?,?,?)""",
                      (id_reg, s.get("id_suplemento"), s["nome"], s.get("modulo"), s.get("qtd_dia"),
                       s.get("unidade")))
        c.commit()
        return id_reg


def _anexar_suplementos(c, registros):
    if not registros:
        return registros
    ids = [r["id_registro"] for r in registros]
    por_reg = {i: [] for i in ids}
    marcas = ",".join("?" * len(ids))
    for s in c.execute(f"SELECT * FROM Mapa_Registro_Suplementos WHERE id_registro IN ({marcas}) ORDER BY id", ids):
        por_reg[s["id_registro"]].append(dict(s))
    for r in registros:
        r["suplementos"] = por_reg[r["id_registro"]]
    return registros


_SEL_REG = ("SELECT R.*, L.codigo AS leito_codigo, L.id_setor AS id_setor, S.nome AS setor "
            "FROM Mapa_Registros R JOIN Mapa_Leitos L ON L.id_leito = R.id_leito "
            "JOIN Mapa_Setores S ON S.id_setor = L.id_setor ")


def obter_registro(db_path, data_iso, id_leito):
    with closing(conectar(db_path)) as c:
        rows = _rows(c.execute(_SEL_REG + "WHERE R.data=? AND R.id_leito=?", (data_iso, id_leito)))
        return _anexar_suplementos(c, rows)[0] if rows else None


def remover_registro(db_path, id_registro):
    with closing(conectar(db_path)) as c:
        c.execute("DELETE FROM Mapa_Registro_Suplementos WHERE id_registro=?", (id_registro,))
        c.execute("DELETE FROM Mapa_Registros WHERE id_registro=?", (id_registro,))
        c.commit()


def mapa_do_dia(db_path, data_iso, id_setor=None):
    """Lista [{'leito': {...}, 'registro': dict|None}] na ordem dos leitos do setor.
    Inclui leitos desativados que tenham registro nesse dia."""
    with closing(conectar(db_path)) as c:
        par = [data_iso]
        filtro = ""
        if id_setor:
            filtro = " AND L.id_setor=?"
            par.append(id_setor)
        regs = _rows(c.execute(_SEL_REG + "WHERE R.data=?" + filtro, par))
        _anexar_suplementos(c, regs)
        por_leito = {r["id_leito"]: r for r in regs}
        q = ("SELECT L.*, S.nome AS setor FROM Mapa_Leitos L JOIN Mapa_Setores S ON S.id_setor = L.id_setor "
             "WHERE (L.ativo=1 OR L.id_leito IN (%s))" % ",".join(str(i) for i in por_leito) if por_leito else
             "SELECT L.*, S.nome AS setor FROM Mapa_Leitos L JOIN Mapa_Setores S ON S.id_setor = L.id_setor "
             "WHERE L.ativo=1")
        par2 = []
        if id_setor:
            q += " AND L.id_setor=?"
            par2.append(id_setor)
        q += " ORDER BY S.nome, L.ordem, L.codigo"
        leitos = _rows(c.execute(q, par2))
    return [{"leito": l, "registro": por_leito.get(l["id_leito"])} for l in leitos]


def ultima_data_com_registros(db_path, antes_de_iso=None, id_setor=None):
    sql = "SELECT MAX(R.data) AS d FROM Mapa_Registros R JOIN Mapa_Leitos L ON L.id_leito = R.id_leito WHERE 1=1"
    par = []
    if antes_de_iso:
        sql += " AND R.data < ?"
        par.append(antes_de_iso)
    if id_setor:
        sql += " AND L.id_setor = ?"
        par.append(id_setor)
    with closing(conectar(db_path)) as c:
        r = c.execute(sql, par).fetchone()
    return r["d"] if r and r["d"] else None


def copiar_mapa(db_path, origem_iso, destino_iso, id_setor=None):
    """Copia os registros de `origem` para `destino` nos leitos que ainda não têm registro
    no destino. Mantém o vínculo do paciente. Retorna quantos foram copiados."""
    copiados = 0
    with closing(conectar(db_path)) as c:
        par = [origem_iso]
        filtro = ""
        if id_setor:
            filtro = " AND L.id_setor=?"
            par.append(id_setor)
        regs = _rows(c.execute(_SEL_REG + "WHERE R.data=?" + filtro, par))
        _anexar_suplementos(c, regs)
        for r in regs:
            if c.execute("SELECT 1 FROM Mapa_Registros WHERE data=? AND id_leito=?",
                         (destino_iso, r["id_leito"])).fetchone():
                continue
            cols = ", ".join(["data", "id_leito"] + _CAMPOS_REG + ["criado_em", "atualizado_em"])
            marc = ", ".join("?" * (2 + len(_CAMPOS_REG) + 2))
            cur = c.execute(f"INSERT INTO Mapa_Registros ({cols}) VALUES ({marc})",
                            [destino_iso, r["id_leito"]] + [r.get(k) for k in _CAMPOS_REG] + [_agora(), _agora()])
            for s in r["suplementos"]:
                c.execute("""INSERT INTO Mapa_Registro_Suplementos
                             (id_registro, id_suplemento, nome, modulo, qtd_dia, unidade) VALUES (?,?,?,?,?,?)""",
                          (cur.lastrowid, s["id_suplemento"], s["nome"], s["modulo"], s["qtd_dia"], s["unidade"]))
            copiados += 1
        c.commit()
    return copiados


def historico_paciente(db_path, id_paciente=None, nome=None):
    """Registros do paciente (mais recentes primeiro). Sem id, procura pelo nome exato."""
    with closing(conectar(db_path)) as c:
        if id_paciente:
            rows = _rows(c.execute(_SEL_REG + "WHERE R.id_paciente=? ORDER BY R.data DESC", (id_paciente,)))
        else:
            rows = _rows(c.execute(_SEL_REG + "WHERE LOWER(R.nome_paciente)=LOWER(?) ORDER BY R.data DESC",
                                   ((nome or "").strip(),)))
        return _anexar_suplementos(c, rows)


def registros_do_mes(db_path, ano, mes, id_setor=None):
    ini = date(ano, mes, 1).isoformat()
    fim = date(ano + (mes == 12), 1 if mes == 12 else mes + 1, 1).isoformat()
    par = [ini, fim]
    filtro = ""
    if id_setor:
        filtro = " AND L.id_setor=?"
        par.append(id_setor)
    with closing(conectar(db_path)) as c:
        rows = _rows(c.execute(_SEL_REG + "WHERE R.data >= ? AND R.data < ?" + filtro + " ORDER BY R.data", par))
        return _anexar_suplementos(c, rows)


def meses_com_dados(db_path):
    """[(ano, mes)] com registros, do mais recente ao mais antigo."""
    with closing(conectar(db_path)) as c:
        rows = c.execute("SELECT DISTINCT substr(data, 1, 7) AS ym FROM Mapa_Registros ORDER BY ym DESC").fetchall()
    return [(int(r["ym"][:4]), int(r["ym"][5:7])) for r in rows]


def listar_pacientes(db_path, filtro=""):
    with closing(conectar(db_path)) as c:
        like = f"%{filtro.strip()}%"
        return _rows(c.execute(
            "SELECT id_paciente, nome, data_nascimento, sexo FROM Pacientes "
            "WHERE nome LIKE ? ORDER BY nome LIMIT 300", (like,)))


def dias_do_mes(ano, mes):
    return calendar.monthrange(ano, mes)[1]
