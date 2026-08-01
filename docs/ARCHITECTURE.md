# Arquitetura

## Componentes

- `app/main.py`: ciclo de vida, workers Telegram e FTPS;
- `app/ftp/server.py`: protocolo FTP e upgrade TLS;
- `app/ftp/pathio.py`: sistema de arquivos virtual e staging;
- `app/ftp/repositories.py`: catálogo, usuários, partes e jobs no SQL Server;
- `app/ftp/staging_space.py`: liberação progressiva de clusters no Windows;
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

