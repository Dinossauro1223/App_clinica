# Guia do usuário — proteção e recuperação dos dados

Este guia explica o que o NutriLab faz automaticamente para proteger o banco local e como interpretar as situações mais comuns. Ele descreve o comportamento implementado no código; não significa que a restauração já tenha uma tela própria no aplicativo.

## 1. O que é o banco de dados?

O arquivo `clinica.db` é a base local que guarda os registros estruturados do programa, como pacientes, consultas e informações dos módulos integrados. Ele não é a mesma coisa que uma exportação em PDF ou Excel: exportar um relatório não substitui um backup do banco.

**Não apague, renomeie, mova ou substitua `clinica.db` enquanto o NutriLab estiver aberto.** Também não abra o banco para edição manual em programas externos.

## 2. Quando o NutriLab cria backups?

O programa tenta criar cópias automáticas em três momentos:

- **Ao abrir uma sessão:** registra um ponto de recuperação próximo ao início do uso.
- **Periodicamente:** por padrão, a cada 15 minutos enquanto o programa está aberto.
- **Ao fechar normalmente:** tenta criar uma última cópia antes de encerrar a janela.

Os backups são cópias consistentes produzidas pela API de backup do SQLite e passam por verificação de integridade. O programa não deve considerar uma cópia concluída quando essa verificação falha.

Um desligamento abrupto pode impedir o backup final. Nesse caso, a cópia periódica mais recente é o ponto de recuperação disponível. Alterações feitas depois dela podem não estar no backup.

## 3. Onde ficam os arquivos?

Por padrão, o programa cria a pasta `backups` ao lado do banco de dados:

```text
Pasta do NutriLab/
├── NutriLab.exe
├── clinica.db
└── backups/
    ├── clinica.backup_20261122-080000_inicio-sessao.db
    ├── clinica.backup_20261122-081500_periodico.db
    └── clinica.backup_20261122-083000_fechamento.db
```

Os horários do nome usam o fuso de Recife. Os nomes acima são exemplos ilustrativos, não arquivos reais.

Cada arquivo identifica data, hora e motivo da cópia. Se já existir um arquivo com o mesmo nome, o programa cria outro com um sufixo numérico; ele não deve sobrescrever o backup anterior.

## 4. Como interpretar mensagens de backup?

| Situação | O que significa | Como agir |
|---|---|---|
| Falha no backup automático | O programa não conseguiu concluir uma cópia. | Leia o detalhe da mensagem, confira espaço livre e permissão de gravação. Não ignore falhas repetidas. |
| Falha ao fechar | A cópia final não foi concluída e o programa mantém a janela aberta. | Tente fechar novamente depois de resolver a causa. Não finalize o processo pelo Gerenciador de Tarefas como primeira opção. |
| Banco não encontrado | O arquivo esperado não está no caminho configurado. | Não crie um banco vazio por cima nem mova arquivos às pressas. Procure a pasta de dados correta e solicite suporte técnico. |
| Backup inválido/corrompido | A cópia não passou na verificação do SQLite. | Não a utilize para restauração. Escolha outro backup íntegro com suporte técnico. |
| Pasta em nuvem ou rede | O caminho pode causar conflitos de sincronização ou problemas de bloqueio do SQLite. | Use armazenamento local. Sincronização de pasta não é mecanismo multiusuário nem substitui cópia externa controlada. |

## 5. O que significa restaurar um backup?

Restaurar é substituir o estado atual do banco pelo conteúdo de uma cópia anterior. **Não é o mesmo que abrir um relatório antigo.** Registros criados depois da data do backup escolhido podem deixar de aparecer na base restaurada.

O serviço de restauração foi projetado para:

1. Verificar a integridade do arquivo escolhido.
2. Criar uma cópia de segurança do banco atual, identificada como `pre-restauracao`.
3. Preparar e verificar um arquivo temporário.
4. Fazer a substituição atômica do banco.
5. Preservar os arquivos auxiliares antigos do SQLite, em vez de descartá-los silenciosamente.

No Windows, o NutriLab deve estar completamente fechado antes da restauração, pois o sistema pode impedir a substituição de um arquivo que ainda esteja aberto.

**Atenção:** na versão documentada neste guia, o gerenciador automático de backups não oferece, por si só, uma tela de seleção/restauração para o usuário. A restauração deve ser realizada por procedimento técnico controlado, depois de confirmar o arquivo e o destino. Não tente fazê-la copiando arquivos manualmente por cima do banco.

## 6. Boas práticas para proteger os dados

- Mantenha espaço livre no disco onde o banco está armazenado.
- Faça cópias externas controladas da pasta `backups`, preferencialmente em mídia protegida e com acesso restrito.
- Não envie banco ou backups por e-mail, mensageiro ou repositório público: podem conter dados pessoais e clínicos.
- Não use OneDrive, Dropbox, Google Drive ou pasta de rede como local de trabalho do banco SQLite.
- Antes de atualizar o aplicativo, confirme que existe pelo menos um backup recente e íntegro.
- Depois de uma restauração, confira com o responsável técnico se os registros esperados estão presentes antes de retomar o uso.

## 7. Perguntas comuns

**“Fechei o programa sem clicar em salvar. O backup recupera tudo?”**

Não necessariamente. O backup é uma cópia do banco no momento em que foi criado. Ele não substitui o salvamento correto de cada formulário e não garante recuperar alterações ainda não gravadas.

**“O backup das 08h recupera o que registrei às 08h10?”**

Somente se os dados já estavam gravados no banco e uma cópia posterior os incluiu. O backup periódico padrão é feito a cada 15 minutos; portanto, pode existir uma janela entre cópias.

**“Posso apagar os backups antigos para liberar espaço?”**

Não faça isso sem uma política de retenção definida pelo responsável pelo sistema. Uma cópia antiga pode ser a única recuperação disponível caso as mais recentes estejam corrompidas.

**“Posso usar a mesma pasta de banco em dois computadores?”**

Não. O banco SQLite local não foi projetado para compartilhamento simultâneo por rede ou pasta sincronizada. O uso multiusuário exige uma arquitetura com serviço/API e banco central.

**“PDF ou Excel exportado é backup?”**

Não. São documentos de consulta/compartilhamento e podem conter apenas parte das informações. O backup é a cópia integral e verificável do banco local.
