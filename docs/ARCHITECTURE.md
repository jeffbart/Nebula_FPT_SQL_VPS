# Arquitetura

## Componentes

- `app/main.py`: ciclo de vida, workers Telegram e FTPS;
- `app/ftp/server.py`: protocolo FTP e upgrade TLS;
- `app/ftp/pathio.py`: sistema de arquivos virtual e staging;
- `app/ftp/repositories.py`: catálogo, usuários, partes e jobs no SQL Server;
- `app/ftp/staging_space.py`: liberação progressiva de clusters no Windows;
- `app/ftp/upload_caption.py`: legenda e formatação do progresso das partes;
- `app/ftp/queue_status.py`: apresentação dos estados consultados por `/queue`;
- `app/ftp/migrations`: schema SQL versionado.

## Consistência do upload

Cada parte segue esta ordem:

```text
ler staging
  -> enviar ao Telegram
  -> persistir telegram_message_id e telegram_file_id no SQL
  -> desalocar o intervalo local
```

Uma parte nunca é desalocada antes de existir no SQL. Se a persistência falhar,
o programa tenta apagar do Telegram somente a mensagem ainda não registrada.

Partes persistidas permanecem associadas ao job quando uma tentativa falha. Na
próxima inicialização, o worker soma os tamanhos contíguos já registrados, pula
esse intervalo e continua na próxima parte. O `obfuscated_id` também permanece
estável para manter os nomes internos consistentes.

## Legenda das partes

Antes de enviar uma parte, o worker calcula a quantidade total com base no
tamanho lógico do arquivo e no `CHUNK_SIZE`. A legenda contém:

```text
nome-original.ext
(parte atual de total de partes) (tamanho enviado de tamanho total)
```

Exemplo:

```text
backup.zip
(05 de 35) (300 MB de 2,7 GB)
```

O número mostrado ao usuário começa em 1; o `part_number` persistido e o nome
interno continuam começando em zero. O progresso inclui a parte que está sendo
enviada e é limitado ao tamanho total, inclusive em retomadas e na última parte.
Os nomes internos ofuscados permanecem inalterados e não substituem o nome
original exibido na legenda.

## Consulta da fila

O handler de `/queue` aceita o comando apenas no canal definido por `CHAT_ID`.
O estado é consultado diretamente nas tabelas `nodes` e `file_parts`, em vez de
inspecionar internamente o `asyncio.Queue`. Assim, a resposta continua coerente
após reinicializações e inclui o progresso já persistido no SQL Server.

Os arquivos são agrupados pelos estados `uploading`, `staging` e `failed`. A
resposta limita cada seção a 20 itens e respeita o limite de 4096 caracteres do
Telegram. Quando permitido, a mensagem original `/queue` é apagada do canal.

O comando `/fetch` consulta todos os nós no estado `failed`, acrescenta os dados
da tentativa de upload mais recente e envia um relatório tabulado em UTF-8. O
arquivo é construído em memória; nenhuma cópia do relatório permanece na VPS.
Esse relatório fornece os `node_id` necessários para auditar uma limpeza antes
de excluir registros ou mensagens do Telegram.

O comando destrutivo `/clearfailed` só é executado com o argumento literal
`confirmar`. Em uma transação, todos os nós `failed` passam para `deleting` e
recebem jobs de exclusão. Os IDs são colocados em `DELETE_QUEUE`; o worker apaga
partes do Telegram, remove o staging local quando presente e, por último, exclui
o nó SQL. Estados `staging`, `uploading` e `completed` não são selecionados.

O comando `/help` usa uma mensagem estática versionada em `queue_status.py`, para
que as instruções operacionais permaneçam alinhadas aos comandos disponíveis.

## Arquivos esparsos

No Windows, truncar o começo deslocaria todos os offsets e corromperia a
retomada. Por isso o programa usa `FSCTL_SET_SPARSE` e
`FSCTL_SET_ZERO_DATA`. O tamanho lógico não diminui durante o upload, mas um
volume compatível pode desalocar os clusters da parte confirmada.

Se a operação não estiver disponível, o programa registra um aviso e preserva
o arquivo até a conclusão. Esse fallback privilegia integridade sobre economia
de disco.

## Exclusão

O catálogo entra no estado `deleting`; o worker agrupa os IDs por canal, apaga
as mensagens e somente então remove o nó SQL. Falhas são reagendadas e as
referências permanecem disponíveis para retry.
