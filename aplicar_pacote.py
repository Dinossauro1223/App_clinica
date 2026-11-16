"""Aplica o pacote (arquivo .bundle) ao repositório App_clinica e publica os branches novos.

Uso normal: dê dois cliques em Aplicar_Pacote_App_clinica.bat (ele chama este script).
Opções:  --sem-push          só prepara e testa, não publica
         --repo URL_OU_CAMINHO   (padrão: https://github.com/Dinossauro1223/App_clinica.git)
         --pasta-trabalho PASTA  (padrão: pasta temporária)
         --bundle ARQUIVO        (padrão: o .bundle mais recente ao lado deste script)

O pacote traz um ou mais branches INDEPENDENTES (cada um criado a partir do branch padrão do repositório).
Ordem das etapas — para na primeira falha e NÃO publica o que ainda não foi publicado:
  1. confere o git e a identidade (user.name / user.email);
  2. clona o repositório numa pasta temporária (o Git pede o login do GitHub, se precisar);
  3. confere que NENHUM dos branches do pacote já existe no GitHub (para não publicar só metade);
  4. para cada branch: cria-o a partir do branch padrão e aplica, um a um, os commits do pacote (mensagens preservadas);
     (branches "docs/instalar-*" são aplicados por SOBREPOSIÇÃO: README, ROADMAP, CLAUDE.md etc. são substituídos pelos
     do pacote; .gitignore e INSTRUCOES_DE_INSTALACAO.md nunca são tocados; se já forem idênticos, nada é publicado);
     se um commit que EDITA arquivos existentes (README/ROADMAP/diário) conflitar, aplica só os arquivos novos dele e
     guarda as edições num arquivo .patch ao lado deste script;
  5. audita o resultado (tools/auditar_repositorio.py, se existir no branch): BLOQUEIO na árvore => NÃO publica;
  6. roda os testes que o próprio pacote trouxe: se falharem, NÃO publica e guarda o resultado em resultado_testes_*.txt;
  7. publica SOMENTE o branch novo (git push; nunca force; nunca a main).
Tudo o que aparece na tela também é gravado em aplicar_pacote_log.txt.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_PADRAO = "https://github.com/Dinossauro1223/App_clinica.git"
AQUI = Path(__file__).resolve().parent
LOG = []
PATCHES = []
PUBLICADOS = []
# Branches cujo nome começa com este prefixo são aplicados por SOBREPOSIÇÃO: os arquivos da árvore do branch substituem
# (ou são adicionados a) os do repositório, em vez de cherry-pick. Usado para instalar o pacote de documentação.
PREFIXO_SOBREPOSICAO = "docs/instalar-"
EXCLUIR_SOBREPOSICAO = {".gitignore", "INSTRUCOES_DE_INSTALACAO.md"}


class Falha(Exception):
    pass


def dizer(msg=""):
    print(msg)
    LOG.append(str(msg))


def executar(cmd, cwd=None, capturar=True, entrada=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=capturar, text=True, encoding="utf-8", errors="replace",
                          input=entrada)


def git(*args, cwd=None, check=True, bruto=False, entrada=None):
    r = executar(["git", *args], cwd=cwd, entrada=entrada)
    if check and r.returncode != 0:
        raise Falha(f"git {' '.join(args[:3])} falhou:\n{(r.stderr or r.stdout).strip()}")
    return r.stdout if bruto else r.stdout.strip()


def localizar_bundle(arg):
    if arg:
        p = Path(arg)
        if not p.is_file():
            raise Falha(f"bundle não encontrado: {p}")
        return p
    achados = sorted(AQUI.glob("*.bundle"), key=lambda x: x.stat().st_mtime)
    if not achados:
        raise Falha(f"nenhum arquivo .bundle ao lado de {Path(__file__).name} (pasta {AQUI})")
    if len(achados) > 1:
        dizer(f"Aviso: há {len(achados)} arquivos .bundle; usando o mais recente: {achados[-1].name}")
    return achados[-1]


def conferir_git_e_identidade():
    try:
        versao = git("--version")
    except FileNotFoundError:
        raise Falha("o git não foi encontrado. Instale o Git for Windows e tente de novo.")
    dizer(f"[1] {versao}")
    nome, email = git("config", "user.name", check=False), git("config", "user.email", check=False)
    if not nome or not email:
        raise Falha('o git não sabe quem é você. Rode uma vez:\n  git config --global user.name "Seu Nome"\n'
                    '  git config --global user.email "seu-email@exemplo.com"')


def itens_do_commit(clone, sha):
    saida = git("diff-tree", "--no-commit-id", "--name-status", "-r", "-z", sha, cwd=clone, bruto=True)
    partes = [p for p in saida.split("\0") if p]
    return list(zip(partes[0::2], partes[1::2]))


def aplicar_commit(clone, sha, pasta_saida):
    """Retorna 'aplicado', 'ja-existia' ou 'parcial'. Lança Falha se não for possível aplicar."""
    r = executar(["git", "cherry-pick", sha], cwd=clone)
    if r.returncode == 0:
        return "aplicado"
    nao_resolvidos = git("diff", "--name-only", "--diff-filter=U", cwd=clone, check=False)
    preparado = executar(["git", "diff", "--cached", "--quiet"], cwd=clone).returncode != 0
    if not nao_resolvidos and not preparado:          # nada a aplicar: mudança já presente
        git("cherry-pick", "--skip", cwd=clone, check=False)
        return "ja-existia"
    git("cherry-pick", "--abort", cwd=clone, check=False)
    itens = itens_do_commit(clone, sha)
    novos = [p for s, p in itens if s == "A"]
    alterados = [p for s, p in itens if s != "A"]
    if not alterados:
        raise Falha(f"conflito ao aplicar {sha[:7]}: estes arquivos NOVOS já existem no repositório:\n  "
                    + "\n  ".join(novos) + "\nEnvie esta mensagem para quem está ajudando no projeto.")
    ja_existem = [p for p in novos if (clone / p).exists()]
    if ja_existem:
        raise Falha(f"conflito ao aplicar {sha[:7]}: arquivos novos já existem: {', '.join(ja_existem)}")
    patch = git("diff", f"{sha}^", sha, "--", *alterados, cwd=clone, bruto=True)
    arq_patch = pasta_saida / f"edicoes_nao_aplicadas_{sha[:7]}.patch"
    arq_patch.write_text(patch, encoding="utf-8", newline="\n")
    PATCHES.append(arq_patch.name)
    dizer(f"      conflito em arquivos existentes ({', '.join(alterados)}): apliquei só os arquivos novos; "
          f"as edições ficaram em {arq_patch.name}")
    if novos:
        git("checkout", sha, "--", *novos, cwd=clone)
        mensagem = git("log", "-1", "--format=%B", sha, cwd=clone, bruto=True).rstrip("\n")
        mensagem += (f"\n\nNota do aplicador: as edições em {', '.join(alterados)} NÃO foram aplicadas "
                     "(conflito com o conteúdo atual do repositório); ficaram num arquivo .patch separado.\n")
        autor = git("log", "-1", "--format=%an <%ae>", sha, cwd=clone)
        data = git("log", "-1", "--format=%aI", sha, cwd=clone)
        git("add", "--", *novos, cwd=clone)
        git("commit", "-F", "-", "--author", autor, "--date", data, cwd=clone, entrada=mensagem)
    return "parcial"


def aplicar_sobreposicao(clone, ref):
    """Instala por sobreposição os arquivos da árvore de `ref`. Retorna ('sobreposto'|'ja-existia', linhas do status)."""
    caminhos = [p for p in git("ls-tree", "-r", "--name-only", "-z", ref, cwd=clone, bruto=True).split("\0")
                if p and p not in EXCLUIR_SOBREPOSICAO]
    if git("status", "--porcelain", cwd=clone):
        raise Falha("a cópia de trabalho não está limpa antes da sobreposição")
    git("checkout", ref, "--", *caminhos, cwd=clone)
    mudancas = git("status", "--porcelain", cwd=clone).splitlines()
    if not mudancas:
        return "ja-existia", []
    mensagem = git("log", "-1", "--format=%B", ref, cwd=clone, bruto=True).rstrip("\n") + "\n"
    autor = git("log", "-1", "--format=%an <%ae>", ref, cwd=clone)
    data = git("log", "-1", "--format=%aI", ref, cwd=clone)
    git("commit", "-F", "-", "--author", autor, "--date", data, cwd=clone, entrada=mensagem)
    return "sobreposto", mudancas


def extrair_auditor(clone, refs, pasta):
    """Copia o auditor do pacote para fora do clone, para auditar TODOS os branches (mesmo os que não o trazem)."""
    for ref in refs:
        if executar(["git", "cat-file", "-e", f"{ref}:tools/auditar_repositorio.py"], cwd=clone).returncode == 0:
            destino = pasta / "auditar_repositorio_do_pacote.py"
            destino.write_text(git("show", f"{ref}:tools/auditar_repositorio.py", cwd=clone, bruto=True),
                               encoding="utf-8", newline="\n")
            return destino
    local = AQUI / "auditar_repositorio.py"      # alternativa: o auditor guardado ao lado deste script
    return local if local.is_file() else None


def processar_branch(clone, ref, padrao, args, pasta, indice, total, auditor):
    branch = ref[len("refs/pacote/"):]
    slug = branch.replace("/", "_")
    dizer("")
    dizer(f"=== Branch {indice}/{total}: {branch} ===")
    raizes = git("rev-list", "--max-parents=0", ref, cwd=clone).split()
    if len(raizes) != 1:
        raise Falha(f"o branch {branch} do pacote tem histórico inesperado (mais de uma raiz)")
    commits = git("rev-list", "--reverse", f"{raizes[0]}..{ref}", cwd=clone).split()
    dizer(f"[a] {len(commits)} commits; base no repositório: {padrao}")

    git("checkout", "-q", "-b", branch, padrao, cwd=clone)
    resultado, tests_novos = [], []
    if branch.startswith(PREFIXO_SOBREPOSICAO):
        dizer("[b] Instalando por SOBREPOSIÇÃO (arquivos de mesmo nome são substituídos; "
              ".gitignore e INSTRUCOES_DE_INSTALACAO.md não são tocados):")
        estado, mudancas = aplicar_sobreposicao(clone, ref)
        for linha in mudancas:
            dizer("  - " + ("substitui " if linha[0] == "M" else "adiciona   ") + linha[3:])
        if estado == "ja-existia":
            dizer("      nada a instalar: os arquivos já são idênticos aos do pacote — este branch NÃO será publicado.")
            git("checkout", "-q", "--detach", padrao, cwd=clone)
            git("branch", "-q", "-D", branch, cwd=clone)
            return
        resultado = ["aplicado"]
    else:
        dizer("[b] Aplicando os commits:")
        for sha in commits:
            titulo = git("log", "-1", "--format=%s", sha, cwd=clone)
            estado = aplicar_commit(clone, sha, AQUI)
            resultado.append(estado)
            tests_novos += [p for s, p in itens_do_commit(clone, sha)
                            if s == "A" and p.startswith("tests/test_") and p.endswith(".py")]
            dizer(f"  - {estado:<10} {titulo}")
        if not any(e in ("aplicado", "parcial") for e in resultado):
            raise Falha(f"nenhum commit do branch {branch} pôde ser aplicado")

    dizer("[c] Auditoria de dados sensíveis no branch resultante...")
    if auditor is None:
        dizer("      (o pacote não traz o auditor — etapa pulada)")
    else:
        json_auditoria = pasta / f"auditoria_{slug}.json"
        aud = executar([sys.executable, str(auditor), "--raiz", str(clone), "--json", str(json_auditoria)], cwd=clone)
        (AQUI / f"auditoria_resultado_{slug}.txt").write_text(aud.stdout, encoding="utf-8")
        achados = json.loads(json_auditoria.read_text(encoding="utf-8")) if json_auditoria.exists() else []
        bloqueios = [a for a in achados if a["nivel"] == "BLOQUEIO" and a["origem"] != "historico"]
        historicos = [a for a in achados if a["nivel"] == "BLOQUEIO" and a["origem"] == "historico"]
        dizer(f"      {len(bloqueios)} BLOQUEIO(s) na árvore atual, {len(historicos)} no histórico "
              f"(relatório só com caminhos: auditoria_resultado_{slug}.txt)")
        if bloqueios:
            raise Falha("a auditoria encontrou dado sensível NA ÁRVORE do repositório "
                        f"(veja auditoria_resultado_{slug}.txt).\nConforme as regras do projeto, não faço push "
                        "adicional antes de tratar isso com o responsável.")
        if historicos:
            dizer("      ATENÇÃO: há arquivos sensíveis no HISTÓRICO do repositório (já estavam lá antes deste pacote). "
                  "Avise o responsável; este pacote não piora a situação.")

    dizer("[d] Rodando os testes que o branch trouxe...")
    modulos = sorted({"tests." + Path(p).stem for p in tests_novos})
    if not modulos:
        dizer("      (nenhum teste novo neste branch)")
    else:
        t = executar([sys.executable, "-m", "unittest", *modulos], cwd=clone)
        (AQUI / f"resultado_testes_{slug}.txt").write_text((t.stdout or "") + (t.stderr or ""), encoding="utf-8")
        resumo = [l for l in (t.stderr or "").splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
        dizer("      " + " | ".join(resumo))
        if t.returncode != 0:
            raise Falha("os testes do branch FALHARAM neste computador (provavelmente um detalhe do Windows).\n"
                        f"Envie o arquivo resultado_testes_{slug}.txt (ao lado deste script) para corrigirmos.")

    if args.sem_push:
        dizer(f"[e] --sem-push: nada publicado. O branch '{branch}' está pronto em: {clone}")
        return
    dizer(f"[e] Publicando '{branch}' no GitHub (somente ele; sem force)...")
    if executar(["git", "push", "-u", "origin", branch], cwd=clone, capturar=False).returncode != 0:
        raise Falha("o push foi recusado ou falhou; nada foi alterado no GitHub para este branch.")
    PUBLICADOS.append(branch)


def executar_etapas(args):
    bundle = localizar_bundle(args.bundle)
    conferir_git_e_identidade()
    pasta = Path(args.pasta_trabalho) if args.pasta_trabalho else Path(tempfile.mkdtemp(prefix="App_clinica_pacote_"))
    pasta.mkdir(parents=True, exist_ok=True)
    clone = pasta / "App_clinica"
    if clone.exists():
        raise Falha(f"a pasta {clone} já existe; apague-a ou use --pasta-trabalho com outra pasta")

    dizer(f"[2] Clonando {args.repo} (se o Git pedir login do GitHub, entre normalmente)...")
    if executar(["git", "clone", args.repo, str(clone)], capturar=False).returncode != 0:
        raise Falha("não foi possível clonar o repositório (login recusado? sem acesso ao repositório privado?)")

    padrao = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=clone, check=False)
    if not padrao:
        atual = git("rev-parse", "--abbrev-ref", "HEAD", cwd=clone, check=False)
        if not atual or atual == "HEAD":
            raise Falha("o repositório está vazio ou sem branch padrão")
        padrao = "origin/" + atual

    git("fetch", str(bundle), "+refs/heads/*:refs/pacote/*", cwd=clone)
    refs = sorted(git("for-each-ref", "--format=%(refname)", "refs/pacote/", cwd=clone).splitlines())
    if not refs:
        raise Falha("o pacote não contém nenhum branch")
    nomes = [r[len("refs/pacote/"):] for r in refs]
    dizer(f"[3] Pacote {bundle.name}: {len(refs)} branch(es): {', '.join(nomes)}")
    for nome in nomes:
        if git("ls-remote", "--heads", "origin", f"refs/heads/{nome}", cwd=clone):
            raise Falha(f"o branch '{nome}' JÁ EXISTE no GitHub; não vou sobrescrevê-lo.")

    auditor = extrair_auditor(clone, refs, pasta)
    for i, ref in enumerate(refs, start=1):
        processar_branch(clone, ref, padrao, args, pasta, i, len(refs), auditor)

    dizer("")
    if args.sem_push:
        dizer(f"PRONTO (sem publicar). Cópia de trabalho: {clone}")
        return 0
    if not PUBLICADOS:
        dizer("PRONTO. Nada a publicar: o repositório já está idêntico ao conteúdo do pacote.")
        return 0
    dizer("PRONTO. Branches publicados: " + ", ".join(PUBLICADOS))
    if PATCHES:
        dizer("ATENÇÃO: edições de arquivos existentes (README/ROADMAP/diário) NÃO entraram (conflito). Elas só se aplicam às")
        dizer("versões NOVAS desses arquivos (as do pacote de documentação). Se o repositório ainda tem as versões antigas,")
        dizer("instale primeiro o pacote de documentação (INSTRUCOES_DE_INSTALACAO.md) e depois rode, na cópia de trabalho:")
        for nome in PATCHES:
            dizer(f"    git apply --3way \"{AQUI / nome}\"")
    if args.repo.startswith("https://github.com/"):
        base = args.repo[:-4] if args.repo.endswith(".git") else args.repo
        for b in PUBLICADOS:
            dizer(f"Abra o Pull Request: {base}/compare/{b}?expand=1")
    dizer(f"(cópia de trabalho: {clone})")
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Aplica o pacote ao repositório App_clinica.")
    ap.add_argument("--repo", default=REPO_PADRAO)
    ap.add_argument("--pasta-trabalho", default=None)
    ap.add_argument("--bundle", default=None)
    ap.add_argument("--sem-push", action="store_true")
    args = ap.parse_args()
    try:
        return executar_etapas(args)
    except Falha as exc:
        dizer("")
        if PUBLICADOS:
            dizer("PAROU. Já publicado(s) ANTES da falha: " + ", ".join(PUBLICADOS) + ". O restante NÃO foi publicado.")
        else:
            dizer("PAROU — NADA FOI PUBLICADO.")
        dizer(str(exc))
        return 1
    finally:
        try:
            (AQUI / "aplicar_pacote_log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
