# NutriLab Mobile — descrição e guia de integração

Entregue em **12/11/2026** (duas entregas no mesmo dia; este arquivo vale para a versão atual, branch `feat/mobile-nutricao-copa-refeicoes-2026-11-12`,
que inclui a primeira). Descreve **tudo** o que existe, para o programa desktop (CustomTkinter/SQLite) ser atualizado depois, em outro chat,
para receber/enviar estes dados.

## 1. O que existe

Um servidor pequeno (`mobile/servidor.py`, só biblioteca padrão do Python) que roda **no computador do administrador** e serve uma página
(`mobile/static/index.html`) aos celulares da mesma rede. A página muda de cor e de abas conforme o login. Não toca em `main.py`, `mapa_db.py`
nem no `clinica.db`.

Como rodar: dois cliques em `mobile/iniciar_servidor.bat` (ou `python mobile/servidor.py`). Na primeira vez mostra a senha do usuário `admin`
(`--redefinir-admin` gera outra). No computador: `http://localhost:8765`; nos celulares: o endereço `http://IP:8765` mostrado na tela, no **mesmo
Wi-Fi/rede** (liberar a porta 8765 no Firewall do Windows, rede privada). Qualquer IP que não seja de rede local é recusado. O banco fica em
`mobile/dados/mobile.db` (não versionar: `*.db` está no `.gitignore`); bancos da primeira entrega são atualizados sozinhos na inicialização.

## 2. Perfis e permissões

| Perfil | Cor | Abas | Pode |
|---|---|---|---|
| `admin` | azul-petróleo | Painel, Mapa, Refeições, Estoques, Avisos, Cadastros | tudo, de qualquer dia; cria usuários, setores/leitos, itens; habilita refeições; decide correções |
| `nutricionista` (`id_setor` vazio = todos os setores) | verde | Painel, Mapa, Refeições, Avisos | edita o mapa (rascunho) e **publica para a copa**; envia avisos; ajusta horários de contagem do setor; decide correções de mapa/refeições do setor; não acessa estoque |
| `copa` (copeira; `id_setor` = setor dela) | âmbar | Mapa, Refeições, Estoque | mapa e contagem do próprio setor, só hoje; estoque da copa |
| `estoque_cozinha` | tijolo | Estoque | só o estoque da cozinha, só hoje |
| `estoque_almox` | índigo | Estoque | só o almoxarifado, só hoje |

Perfis `setor` e `estoque_copa` da primeira entrega viram `copa` na migração (a copa agora faz mapa, contagem e estoque com um só login).

## 3. Mapa da copa e publicação pela nutrição

- Campos por leito: **nome**, **idade** (anos e meses), **tipo de dieta** (opcional), **diagnóstico** (opcional), **preferências: gosta / não aceita**
  (opcionais), acompanhante. Leito sem nome = leito livre (os demais campos são limpos). O leito em si vem do cadastro de setores.
- A **copeira** grava direto (só no dia de hoje; o formulário abre com o último mapa salvo).
- **Nutrição/admin** gravam **rascunho** (`mapa_rascunho`): a copa não vê nada até o botão **"Salvar e publicar para a copa"**. Publicar aplica o
  rascunho do setor e cria **um aviso** com os leitos alterados (`novo`, `alterado` + campos, `liberado`). Nada é em tempo real: nada apita enquanto
  a nutrição trabalha. Assim dieta, diagnóstico e preferências aparecem sozinhos no mapa da copa, sem retrabalho.
- Se a copa alterar depois um leito que a nutrição/admin já gravou no dia, nada é sobrescrito: nasce uma **correção pendente** (só daquele leito, com os
  campos mudados) para a nutrição do setor ou o admin aprovar/recusar no Painel. Para refeições e estoque a regra é a mesma (estoque: só o admin decide).

## 4. Avisos no celular

`GET /api/avisos` (não lidos da copa: do setor dela ou gerais, criados depois do cadastro dela) e `POST /api/avisos/lidos {ids}`. A página mostra um
**popup ao entrar** e confere de novo a cada 60 s enquanto está aberta (e ao voltar para a aba), com vibração. **Notificação do sistema** (barra do
celular) só funciona se o navegador permitir, o que exige HTTPS; em `http://IP` Chrome/Safari bloqueiam. Notificação com o app fechado pede HTTPS + Web Push
(**não feito**). Aviso em texto livre: `POST /api/nutri/avisos {texto, id_setor?}`.

## 5. Contagem de refeições

- Conferidas hoje: **almoço e jantar** (`refeicoes_cfg.ativa`). O admin pode habilitar outras (desjejum, colação, lanche, ceia) na aba Cadastros, com horário.
- Horário de contagem (relógio do servidor, UTC−3): **almoço 09:00–16:00** (serviço padrão 11:30–13:30 + folga larga), **jantar 16:00–22:00**. A
  nutrição do setor pode mudar o horário do **seu** setor (`janelas`), que prevalece sobre o padrão. Janela não atravessa a meia-noite.
- A copa só conta refeição habilitada e **dentro do horário** (fora dele o campo fica bloqueado e o servidor recusa). Nutrição/admin contam a qualquer hora.
  A contagem recomeça do zero a cada dia.

