# Atualizações do NutriLab — Android e Windows

## Princípios obrigatórios

- Consultar releases publicados em `Dinossauro1223/App_clinica`; não tratar erro de rede/API como "já atualizado".
- Atualização de aplicativo e migração de banco são operações distintas.
- Nunca apagar, recriar ou substituir `clinica.db`, `mobile.db`, mapas, fila offline, backups ou anexos.
- A atualização desktop deve executar backup SQLite verificável antes de qualquer migração; preservar os arquivos de dados fora do pacote do programa.
- Não fazer limpeza genérica de Downloads. Android só pode remover IDs de downloads APK que o próprio NutriLab registrou.
- Não instalar silenciosamente: Android exige confirmação do usuário e autorização do instalador de pacotes.

## Android

O APK continua sendo uma casca WebView. A interface servida pelo computador não exige recompilação do APK a cada mudança visual. O APK é compilado no GitHub Actions quando uma tag `v*` é publicada.

O workflow `.github/workflows/release.yml` exige os secrets:
- `ANDROID_KEYSTORE_BASE64`: keystore de assinatura em Base64;
- `ANDROID_KEYSTORE_PASSWORD`;
- `ANDROID_KEY_ALIAS`;
- `ANDROID_KEY_PASSWORD`.

**A mesma chave deve ser usada em todas as versões.** Sem ela, Android rejeitará a instalação por cima do aplicativo existente. Nunca commitar o keystore ou senhas. O APK inicial já distribuído com uma chave local precisa ser substituído uma vez por uma instalação assinada com a chave oficial; depois disso, as atualizações preservam a identidade do pacote.

O app consulta a release estável, compara `versionName`, oferece o APK e usa DownloadManager/instalador Android. Quando a versão local já é a mais recente, remove somente downloads temporários previamente registrados pelo próprio app.

## Windows — estado desta entrega

O módulo `desktop/atualizador.py` consulta a release mais recente e compara versões sem tocar no banco ou nos arquivos locais. O pacote Windows ainda não é publicado automaticamente por este workflow. Até existir um empacotamento Windows reproduzível e um aplicador transacional testado, o app deve informar a versão e abrir a página da release para instalação manual.

**Não declarar atualização automática do executável Windows concluída.** O próximo passo é construir o pacote PyInstaller a partir de um banco-modelo sanitizado e implementar o aplicador que espera o processo encerrar, faz backup verificado e troca apenas os arquivos do programa, nunca os dados.

## Versionamento

- Android: `mobile/version.properties`.
- Desktop: `desktop/version.json`.
- Releases: tags semânticas `vMAJOR.MINOR.PATCH`.
- Publicar notas de versão e anexar `NutriLab-Mobile.apk` e `SHA256SUMS.txt`.
