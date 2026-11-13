# NutriLab Mobile — descrição e guia de integração

Entregue em **12/11/2026** (branch `feat/mobile-lan-perfis-2026-11-12`). Este arquivo descreve **tudo** o que foi feito,
para que o programa desktop (CustomTkinter/SQLite) seja atualizado depois, em outro chat, para receber estes dados.

## 1. O que existe

Um servidor pequeno (`mobile/servidor.py`, só biblioteca padrão do Python, nenhuma instalação nova) que roda **no computador do
administrador** e serve uma página (`mobile/static/index.html`) para os celulares da mesma rede. A página muda de visual e de
abas conforme o login. Não toca em `main.py`, `mapa_db.py` nem no `clinica.db`.

Como rodar: dois cliques em `mobile/iniciar_servidor.bat` (ou `python mobile/servidor.py`). Na primeira vez ele mostra a senha do
usuário `admin` (anote; `--redefinir-admin` gera outra). Administrador abre `http://localhost:8765`; celulares abrem o endereço
`http://IP-DO-PC:8765` mostrado na tela, ligados ao **mesmo Wi-Fi/rede**. Se o celular não abrir, liberar a porta 8765 no
Firewall do Windows (rede privada). O servidor **recusa qualquer IP que não seja de rede local**.
O banco fica em `mobile/dados/mobile.db` (não versionar: `*.db` já está no `.gitignore`).

## 2. Perfis e permissões

| Perfil | Visual | Abas | Pode |
|---|---|---|---|
| `admin` (no computador) | azul-petróleo, painel amplo | Painel, Mapa, Refeições, Estoques, Cadastros | tudo, de qualquer dia; aprova/recusa correções; cria usuários, setores/leitos, itens |
| `setor` (um por setor) | verde | Mapa, Refeições | só o próprio setor e só o dia de hoje |
| `estoque_copa` | âmbar | Estoque | só o estoque da copa, só hoje |
| `estoque_cozinha` | tijolo | Estoque | só o estoque da cozinha, só hoje |
| `estoque_almox` | índigo | Estoque | só o almoxarifado, só hoje |

Dados de paciente **não** circulam no mobile: o mapa traz só leito, ocupado, acompanhante e tipo de dieta (sem nome,
diagnóstico, antropometria — regra do `CLAUDE.md`). Quem pode mais que isso é o desktop.

## 3. Regras de negócio (todas validadas no servidor)

1. **Só o próprio dia:** usuário comum sempre grava na data do servidor (fuso America/Recife, UTC−3); a data enviada pelo celular é ignorada.
2. **Base do dia anterior:** ao abrir o formulário, cada leito/refeição/item vem com o último valor salvo até hoje (`herdado: true`,
   `data_base`). Salvar sem mexer confirma o dia sem retrabalho.
3. **Correção precisa de autorização:** se o **admin** já gravou aquele dado no dia e um usuário comum envia valor diferente, nada é
   sobrescrito: nasce uma linha em `correcoes` (`pendente`) só para o leito, refeição ou ingrediente alterado. O admin vê no Painel
   (valor atual × valor pedido) e **aprova** (aplica e passa a valer como valor do admin) ou **recusa**. Nova proposta do mesmo
   dado substitui a anterior.
4. **Hierarquia dos estoques** (`POST /api/estoque/reposicao`, sempre no dia de hoje; ajusta o saldo da origem e do destino):
   almoxarifado recebe só de `externo` (fornecedor/compra); **cozinha só do almoxarifado**; **copa** da cozinha e, só se a cozinha
   estiver com saldo zero daquele item, do almoxarifado. Se o saldo da origem era menor que o retirado, o movimento é aceito mas
   marcado `divergente` e aparece no Painel (contagem da origem desatualizada).
5. **Contagem do dia** (`POST /api/estoque`): define a quantidade do item no estoque. Reposição e contagem coexistem; recarregue a
   tela depois de registrar uma reposição (a tela já faz isso).

## 4. Modelo de dados (`mobile.db`)

