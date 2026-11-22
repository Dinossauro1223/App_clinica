# NutriLab — integração desktop ⇄ mobile e APK

Entregue em **12/11/2026** (terceira entrega do mobile no dia). **Substitui a seção 9 de `INTEGRACAO_MOBILE.md`** ("Integração com o desktop, próximo chat").
Precisa do servidor mobile atualizado (`mobile/servidor.py` da versão 2, que vem junto no pacote "Att 14.11.26 Mobile Completo"). Com o servidor da primeira versão a tela avisa que está desatualizado.

## 1. Como o desktop conversa com o mobile

Desktop e servidor ficam **no mesmo computador**. O desktop (`integracao_mobile.py`) usa as funções de `mobile/servidor.py` direto sobre o banco do servidor
(`mobile/dados/mobile.db`): sem HTTP, sem senha, sem compartilhar arquivo pela rede (o `CLAUDE.md` proíbe SQLite em rede). O servidor pode estar ligado ou não.
O caminho do banco fica na configuração `mobile_db` do `clinica.db` (padrão `mobile/dados/mobile.db`; botão "Trocar banco" na tela).

## 2. Tela "Mobile (copa)" (`mobile_ui.py`, botão novo no menu lateral)

- **Verificar o que chegou do mobile:** compara o mapa do dia com o do desktop e lista o que o nutricionista precisa conferir; ao mesmo tempo guarda as contagens de refeição e de estoque.
- **Aplicar marcados / Ignorar marcados:** só entra no mapa o que for aprovado. Itens que só preenchem campos vazios já vêm marcados; os que sobrescrevem dado ou trocam o paciente, não.
- **Enviar mapa para a copa:** grava o mapa do dia no mobile como administrador e **publica**: as copeiras recebem o popup com os leitos alterados. Antes de enviar, avisa se há alterações da copa ainda não conferidas.
- Painel web (`http://localhost:8765`) continua existindo para usuários, setores, itens e horários. A tela abre também sozinha: `python mobile_ui.py` (útil se o botão do `main.py` não for aplicado).

## 3. Regras do que vem do mobile

| Situação | Tipo | Marcado? | O que acontece ao aplicar |
|---|---|---|---|
| Leito sem registro no desktop e com paciente no mobile | novo | sim | cria o registro (nome, idade, acompanhante, preferências, consistência/via) e o paciente |
| Mesmo paciente, dados novos | alterado | sim, se só preencher campos vazios | atualiza **só os campos que vieram**; antropometria, suplementos e vínculo do paciente ficam |
| Nome diferente no leito | troca | não | registro limpo do novo paciente (dados clínicos do anterior **não** passam) |
| Mobile sem paciente e desktop com registro | liberar | não | remove o registro do dia |

- **Valor vazio do mobile nunca apaga dado do desktop** (exceto "acompanhante", que é sim/não).
- **Correção da copa** (copeira mudou algo que o admin/nutrição já tinha publicado no dia) chega aqui como proposta "correção da copa": aplicar **aprova** a correção no mobile; ignorar **recusa**.
- **Ignorado não volta** até o mobile mudar aquele leito (`Mobile_Visto`). O que o desktop acabou de enviar também não volta como novidade.
- Correções de refeição/estoque não são decididas aqui: a tela só mostra quantas esperam no painel web.

## 4. Mapeamento de campos

| Mobile | Desktop (`Mapa_Registros`) |
|---|---|
| nome, idade_anos, idade_meses, acompanhante | nome_paciente, idade_anos, idade_meses, acompanhante |
| pref_sim, pref_nao | obs_sim, obs_nao |
| dieta: Geral/Livre, Branda, Pastosa, Líquida, Líq/Past | consistencia: Livre, Branda, Pastosa, Líquida, Líq/Past |
| dieta: Enteral | via = Enteral |
| dieta: outro texto (Hipossódica, Zero...) e diagnóstico | sem campo: guardados em `Mobile_Extra` (e mostrados na conferência) |

Ao **enviar**: dieta ← consistência (ou "Enteral"), diagnóstico ← siglas DM/HAS/DRC marcadas, preferências ← obs_sim/obs_nao. Se o desktop não tiver dieta/diagnóstico, o que a copa/nutrição digitou no mobile é mantido.
Leito vazio no desktop só é "liberado" na copa se foi o próprio desktop que pôs o paciente lá antes (`Mobile_Enviado`); senão pode haver dado novo da copa e nada é mexido.

