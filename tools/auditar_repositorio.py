"""Auditoria de dados sensíveis e segredos em um repositório Git (Fase 0 — NutriLab).

Uso (na raiz do repositório, ANTES de qualquer push):
    python tools/auditar_repositorio.py [--raiz CAMINHO] [--ci] [--estrito] [--json arquivo.json]
                                        [--permitir GLOB ...] [--sem-historico]

O que examina:
  1. arquivos RASTREADOS pelo Git (git ls-files);
  2. arquivos NÃO rastreados e NÃO ignorados (iriam no próximo `git add -A`);
  3. HISTÓRICO: arquivos sensíveis que já passaram por algum commit, mesmo apagados depois;
  4. se o .gitignore realmente ignora os padrões obrigatórios (testado com `git check-ignore`).

Níveis:
  BLOQUEIO  banco SQLite/WAL, backup, anexos de pacientes, segredos/chaves, planilhas hospitalares originais,
            CPF válido no texto. Nunca pode ser liberado por lista de permissão.
  REVISAR   planilhas/PDF/DOC/ZIP quaisquer, e-mail, telefone, possível credencial. Pode ser liberado com
            `--permitir GLOB` ou em tools/auditoria_permitidos.txt (um glob por linha, '#' comenta).

PRIVACIDADE: o relatório mostra apenas caminho, número de linha, categoria e hash curto de commit.
Nenhum trecho de arquivo é impresso ou gravado.

Código de saída: 0 = sem BLOQUEIO; 1 = há BLOQUEIO (ou REVISAR com --estrito); 2 = erro de uso/ambiente.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

BLOQUEIO = "BLOQUEIO"
REVISAR = "REVISAR"

PLANILHAS_HOSPITAL = (
    "controle de refeicoes", "controle de fichas", "controle da nutricao",
    "mapa externo", "calculos estimativa", "evolucao nutricional pacientes",
)
EXT_PLANILHA_OU_PDF = (".xlsx", ".xlsm", ".xls", ".ods", ".pdf", ".csv")
EXT_DOCUMENTO = (".xlsx", ".xlsm", ".xls", ".ods", ".pdf", ".doc", ".docx", ".odt", ".zip", ".7z", ".rar")
EXT_SEGREDO = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")
NOMES_CHAVE_SSH = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
MODELOS_ENV = (".env.example", ".env.sample", ".env.template")
PASTAS_RAIZ_BLOQUEADAS = ("backups", "dados_locais", "exports", "exportacoes", "relatorios_gerados", "logs")
EXT_TEXTO = {".py", ".json", ".md", ".txt", ".csv", ".sql", ".bat", ".cmd", ".ps1", ".sh", ".yml", ".yaml",
             ".ini", ".cfg", ".toml", ".spec", ".html", ".htm", ".js", ".xml"}
TAMANHO_MAXIMO_TEXTO = 2 * 1024 * 1024
MAX_ACHADOS_POR_CATEGORIA_E_ARQUIVO = 5

# Caminhos sintéticos que o .gitignore DEVE ignorar (testados com `git check-ignore`; não dependem de existir).
SONDAS_GITIGNORE = (
    "clinica.db", "clinica.db-wal", "clinica.db-shm", "outro.sqlite3", "clinica.backup_20260101",
    "arquivos_pacientes/exemplo.pdf", "sub/arquivos_pacientes/exemplo.pdf", "backups/copia.db",
    ".env", ".env.local", "chave.pem",
    "CONTROLE DE REFEIÇÕES - Mes.xlsx", "CONTROLE DE FICHAS - Mes.xlsx", "Controle da Nutrição - Mes.xlsx",
    "Mapa_externo_novo_layout.xlsx", "Evolucao_nutricional_pacientes.pdf", "logs/compilacao_local.log",
)

RE_CPF = re.compile(r"(?<!\d)(\d{3})\.(\d{3})\.(\d{3})-(\d{2})(?!\d)")
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
RE_TELEFONE = re.compile(r"\(\d{2}\)\s?9?\d{4}-\d{4}")
RE_CHAVE_PRIVADA = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
RE_TOKEN_GITHUB = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")
RE_CHAVE_AWS = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
RE_SEGREDO_ATRIBUIDO = re.compile(
    r"""(?i)\b(password|passwd|senha|secret|token|api[_-]?key)\b\s*[:=]\s*['"]([^'"\s]{6,})['"]""")
RE_VALOR_PLACEHOLDER = re.compile(
    r"(?i)^(changeme|exemplo|example|xxx+|\*+|<.*>|senha|password|your[_-].*|teste|test.*|\$\{.*\}|%.*%)$")
DOMINIOS_EMAIL_PERMITIDOS = ("example.com", "example.org", "example.net", "anthropic.com", "users.noreply.github.com")


class ErroAuditoria(Exception):
    pass


@dataclass(frozen=True)
class Achado:
    nivel: str
    categoria: str
    caminho: str
    origem: str          # rastreado | nao-rastreado | historico | gitignore
    linha: int = 0       # 0 = não se aplica
    detalhe: str = ""    # rótulo fixo ou hash curto de commit — NUNCA conteúdo de arquivo


# ----------------------------------------------------------------------------- utilidades

def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _git(raiz, *args, check=True) -> str:
    try:
        r = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise ErroAuditoria("git não encontrado no PATH") from exc
    if check and r.returncode != 0:
        raise ErroAuditoria(f"git {' '.join(args[:2])} falhou: {r.stderr.strip()[:200]}")
    return r.stdout


def raiz_do_repositorio(inicio) -> Path:
    return Path(_git(inicio, "rev-parse", "--show-toplevel").strip())


def cpf_valido(digitos: str) -> bool:
    """Valida os dígitos verificadores de um CPF (11 dígitos)."""
    if len(digitos) != 11 or not digitos.isdigit() or digitos == digitos[0] * 11:
        return False

    def dv(base: str) -> int:
        soma = sum(int(d) * p for d, p in zip(base, range(len(base) + 1, 1, -1)))
        r = (soma * 10) % 11
        return 0 if r == 10 else r

    return dv(digitos[:9]) == int(digitos[9]) and dv(digitos[:10]) == int(digitos[10])


# ----------------------------------------------------------------------------- classificação por caminho

def classificar_caminho(caminho: str) -> list:
    """Retorna [(nivel, categoria)] para um caminho relativo (separador '/'). Não lê o arquivo."""
    achados = []
    partes = [p for p in caminho.replace("\\", "/").split("/") if p]
    if not partes:
        return achados
    norm = [_norm(p) for p in partes]
    base = norm[-1]
    base_espacos = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", base))
    ext = PurePosixPath(base).suffix

    if re.search(r"\.(db|sqlite|sqlite3|db3|s3db)(-[a-z0-9_]+)?$", base):
        achados.append((BLOQUEIO, "banco-sqlite"))
    if re.search(r"\.(backup|bak)(_[^/]*)?$", base) or ".backup_" in base:
        achados.append((BLOQUEIO, "backup"))
    if "arquivos_pacientes" in norm:
        achados.append((BLOQUEIO, "pasta-de-pacientes"))
    if len(norm) > 1 and norm[0] in PASTAS_RAIZ_BLOQUEADAS:
        achados.append((BLOQUEIO, "pasta-de-dados-locais"))
    if (base == ".env" or (base.startswith(".env.") and base not in MODELOS_ENV)
            or ext in EXT_SEGREDO or base in NOMES_CHAVE_SSH):
        achados.append((BLOQUEIO, "segredo"))
    if ext in EXT_PLANILHA_OU_PDF and any(p in base_espacos for p in PLANILHAS_HOSPITAL):
        achados.append((BLOQUEIO, "planilha-hospitalar"))
    elif ext in EXT_DOCUMENTO:
        achados.append((REVISAR, "documento-binario"))
    if re.match(r"^(credentials|secrets?|service[-_ ]account.*)\.json$", base):
        achados.append((REVISAR, "possivel-credencial"))
    return achados


# ----------------------------------------------------------------------------- varredura de conteúdo

def _email_permitido(email: str) -> bool:
    local, _, dominio = email.lower().rpartition("@")
    return dominio.endswith(DOMINIOS_EMAIL_PERMITIDOS) or local in ("noreply", "exemplo", "example")


def escanear_texto(texto: str) -> list:
    """Procura padrões de PII/segredo. Retorna [(nivel, categoria, linha)] — nunca o trecho encontrado."""
    achados, contagem = [], {}

    def registrar(nivel, categoria, numero):
        contagem[categoria] = contagem.get(categoria, 0) + 1
        if contagem[categoria] <= MAX_ACHADOS_POR_CATEGORIA_E_ARQUIVO:
            achados.append((nivel, categoria, numero))

    for numero, linha in enumerate(texto.splitlines(), start=1):
        for m in RE_CPF.finditer(linha):
            if cpf_valido("".join(m.groups())):
                registrar(BLOQUEIO, "cpf-valido", numero)
        if RE_CHAVE_PRIVADA.search(linha):
            registrar(BLOQUEIO, "chave-privada", numero)
        if RE_TOKEN_GITHUB.search(linha):
            registrar(BLOQUEIO, "token-github", numero)
        if RE_CHAVE_AWS.search(linha):
            registrar(BLOQUEIO, "chave-aws", numero)
        for m in RE_EMAIL.finditer(linha):
            if not _email_permitido(m.group(0)):
                registrar(REVISAR, "email", numero)
        if RE_TELEFONE.search(linha):
            registrar(REVISAR, "telefone", numero)
        for m in RE_SEGREDO_ATRIBUIDO.finditer(linha):
            if not RE_VALOR_PLACEHOLDER.match(m.group(2)):
                registrar(REVISAR, "segredo-atribuido", numero)
    return achados


def _ler_texto(caminho: Path):
    if caminho.suffix.lower() not in EXT_TEXTO:
        return None
    try:
        if not caminho.is_file() or caminho.stat().st_size > TAMANHO_MAXIMO_TEXTO:
            return None
        return caminho.read_bytes().decode("utf-8", errors="ignore")
    except OSError:
        return None


# ----------------------------------------------------------------------------- listas de permissão

def ler_permitidos(raiz: Path, extras=()) -> list:
    padroes = list(extras)
    arq = raiz / "tools" / "auditoria_permitidos.txt"
    if arq.is_file():
        for linha in arq.read_text(encoding="utf-8").splitlines():
            linha = linha.split("#", 1)[0].strip()
            if linha:
                padroes.append(linha)
    return padroes


def _permitido(caminho: str, padroes) -> bool:
    return any(fnmatch.fnmatch(caminho, p) for p in padroes)


# ----------------------------------------------------------------------------- auditoria

def _listar(raiz, *args) -> list:
    saida = _git(raiz, "-c", "core.quotepath=false", "ls-files", "-z", *args)
    return [p for p in saida.split("\0") if p]


def auditar_arquivos(raiz: Path, caminhos, origem: str, permitidos=()) -> list:
    achados = []
    for caminho in caminhos:
        for nivel, categoria in classificar_caminho(caminho):
            if nivel == REVISAR and _permitido(caminho, permitidos):
                continue
            achados.append(Achado(nivel, categoria, caminho, origem))
        texto_permitido = _permitido(caminho, permitidos)  # liberado: ignora só REVISAR; BLOQUEIO permanece
        texto = _ler_texto(raiz / caminho)
        if texto is None:
            continue
        for nivel, categoria, numero in escanear_texto(texto):
            if nivel == REVISAR and texto_permitido:
                continue
            achados.append(Achado(nivel, categoria, caminho, origem, linha=numero))
    return achados


def auditar_historico(raiz: Path, rastreados) -> list:
    """Arquivos de nível BLOQUEIO que já estiveram em algum commit e não estão mais na árvore atual."""
    r = subprocess.run(["git", "-C", str(raiz), "-c", "core.quotepath=false", "log", "--all", "--name-only",
                        "--diff-filter=AM", "--pretty=format:@@%h"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return []  # repositório sem commits
    atuais, vistos, commit, achados = set(rastreados), set(), "", []
    for linha in r.stdout.splitlines():
        if linha.startswith("@@"):
            commit = linha[2:]
            continue
        caminho = linha.strip()
        if not caminho or caminho in atuais:
            continue
        for nivel, categoria in classificar_caminho(caminho):
            if nivel == BLOQUEIO and (caminho, categoria) not in vistos:
                vistos.add((caminho, categoria))
                achados.append(Achado(BLOQUEIO, categoria, caminho, "historico", detalhe=f"commit {commit}"))
    return achados


def auditar_gitignore(raiz: Path) -> list:
    achados = []
    for sonda in SONDAS_GITIGNORE:
        r = subprocess.run(["git", "-C", str(raiz), "check-ignore", "--no-index", "-q", "--", sonda],
                           capture_output=True, text=True)
        if r.returncode == 1:
            achados.append(Achado(REVISAR, "gitignore-sem-padrao", sonda, "gitignore",
                                  detalhe="o .gitignore não ignora este caminho de teste"))
    return achados


def auditar(raiz, *, permitir=(), historico=True) -> list:
    raiz = raiz_do_repositorio(raiz)
    permitidos = ler_permitidos(raiz, permitir)
    rastreados = _listar(raiz)
    achados = auditar_arquivos(raiz, rastreados, "rastreado", permitidos)
    achados += auditar_arquivos(raiz, _listar(raiz, "--others", "--exclude-standard"), "nao-rastreado", permitidos)
    if historico:
        achados += auditar_historico(raiz, rastreados)
    achados += auditar_gitignore(raiz)
    return achados


# ----------------------------------------------------------------------------- relatório

def formatar_relatorio(achados) -> str:
    bloqueios = [a for a in achados if a.nivel == BLOQUEIO]
    revisar = [a for a in achados if a.nivel == REVISAR]
    linhas = ["NutriLab — auditoria de dados sensíveis (sem exibir conteúdo de arquivos)", ""]
    for titulo, grupo in (("BLOQUEIO", bloqueios), ("REVISAR", revisar)):
        for a in sorted(grupo, key=lambda x: (x.categoria, x.caminho, x.linha)):
            extra = f" linha {a.linha}" if a.linha else ""
            det = f" [{a.detalhe}]" if a.detalhe else ""
            linhas.append(f"[{titulo}] {a.categoria:<22} {a.caminho}{extra} ({a.origem}){det}")
    linhas.append("")
    linhas.append(f"Resumo: {len(bloqueios)} BLOQUEIO, {len(revisar)} REVISAR.")
    if bloqueios:
        linhas += [
            "",
            "Há BLOQUEIO: NÃO faça push. Retire do índice sem apagar o arquivo local:  git rm --cached -- <caminho>",
            "e confira o .gitignore. Achado de origem 'historico' (ou algo já enviado ao GitHub) exige tratar o histórico",
            "com o responsável pelo repositório/TI ANTES de qualquer novo push; o .gitignore não remove o que já foi versionado.",
        ]
    elif not revisar:
        linhas.append("Nenhum achado.")
    return "\n".join(linhas)



def _saida_tolerante() -> None:
    """Evita UnicodeEncodeError ao redirecionar a saída no Windows (páginas de código cp850/cp1252)."""
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar:
        reconfigurar(errors="replace")

def main(argv=None) -> int:
    _saida_tolerante()
    ap = argparse.ArgumentParser(description="Audita dados sensíveis e segredos em um repositório Git.")
    ap.add_argument("--raiz", default=".", help="pasta dentro do repositório (padrão: atual)")
    ap.add_argument("--ci", action="store_true", help="modo CI (mesmo critério de saída; mantido por clareza nos workflows)")
    ap.add_argument("--estrito", action="store_true", help="REVISAR também reprova (código 1)")
    ap.add_argument("--json", dest="json_saida", default=None, help="grava os achados (sem conteúdo) em JSON")
    ap.add_argument("--permitir", action="append", default=[], metavar="GLOB",
                    help="libera caminhos de nível REVISAR (repetível); BLOQUEIO nunca é liberável")
    ap.add_argument("--sem-historico", action="store_true", help="não examinar commits antigos")
    args = ap.parse_args(argv)
    try:
        achados = auditar(args.raiz, permitir=args.permitir, historico=not args.sem_historico)
    except ErroAuditoria as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    print(formatar_relatorio(achados))
    if args.json_saida:
        Path(args.json_saida).write_text(json.dumps([asdict(a) for a in achados], ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    if any(a.nivel == BLOQUEIO for a in achados):
        return 1
    if args.estrito and any(a.nivel == REVISAR for a in achados):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