`usuarios(id, login, nome, perfil, id_setor, salt, senha[PBKDF2-SHA256], ativo)` · `setores(id, nome)` · `leitos(id, id_setor, codigo)` ·
`itens(id, nome, unidade)` · `mapa_dia(data, id_leito, ocupado, acompanhante, dieta, por_usuario, por_perfil, atualizado_em)` ·
`refeicoes_dia(data, id_setor, refeicao, qtd, …)` com `refeicao` ∈ desjejum, colacao, almoco, lanche, jantar, ceia ·
`estoque_dia(data, estoque, id_item, qtd, …)` com `estoque` ∈ almox, cozinha, copa · `movimentos(data, hora, origem, destino, id_item, qtd, por_usuario, divergente)` ·
`correcoes(tipo, data, chave, rotulo, valor_atual, valor_proposto, por_usuario, status, decidido_em)`.
`por_perfil` guarda quem gravou por último (`admin` ativa a regra 3). Datas em `AAAA-MM-DD`; horas em ISO com −03:00.

Correspondência sugerida com o desktop: `setores`→`Mapa_Setores`, `leitos`→`Mapa_Leitos`, `mapa_dia.acompanhante`→`Mapa_Registros.acompanhante`,
`mapa_dia.dieta`→(a decidir: `consistencia`/`via`), `refeicoes_dia`→(tabela nova), `itens`/`estoque_dia`/`movimentos`→(módulo de estoque, Fase 6).

## 5. API (JSON; `Authorization: Bearer <token>`)

`POST /api/login` · `GET /api/eu` · `GET /api/setores` · `GET /api/itens` · `GET|POST /api/mapa` · `GET|POST /api/refeicoes` ·
`GET|POST /api/estoque` · `POST /api/estoque/reposicao` · admin: `GET /api/admin/painel`, `GET /api/admin/correcoes`,
`POST /api/admin/correcoes/<id>` `{acao: aprovar|recusar}`, `GET|POST /api/admin/usuarios`, `POST /api/admin/usuarios/<id>`,
`POST /api/admin/setores`, `POST /api/admin/itens`, **`GET /api/admin/exportar?data=AAAA-MM-DD`**.

## 6. Como o desktop vai receber (próximo chat)

O ponto de integração é `GET /api/admin/exportar`: devolve `{esquema: 1, data, setores, leitos, itens, mapa, refeicoes, estoque, movimentos, correcoes_pendentes}`
do dia pedido. Plano: botão no desktop que loga como admin, baixa o JSON e grava nas tabelas do Mapa/Estoque via o serviço de banco da Fase 0,
**sem** sobrescrever dados clínicos (o mobile só conhece leito, ocupação, acompanhante, dieta, refeições e estoque).
Decisões em aberto: mapeamento de `dieta`; se `setores`/`leitos` nascem no desktop e são enviados ao mobile (hoje nascem no admin web);
banco central definitivo (o `CLAUDE.md` proíbe compartilhar SQLite por rede — aqui o arquivo é acessado só pelo processo do servidor).

## 7. Limites desta entrega (não feito)

HTTP sem criptografia (uso restrito à rede interna); sessões em memória (reiniciar o servidor pede novo login); sem modo offline/PWA;
refeição **por paciente** com aceitação 0/25/50/75/100, janelas de almoço 12–13h e jantar 19–20h de servidores e reconciliação de
tickets (Fase 7) **não** foram feitas — hoje "refeições servidas" é a contagem diária por setor e refeição; cadastro de itens/leitos só cresce (sem exclusão);
a lista de itens é única para os três estoques (cada estoque guarda a própria quantidade).

## 8. Commits (todos levam o dia na mensagem, para o merge)

1. `[12/11/2026] mobile: servidor da rede local …` — `mobile/servidor.py`, `mobile/iniciar_servidor.bat`
2. `[12/11/2026] mobile: interface por perfil …` — `mobile/static/index.html`
3. `[12/11/2026] mobile: testes …` — `tests/test_mobile.py` (6 testes, dados sintéticos)
4. `[12/11/2026] mobile: documentação …` — este arquivo