## 5. Tabelas novas no `clinica.db` (criadas sob demanda, prefixo `Mobile_`)

`Mobile_Refeicoes(data, setor, refeicao, qtd)` · `Mobile_Estoque_Dia(data, estoque, item, unidade, qtd)` · `Mobile_Movimentos(data, id_mobile, hora, origem, destino, item, unidade, qtd, divergente)` ·
`Mobile_Extra(data, setor, leito, dieta, diagnostico)` · `Mobile_Visto(data, setor, leito, assinatura)` · `Mobile_Enviado(setor, leito, com_paciente, data)`.
Nenhuma tabela existente foi alterada; `mapa_db.py` não foi tocado. Setores e leitos faltantes são criados no desktop pelo nome/código vindos do mobile.

## 6. APK (`mobile/apk/`)

`Gerar_APK.bat` gera `saida\NutriLab-Mobile.apk`: uma casca Android (WebView, minSdk 26) que pede o endereço do servidor na primeira vez e abre a página servida pelo computador.
Sem Gradle nem Android Studio: baixa o JDK 17 e as ferramentas do Android para `%LOCALAPPDATA%\NutriLabApk` (uma vez, ~600 MB) e monta o APK com `aapt2`, `javac`, `d8`, `zipalign` e `apksigner`.
A chave de assinatura fica nessa mesma pasta (atualizações instalam por cima). Ao final oferece servir o APK pelo Wi-Fi (`servir_apk.py`, porta 8000) para baixar no celular. Detalhes: `mobile/apk/LEIA-ME.txt`.
A tela do app é a do servidor; mudar o visual **não** exige gerar o APK de novo. Caminho do projeto com acento (como `C:\Users\fulano nutrição`): o `aapt2` do Android não abre pastas com acento, então o gerador compila numa pasta de trabalho sem acento (a pasta das ferramentas usa o caminho curto do perfil) e devolve o APK para `saida\`. O app confere o endereço digitado (`GET /api/eu` sem login deve devolver 401 com `erro`), assume a porta 8765 quando ela é omitida, explica o motivo quando o endereço não é o servidor do NutriLab (por exemplo a porta 8000, que só serve o download do APK) ou não responde, e o `Gerar_APK.bat` grava o IP deste computador em `assets/servidor.txt` para o endereço já vir preenchido.

## 7. Limites

Desktop e servidor precisam estar no mesmo computador (para outro computador seria preciso um modo HTTP). Rodando como programa empacotado (PyInstaller) a pasta `mobile` precisa ir junto; pelo código-fonte funciona direto.
Não feito: tela de estoque/refeições dentro do desktop (os dados já chegam nas tabelas `Mobile_*`), decisão de correções de refeição/estoque pelo desktop, notificação com o app do celular fechado.
O APK ainda não foi confirmado em aparelho: o primeiro teste real (14/11/2026) parou no `aapt2` por causa do acento no caminho do usuário, o que foi corrigido; o registro do `.bat` (`gerar_apk_log.txt`) mostra qualquer falha nova.

## 8. Commits (todos com o dia na mensagem)

APK e gerador · módulo de integração e testes · tela Mobile · botão no `main.py` · esta documentação.


## Suplementos e campos estruturados da Copa

O envio desktop → mobile atualiza o catálogo ativo `Mapa_Suplementos` na tabela `suplementos_catalogo` do banco mobile. A sincronização também ocorre ao abrir o painel Mobile no desktop. O aplicativo da Copa consulta `GET /api/suplementos` ao entrar, utilizando o último catálogo sincronizado quando estiver sem conexão.

O retorno mobile → desktop mapeia cor, via, consistência e características DM/HAS/laxativa/constipante/DRC para `Mapa_Registros`. Os detalhes de cada suplemento são preservados em `Mapa_Registro_Suplementos`, incluindo mL por oferta, água adicionada, refeições selecionadas e indicação de preparo com fruta.

A tela principal do Mapa Nutricional abre em **Visão geral (todos os setores)**. A lista inclui registros recebidos de todos os setores mobile e apresenta uma coluna Setor para diferenciar leitos com códigos iguais. É possível selecionar um setor específico no mesmo filtro. Os dados permanecem vinculados ao setor original; não são mesclados em uma única tabela de leitos.