## 6. Regras que continuam valendo

Copa e estoquistas só gravam no **próprio dia** (data do servidor); formulários de mapa e estoque começam pelo **último valor salvo**; hierarquia de
estoques em `POST /api/estoque/reposicao`: almoxarifado recebe só de `externo`; **cozinha só do almoxarifado**; **copa da cozinha** e, só com a cozinha em
zero naquele item, do almoxarifado (saldo da origem menor que o retirado = movimento `divergente`, avisado no Painel).

## 7. Dados (`mobile.db`)

`usuarios(id, login, nome, perfil, id_setor, salt, senha[PBKDF2], ativo)` · `setores` · `leitos(id_setor, codigo)` · `itens(nome, unidade)` ·
`mapa_dia(data, id_leito, ocupado, acompanhante, dieta, nome, idade_anos, idade_meses, diagnostico, pref_sim, pref_nao, por_usuario, por_perfil, atualizado_em)` ·
`mapa_rascunho(data, id_leito, campos[JSON])` · `refeicoes_cfg(refeicao, ativa, abre, fecha)` · `janelas(id_setor, refeicao, abre, fecha)` ·
`refeicoes_dia(data, id_setor, refeicao, qtd, …)` · `estoque_dia(data, estoque, id_item, qtd, …)` · `movimentos` · `correcoes(tipo, data, chave, rotulo, id_setor, valor_atual, valor_proposto, status)` ·
`avisos(criado_em, tipo[mapa|texto], id_setor, titulo, texto, leitos[JSON])` · `avisos_lidos`. Datas `AAAA-MM-DD`; horas ISO com −03:00; `por_perfil` guarda quem gravou por último.

## 8. API (JSON, `Authorization: Bearer <token>`)

`POST /api/login` · `GET /api/eu|setores|itens|avisos` · `POST /api/avisos/lidos` · `GET|POST /api/mapa` · `GET|POST /api/refeicoes` · `GET|POST /api/estoque` ·
`POST /api/estoque/reposicao` · nutrição e admin: `GET /api/nutri/painel`, `GET /api/nutri/correcoes`, `POST /api/nutri/correcoes/<id> {acao}`,
`POST /api/nutri/publicar {setor, data?, texto?}`, `POST /api/nutri/avisos`, `POST /api/nutri/janelas {setor?, refeicao, abre, fecha}` · admin: `GET|POST /api/admin/usuarios`,
`POST /api/admin/usuarios/<id>`, `POST /api/admin/setores`, `POST /api/admin/itens`, `GET|POST /api/admin/refeicoes`, **`GET /api/admin/exportar?data=`**.
Linhas do mapa: `{id_leito, nome, idade_anos, idade_meses, dieta, diagnostico, pref_sim, pref_nao, acompanhante}`.

## 9. Integração com o desktop (próximo chat)

O desktop entra como **nutricionista** e usa os mesmos endpoints: ao salvar o mapa, `POST /api/mapa` (vira rascunho) e, no botão "atualizar para a copa",
`POST /api/nutri/publicar` — o aviso aos celulares sai automaticamente. Leitura de volta (contagens, estoque, correções): `GET /api/admin/exportar?data=`
(`esquema: 2`). Mapeamento sugerido: `setores`→`Mapa_Setores`, `leitos`→`Mapa_Leitos`, `nome`→`nome_paciente`, `idade_anos/meses`→idem, `pref_sim/pref_nao`→`obs_sim/obs_nao`,
`dieta`→(a decidir: `consistencia`/`via`), `diagnostico`→(a decidir; hoje o desktop tem só flags de doenças), `refeicoes_dia`/`estoque_dia`→tabelas novas.
Em aberto: de onde nascem setores/leitos (hoje, do admin web); banco central definitivo (o `CLAUDE.md` proíbe compartilhar SQLite por rede; aqui só o processo do servidor abre o arquivo).

## 10. Privacidade e limites

- **Decisão de 12/11/2026:** a copa passa a ver nome, idade e, se preenchidos, diagnóstico e preferências. Isso **contraria** a regra do `CLAUDE.md` ("nunca expor
  PEP, diagnóstico ou antropometria a funcionário com permissão apenas de refeições"): atualizar essa linha para abrir a exceção do mapa da copa. Antropometria e PEP continuam fora do mobile.
- A comunicação é **HTTP sem criptografia** (só rede interna): como agora há dados de paciente, usar Wi-Fi fechado/dedicado e, antes de uso amplo, HTTPS.
- Sessões ficam em memória (reiniciar o servidor pede novo login). Sem modo offline.
- **Não feito:** refeição por paciente com aceitação 0/25/50/75/100, conferência de refeições de servidores, notificação com o app fechado, histórico de avisos na tela, exclusão de leitos/itens,
  nutricionista responsável por mais de um setor (hoje: um setor ou todos).

## 11. Commits do branch (todos levam o dia na mensagem)

1–4: primeira entrega (servidor, interface, testes, documentação). 5–8, esta entrega: servidor com nutricionista/copa/rascunho/avisos/horários, interface por perfil,
testes (8, dados sintéticos) e este arquivo.
