# -*- coding: utf-8 -*-
"""Cadastro, estoque, custos e programação do Almoxarifado."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import db_service

FUSO = timezone(timedelta(hours=-3))
REFEICOES = (("desjejum","Desjejum"),("colacao","Lanche da manhã"),("almoco","Almoço"),
             ("lanche","Lanche da tarde"),("jantar","Jantar"),("ceia","Ceia"))
REFEICOES_LABEL = dict(REFEICOES)
CATEGORIAS = ("Gêneros alimentícios","Dietas enterais","Suplementos","Materiais","Limpeza","Outros")
DDL = """
CREATE TABLE IF NOT EXISTS Almox_Itens(
 id_item INTEGER PRIMARY KEY AUTOINCREMENT,nome TEXT NOT NULL,unidade TEXT NOT NULL,
 categoria TEXT NOT NULL DEFAULT 'Gêneros alimentícios',validade TEXT,valor_unitario REAL,estoque_minimo REAL,
 embalagem_qtd REAL,embalagem_un TEXT,
 ativo INTEGER NOT NULL DEFAULT 1,observacao TEXT,criado_em TEXT NOT NULL,atualizado_em TEXT NOT NULL,
 UNIQUE(nome COLLATE NOCASE,unidade COLLATE NOCASE));
CREATE TABLE IF NOT EXISTS Almox_Historico_Preco(
 id_preco INTEGER PRIMARY KEY AUTOINCREMENT,id_item INTEGER NOT NULL,valor_unitario REAL NOT NULL,
 origem TEXT NOT NULL,fonte TEXT,registrado_em TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_almox_preco_item ON Almox_Historico_Preco(id_item,registrado_em);
CREATE TABLE IF NOT EXISTS Almox_Movimentos(
 id_movimento INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT NOT NULL,hora TEXT NOT NULL,id_item INTEGER NOT NULL,
 operacao TEXT NOT NULL CHECK(operacao IN('entrada','saida')),
 motivo TEXT NOT NULL CHECK(motivo IN('compra','consumo','perda','ajuste','estorno')),
 quantidade REAL NOT NULL CHECK(quantidade>0),valor_unitario REAL NOT NULL CHECK(valor_unitario>=0),
 valor_total REAL NOT NULL CHECK(valor_total>=0),refeicao TEXT,observacao TEXT,usuario TEXT,
 origem TEXT NOT NULL DEFAULT 'manual',id_programacao INTEGER,id_linha_programacao INTEGER,
 id_estorno_de INTEGER UNIQUE,criado_em TEXT NOT NULL,UNIQUE(id_linha_programacao));
CREATE INDEX IF NOT EXISTS ix_almox_mov_data ON Almox_Movimentos(data,motivo,refeicao);
CREATE INDEX IF NOT EXISTS ix_almox_mov_item ON Almox_Movimentos(id_item,data);
CREATE TABLE IF NOT EXISTS Almox_Programacoes(
 id_programacao INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT NOT NULL,refeicao TEXT NOT NULL,
 porcoes REAL NOT NULL CHECK(porcoes>0),status TEXT NOT NULL DEFAULT 'rascunho',
 observacao TEXT,criado_em TEXT NOT NULL,atualizado_em TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_almox_prog_data ON Almox_Programacoes(data,refeicao,status);
CREATE TABLE IF NOT EXISTS Almox_Programacao_Itens(
 id_linha INTEGER PRIMARY KEY AUTOINCREMENT,id_programacao INTEGER NOT NULL,id_item INTEGER NOT NULL,
 quantidade_por_porcao REAL NOT NULL,quantidade_total REAL NOT NULL,valor_unitario REAL NOT NULL,
 valor_total REAL NOT NULL,origem TEXT NOT NULL DEFAULT 'manual',referencia_ficha TEXT,versao_ficha TEXT,observacao TEXT);
CREATE INDEX IF NOT EXISTS ix_almox_prog_item ON Almox_Programacao_Itens(id_programacao,id_item);
CREATE TRIGGER IF NOT EXISTS tr_almox_mov_nao_alterar BEFORE UPDATE ON Almox_Movimentos
 BEGIN SELECT RAISE(ABORT,'Movimento é histórico: registre ajuste ou estorno.'); END;
CREATE TRIGGER IF NOT EXISTS tr_almox_mov_nao_apagar BEFORE DELETE ON Almox_Movimentos
 BEGIN SELECT RAISE(ABORT,'Movimento não pode ser apagado; registre estorno.'); END;
CREATE TRIGGER IF NOT EXISTS tr_almox_preco_nao_alterar BEFORE UPDATE ON Almox_Historico_Preco
 BEGIN SELECT RAISE(ABORT,'Histórico de preço não pode ser alterado.'); END;
CREATE TRIGGER IF NOT EXISTS tr_almox_preco_nao_apagar BEFORE DELETE ON Almox_Historico_Preco
 BEGIN SELECT RAISE(ABORT,'Histórico de preço não pode ser apagado.'); END;
"""

def conectar(db):
 c=db_service.conectar(db); c.row_factory=sqlite3.Row; return c
def agora(): return datetime.now(FUSO).isoformat(timespec="seconds")
def hoje(): return datetime.now(FUSO).date().isoformat()
def _data(v):
 try:return date.fromisoformat(str(v)).isoformat()
 except (TypeError,ValueError):raise ValueError("Data inválida. Use AAAA-MM-DD.")
def _d(v,campo="valor",obrigatorio=False,minimo=None):
 if v in (None,""):
  if obrigatorio:raise ValueError(f"Informe {campo}.")
  return None
 s=str(v).strip().replace("R$","").replace("\u00a0","").replace(" ","")
 if "," in s and "." in s:s=s.replace(".","").replace(",",".")
 else:s=s.replace(",",".")
 try:x=Decimal(s)
 except (InvalidOperation,ValueError):raise ValueError(f"Valor inválido em {campo}.")
 if not x.is_finite() or (minimo is not None and x<Decimal(str(minimo))):
  adjetivo = "inválida" if campo.strip().lower().startswith("quantidade") else "inválido"
  raise ValueError(f"{campo.strip().lower()} {adjetivo}.")
 return x
def _f(x):return None if x is None else float(x)
def _ref(v,req=False):
 r=str(v or "").strip().lower()
 if not r and not req:return None
 if r not in REFEICOES_LABEL:raise ValueError("Selecione uma refeição válida.")
 return r
def inicializar(db):
 with closing(conectar(db)) as c:
  c.executescript(DDL)
  colunas={r[1] for r in c.execute("PRAGMA table_info(Almox_Itens)")}
  if "embalagem_qtd" not in colunas:c.execute("ALTER TABLE Almox_Itens ADD COLUMN embalagem_qtd REAL")
  if "embalagem_un" not in colunas:c.execute("ALTER TABLE Almox_Itens ADD COLUMN embalagem_un TEXT")
  if "validade" not in colunas:c.execute("ALTER TABLE Almox_Itens ADD COLUMN validade TEXT")
  c.commit()

def _saldo(c,iid):
 r=c.execute("SELECT COALESCE(SUM(CASE WHEN operacao='entrada' THEN quantidade ELSE -quantidade END),0) s FROM Almox_Movimentos WHERE id_item=?",(iid,)).fetchone()
 return float(r["s"] or 0)

def salvar_item(db,d):
 nome=str(d.get("nome") or "").strip();un=str(d.get("unidade") or "").strip()
 cat=str(d.get("categoria") or CATEGORIAS[0]).strip()
 if not nome:raise ValueError("Informe o nome do item.")
 if not un:raise ValueError("Informe a unidade padrão do item.")
 if cat not in CATEGORIAS:raise ValueError("Selecione uma categoria válida.")
 p=_d(d.get("valor_unitario"),"valor por unidade",minimo=0);mn=_d(d.get("estoque_minimo"),"estoque mínimo",minimo=0)
 embalagem_qtd=_d(d.get("embalagem_qtd"),"conteúdo da embalagem",minimo=Decimal("0.0000001"))
 embalagem_un=str(d.get("embalagem_un") or "").strip().lower() or None
 if (embalagem_qtd is None) != (embalagem_un is None):
  raise ValueError("Informe quantidade e unidade do conteúdo da embalagem.")
 if embalagem_qtd is not None and un.strip().lower() not in ("un","unidade","unidades"):
  raise ValueError("O conteúdo da embalagem só deve ser informado quando a unidade de estoque for un.")
 if embalagem_un not in (None,"g","kg","mg","ml","l"):
  raise ValueError("Unidade do conteúdo deve ser g, kg, mg, ml ou L.")
 now=agora()
 with closing(conectar(db)) as c:
  iid=d.get("id_item")
  try:
   if iid:
    old=c.execute("SELECT * FROM Almox_Itens WHERE id_item=?",(int(iid),)).fetchone()
    if not old:raise ValueError("Item não encontrado.")
    anterior=old["valor_unitario"]
    validade=str(d.get("validade") or "").strip() or None
    if validade is not None: validade=_data(validade)
    c.execute("UPDATE Almox_Itens SET nome=?,unidade=?,categoria=?,validade=?,valor_unitario=?,estoque_minimo=?,embalagem_qtd=?,embalagem_un=?,observacao=?,atualizado_em=? WHERE id_item=?",
      (nome,un,cat,validade,_f(p),_f(mn),_f(embalagem_qtd),embalagem_un,str(d.get("observacao") or "").strip(),now,int(iid)))
    iid=int(iid)
   else:
    validade=str(d.get("validade") or "").strip() or None
    if validade is not None: validade=_data(validade)
    cur=c.execute("INSERT INTO Almox_Itens(nome,unidade,categoria,validade,valor_unitario,estoque_minimo,embalagem_qtd,embalagem_un,observacao,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
      (nome,un,cat,validade,_f(p),_f(mn),_f(embalagem_qtd),embalagem_un,str(d.get("observacao") or "").strip(),now,now))
    iid=cur.lastrowid;anterior=None
  except sqlite3.IntegrityError as e:c.rollback();raise ValueError("Já existe um item com esse nome e unidade.") from e
  if p is not None and (anterior is None or round(float(anterior),8)!=float(p)):
   c.execute("INSERT INTO Almox_Historico_Preco(id_item,valor_unitario,origem,fonte,registrado_em) VALUES(?,?,?,?,?)",
             (iid,float(p),"cadastro",str(d.get("observacao") or "") or None,now))
  c.commit();return iid

def alterar_item_ativo(db,iid,ativo):
 with closing(conectar(db)) as c:c.execute("UPDATE Almox_Itens SET ativo=?,atualizado_em=? WHERE id_item=?",(1 if ativo else 0,agora(),int(iid)));c.commit()
def remover_item(db,iid):
 with closing(conectar(db)) as c:
  usado=any(c.execute(f"SELECT 1 FROM {t} WHERE id_item=? LIMIT 1",(int(iid),)).fetchone()
            for t in ("Almox_Movimentos","Almox_Programacao_Itens","Almox_Historico_Preco"))
  if usado:
   c.execute("UPDATE Almox_Itens SET ativo=0,atualizado_em=? WHERE id_item=?",(agora(),int(iid)));c.commit();return False
  c.execute("DELETE FROM Almox_Itens WHERE id_item=?",(int(iid),));c.commit();return True
def listar_itens(db,apenas_ativos=True,termo=None):
 sql="""SELECT i.*,(SELECT COALESCE(SUM(CASE WHEN operacao='entrada' THEN quantidade ELSE -quantidade END),0)
 FROM Almox_Movimentos m WHERE m.id_item=i.id_item) saldo FROM Almox_Itens i WHERE 1=1"""
 args=[]
 if apenas_ativos:sql+=" AND i.ativo=1"
 if termo:sql+=" AND i.nome LIKE ?";args.append("%"+str(termo).strip()+"%")
 sql+=" ORDER BY CASE WHEN i.validade IS NULL OR i.validade='' THEN 1 ELSE 0 END,i.validade,i.categoria,i.nome"
 with closing(conectar(db)) as c:return [dict(r) for r in c.execute(sql,args)]
def obter_item(db,iid):
 return next((x for x in listar_itens(db,False) if x["id_item"]==int(iid)),None)
def _insert_mov(c,dt,iid,operacao,motivo,qtd,preco,ref=None,obs="",usuario=None,origem="manual",pid=None,lid=None,estorno=None):
 total=(qtd*preco).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
 cur=c.execute("""INSERT INTO Almox_Movimentos(data,hora,id_item,operacao,motivo,quantidade,valor_unitario,valor_total,
 refeicao,observacao,usuario,origem,id_programacao,id_linha_programacao,id_estorno_de,criado_em)
 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
 (_data(dt),agora()[11:19],iid,operacao,motivo,float(qtd),float(preco),float(total),ref,obs,usuario,origem,pid,lid,estorno,agora()))
 return cur.lastrowid
def registrar_movimento(db,data,id_item,tipo,quantidade,valor_unitario=None,refeicao=None,observacao="",usuario=None,origem="manual"):
 if tipo not in ("entrada","consumo","perda","ajuste_entrada","ajuste_saida"):raise ValueError("Tipo de movimento inválido.")
 q=_d(quantidade,"quantidade",True,Decimal("0.0000001"));ref=_ref(refeicao,tipo=="consumo")
 with closing(conectar(db)) as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   item=c.execute("SELECT * FROM Almox_Itens WHERE id_item=? AND ativo=1",(int(id_item),)).fetchone()
   if not item:raise ValueError("Item não encontrado ou inativo.")
   op,mot=(("entrada","compra") if tipo=="entrada" else ("saida","consumo") if tipo=="consumo" else
           ("saida","perda") if tipo=="perda" else ("entrada","ajuste") if tipo=="ajuste_entrada" else ("saida","ajuste"))
   saldo=Decimal(str(_saldo(c,int(id_item))))
   if op=="saida" and q>saldo:raise ValueError(f"Saldo insuficiente de {item['nome']}: disponível {saldo} {item['unidade']}.")
   if tipo=="entrada":
    p=_d(valor_unitario,"valor unitário da compra",True,0);old=_d(item["valor_unitario"],"valor atual",minimo=0)
    media=((saldo*old)+(q*p))/(saldo+q) if saldo>0 and old is not None else p
    c.execute("UPDATE Almox_Itens SET valor_unitario=?,atualizado_em=? WHERE id_item=?",(float(media),agora(),int(id_item)))
    c.execute("INSERT INTO Almox_Historico_Preco(id_item,valor_unitario,origem,fonte,registrado_em) VALUES(?,?,?,?,?)",
      (int(id_item),float(media),"compra",observacao or "Compra/entrada",agora()))
   else:p=_d(valor_unitario or item["valor_unitario"],"valor unitário",True,0)
   mid=_insert_mov(c,data,int(id_item),op,mot,q,p,ref,observacao,usuario,origem)
   c.commit();return mid
  except Exception:c.rollback();raise
def estornar_movimento(db,id_movimento,*,data=None,usuario=None,justificativa=""):
 with closing(conectar(db)) as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   m=c.execute("SELECT * FROM Almox_Movimentos WHERE id_movimento=?",(int(id_movimento),)).fetchone()
   if not m:raise ValueError("Movimento não encontrado.")
   if m["id_estorno_de"] is not None or c.execute("SELECT 1 FROM Almox_Movimentos WHERE id_estorno_de=?",(int(id_movimento),)).fetchone():raise ValueError("Movimento já foi estornado.")
   tipo="ajuste_saida" if m["operacao"]=="entrada" else "ajuste_entrada"
   if tipo=="ajuste_saida" and Decimal(str(m["quantidade"]))>Decimal(str(_saldo(c,m["id_item"]))):raise ValueError("Saldo insuficiente para estornar esta entrada.")
   mid=_insert_mov(c,data or hoje(),m["id_item"],"saida" if m["operacao"]=="entrada" else "entrada","estorno",
      Decimal(str(m["quantidade"])),Decimal(str(m["valor_unitario"])),m["refeicao"],
      f"Estorno do movimento #{id_movimento}. {justificativa}".strip(),usuario,"estorno",estorno=int(id_movimento))
   c.commit();return mid
  except Exception:c.rollback();raise
def listar_movimentos(db,inicio=None,fim=None,id_item=None,limite=500):
 sql="SELECT m.*,i.nome AS item,i.unidade FROM Almox_Movimentos m JOIN Almox_Itens i ON i.id_item=m.id_item WHERE 1=1";args=[]
 if inicio:sql+=" AND m.data>=?";args.append(_data(inicio))
 if fim:sql+=" AND m.data<=?";args.append(_data(fim))
 if id_item:sql+=" AND m.id_item=?";args.append(int(id_item))
 sql+=" ORDER BY m.data DESC,m.hora DESC,m.id_movimento DESC LIMIT ?";args.append(int(limite))
 with closing(conectar(db)) as c:return [dict(x) for x in c.execute(sql,args)]
def historico_precos(db,iid):
 with closing(conectar(db)) as c:return [dict(x) for x in c.execute("SELECT * FROM Almox_Historico_Preco WHERE id_item=? ORDER BY registrado_em DESC,id_preco DESC",(int(iid),))]
def criar_programacao(db,data,refeicao,porcoes,observacao=""):
 q=_d(porcoes,"número de porções",True,Decimal("0.0000001"));now=agora()
 with closing(conectar(db)) as c:
  cur=c.execute("INSERT INTO Almox_Programacoes(data,refeicao,porcoes,status,observacao,criado_em,atualizado_em) VALUES(?,?,?,'rascunho',?,?,?)",
    (_data(data),_ref(refeicao,True),float(q),observacao,now,now));c.commit();return cur.lastrowid
def adicionar_item_programacao(db,pid,iid,quantidade_por_porcao,origem="manual",referencia_ficha=None,versao_ficha=None,observacao=""):
 q=_d(quantidade_por_porcao,"quantidade por porção",True,Decimal("0.0000001"))
 with closing(conectar(db)) as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   p=c.execute("SELECT * FROM Almox_Programacoes WHERE id_programacao=?",(int(pid),)).fetchone()
   i=c.execute("SELECT * FROM Almox_Itens WHERE id_item=? AND ativo=1",(int(iid),)).fetchone()
   if not p:raise ValueError("Programação não encontrada.")
   if p["status"]!="rascunho":raise ValueError("Somente programações em rascunho podem ser alteradas.")
   if not i:raise ValueError("Item não encontrado ou inativo.")
   preco=_d(i["valor_unitario"],"valor unitário do item",True,0);total=q*Decimal(str(p["porcoes"]))
   cost=(total*preco).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
   cur=c.execute("""INSERT INTO Almox_Programacao_Itens(id_programacao,id_item,quantidade_por_porcao,quantidade_total,
   valor_unitario,valor_total,origem,referencia_ficha,versao_ficha,observacao) VALUES(?,?,?,?,?,?,?,?,?,?)""",
   (int(pid),int(iid),float(q),float(total),float(preco),float(cost),origem,referencia_ficha,versao_ficha,observacao))
   c.execute("UPDATE Almox_Programacoes SET atualizado_em=? WHERE id_programacao=?",(agora(),int(pid)));c.commit();return cur.lastrowid
  except Exception:c.rollback();raise
def listar_programacoes(db,inicio=None,fim=None,status=None):
 sql="""SELECT p.*,COALESCE((SELECT SUM(valor_total) FROM Almox_Programacao_Itens i WHERE i.id_programacao=p.id_programacao),0) custo_estimado,
 (SELECT COUNT(*) FROM Almox_Programacao_Itens i WHERE i.id_programacao=p.id_programacao) itens FROM Almox_Programacoes p WHERE 1=1""";args=[]
 if inicio:sql+=" AND p.data>=?";args.append(_data(inicio))
 if fim:sql+=" AND p.data<=?";args.append(_data(fim))
 if status:sql+=" AND p.status=?";args.append(status)
 sql+=" ORDER BY p.data DESC,p.refeicao"
 with closing(conectar(db)) as c:return [dict(x) for x in c.execute(sql,args)]
def itens_programacao(db,pid):
 with closing(conectar(db)) as c:return [dict(x) for x in c.execute("""SELECT pi.*,i.nome AS item,i.unidade FROM Almox_Programacao_Itens pi
 JOIN Almox_Itens i ON i.id_item=pi.id_item WHERE pi.id_programacao=? ORDER BY i.nome""",(int(pid),))]
def remover_item_programacao(db,line):
 with closing(conectar(db)) as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   r=c.execute("SELECT id_programacao FROM Almox_Programacao_Itens WHERE id_linha=?",(int(line),)).fetchone()
   if not r:raise ValueError("Item da programação não encontrado.")
   p=c.execute("SELECT status FROM Almox_Programacoes WHERE id_programacao=?",(r[0],)).fetchone()
   if p[0]!="rascunho":raise ValueError("Só é possível remover itens de uma programação em rascunho.")
   c.execute("DELETE FROM Almox_Programacao_Itens WHERE id_linha=?",(int(line),));c.commit()
  except Exception:c.rollback();raise
def alterar_status_programacao(db,pid,status):
 if status not in ("confirmada","cancelada"):raise ValueError("Status inválido.")
 with closing(conectar(db)) as c:
  r=c.execute("SELECT status FROM Almox_Programacoes WHERE id_programacao=?",(int(pid),)).fetchone()
  if not r or r[0]!="rascunho":raise ValueError("Somente uma programação em rascunho pode ser confirmada ou cancelada.")
  c.execute("UPDATE Almox_Programacoes SET status=?,atualizado_em=? WHERE id_programacao=?",(status,agora(),int(pid)));c.commit()
def realizar_programacao(db,pid,usuario=None):
 with closing(conectar(db)) as c:
  c.execute("BEGIN IMMEDIATE")
  try:
   p=c.execute("SELECT * FROM Almox_Programacoes WHERE id_programacao=?",(int(pid),)).fetchone()
   if not p or p["status"]!="confirmada":raise ValueError("Confirme a programação antes de registrar sua realização.")
   lines=list(c.execute("SELECT * FROM Almox_Programacao_Itens WHERE id_programacao=? ORDER BY id_linha",(int(pid),)))
   if not lines:raise ValueError("Adicione itens antes de realizar a programação.")
   mids=[]
   for l in lines:
    if _saldo(c,l["id_item"])<l["quantidade_total"]:raise ValueError("Saldo insuficiente para realizar a programação.")
    mids.append(_insert_mov(c,p["data"],l["id_item"],"saida","consumo",Decimal(str(l["quantidade_total"])),
      Decimal(str(l["valor_unitario"])),p["refeicao"],f"Realização da programação #{pid}",usuario,"programacao",int(pid),int(l["id_linha"])))
   c.execute("UPDATE Almox_Programacoes SET status='realizada',atualizado_em=? WHERE id_programacao=?",(agora(),int(pid)));c.commit();return mids
  except Exception:c.rollback();raise
def resumo_periodo(db,inicio,fim):
 ini,end=_data(inicio),_data(fim)
 with closing(conectar(db)) as c:
  realref=[dict(r) for r in c.execute("""SELECT refeicao,ROUND(SUM(CASE WHEN operacao='saida' THEN valor_total ELSE -valor_total END),2) total
   FROM Almox_Movimentos WHERE data BETWEEN ? AND ? AND refeicao IS NOT NULL AND motivo IN('consumo','estorno') GROUP BY refeicao""",(ini,end))]
  realdia=[dict(r) for r in c.execute("""SELECT data,ROUND(SUM(CASE WHEN operacao='saida' THEN valor_total ELSE -valor_total END),2) total
   FROM Almox_Movimentos WHERE data BETWEEN ? AND ? AND refeicao IS NOT NULL AND motivo IN('consumo','estorno') GROUP BY data""",(ini,end))]
  real=c.execute("""SELECT ROUND(COALESCE(SUM(CASE WHEN operacao='saida' THEN valor_total ELSE -valor_total END),0),2)
   FROM Almox_Movimentos WHERE data BETWEEN ? AND ? AND refeicao IS NOT NULL AND motivo IN('consumo','estorno')""",(ini,end)).fetchone()[0] or 0
  pref=[dict(r) for r in c.execute("""SELECT p.refeicao,ROUND(SUM(i.valor_total),2) total FROM Almox_Programacoes p
   JOIN Almox_Programacao_Itens i ON i.id_programacao=p.id_programacao WHERE p.data BETWEEN ? AND ?
   AND p.status IN('rascunho','confirmada') GROUP BY p.refeicao""",(ini,end))]
  pdia=[dict(r) for r in c.execute("""SELECT p.data,ROUND(SUM(i.valor_total),2) total FROM Almox_Programacoes p
   JOIN Almox_Programacao_Itens i ON i.id_programacao=p.id_programacao WHERE p.data BETWEEN ? AND ?
   AND p.status IN('rascunho','confirmada') GROUP BY p.data""",(ini,end))]
  planned=c.execute("""SELECT ROUND(COALESCE(SUM(i.valor_total),0),2) FROM Almox_Programacoes p
   JOIN Almox_Programacao_Itens i ON i.id_programacao=p.id_programacao WHERE p.data BETWEEN ? AND ?
   AND p.status IN('rascunho','confirmada')""",(ini,end)).fetchone()[0] or 0
  loss=c.execute("""SELECT ROUND(COALESCE(SUM(CASE WHEN motivo='perda' AND operacao='saida' THEN valor_total
   WHEN motivo='estorno' AND id_estorno_de IN(SELECT id_movimento FROM Almox_Movimentos WHERE motivo='perda' AND operacao='saida')
   THEN -valor_total ELSE 0 END),0),2) FROM Almox_Movimentos WHERE data BETWEEN ? AND ?""",(ini,end)).fetchone()[0] or 0
 return {"inicio":ini,"fim":end,"realizado_total":float(real),"programado_total":float(planned),"perdas_total":float(loss),
  "realizado_refeicao":realref,"realizado_dia":realdia,"programado_refeicao":pref,"programado_dia":pdia}
def historico_precos(db,iid):
 with closing(conectar(db)) as c:return [dict(r) for r in c.execute("SELECT * FROM Almox_Historico_Preco WHERE id_item=? ORDER BY registrado_em DESC,id_preco DESC",(int(iid),))]
