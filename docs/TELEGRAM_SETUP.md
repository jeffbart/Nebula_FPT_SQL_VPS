# Configuração do Telegram

O NebulaFTP usa uma aplicação Telegram, um bot e um canal privado. O bot envia
as partes dos arquivos, recupera-as para download e apaga as mensagens quando o
arquivo é excluído pelo FTPS.

## 1. Criar `API_ID` e `API_HASH`

1. Acesse `https://my.telegram.org` com a conta reservada para o projeto.
2. Informe o telefone e confirme o código recebido no Telegram.
3. Abra **API development tools**.
4. Crie uma aplicação, por exemplo:
   - App title: `NebulaFTP`;
   - Short name: `nebulaftp`;
   - Platform: `Desktop` ou `Other`.
5. Guarde `api_id` e `api_hash`.

Configure-os depois como `API_ID` e `API_HASH`. O `API_HASH` é secreto.

## 2. Criar o bot no BotFather

1. Abra a conversa oficial `@BotFather`.
2. Envie `/newbot`.
3. Defina o nome exibido, por exemplo `Nebula FTP Storage`.
4. Defina um username único terminado em `bot`, por exemplo
   `meu_nebulaftp_bot`.
5. Copie o token entregue pelo BotFather.

O token será `BOT_TOKEN`. Ele concede controle do bot e deve ser tratado como
senha. Se for exposto, revogue-o no BotFather e gere outro.

## 3. Criar o canal privado

No Telegram:

1. Selecione **Novo canal**.
2. Use um nome como `NebulaFTP Storage`.
3. Escolha **Canal privado**.
4. Não publique links ou credenciais do projeto na descrição.

É recomendável usar um canal exclusivo para esta instalação.

## 4. Adicionar o bot como administrador

No canal, abra **Gerenciar canal > Administradores > Adicionar administrador**
e selecione o bot.

Conceda pelo menos as permissões necessárias para:

- publicar mensagens/documentos;
- apagar mensagens.

A permissão de apagar é obrigatória para exclusão de partes e rollback de
uploads incompletos.

## 5. Obter o `CHAT_ID`

Depois de adicionar o bot como administrador:

1. publique uma nova mensagem no canal;
2. execute, pela raiz do projeto:

```bat
telegram_obter_chat_id.bat
```

O utilitário lê `BOT_TOKEN` de `config\.env`. Se ele ainda não estiver
preenchido, solicita o token com entrada oculta. Como alternativa, a consulta
pode ser feita manualmente pelo PowerShell:

```powershell
$botToken = Read-Host "Token do bot"
$updates = Invoke-RestMethod `
  -Uri "https://api.telegram.org/bot$botToken/getUpdates"

$updates.result |
  ForEach-Object { $_.channel_post.chat } |
  Where-Object { $_ } |
  Select-Object id, title, type -Unique

Remove-Variable botToken
```

O ID de canal normalmente é negativo e começa com `-100`, por exemplo:

```text
-1001234567890
```

Se não aparecer resultado, publique outra mensagem depois que o bot já estiver
como administrador e execute novamente.

Não cole o token em prints, issues ou arquivos versionados.

## 6. Testar o token

Depois de preencher `BOT_TOKEN` e `CHAT_ID`, execute na raiz:

```bat
telegram_testar.bat
```

O teste valida o token e o acesso ao canal, envia uma mensagem silenciosa e a
apaga imediatamente. Assim, confirma as duas permissões usadas pelo NebulaFTP.
Se a exclusão falhar, o programa informa o ID da mensagem que pode ter ficado
no canal.

Para testar somente o token manualmente:

```powershell
$botToken = Read-Host "Token do bot"
Invoke-RestMethod `
  -Uri "https://api.telegram.org/bot$botToken/getMe" |
  Select-Object -ExpandProperty result
Remove-Variable botToken
```

O resultado deve mostrar o username do bot e `is_bot` igual a `True`.

## 7. Preencher o `.env`

Edite somente o arquivo privado `config\.env`:

```dotenv
API_ID=12345678
API_HASH=SUBSTITUA_PELO_API_HASH
BOT_TOKEN=SUBSTITUA_PELO_TOKEN_DO_BOT
CHAT_ID=-1001234567890
```

Não altere o exemplo público com valores reais. O `.gitignore` impede o envio
de `config\.env`, mas confirme antes de cada commit.

## 8. Validar pelo NebulaFTP

Ao iniciar `iniciar_nebulaftp_vps.bat`, o log deve conter uma mensagem semelhante
a:

```text
Canal Telegram validado: NebulaFTP Storage
```

Erros comuns:

- `BOT_TOKEN não configurado`: token ausente no `.env`;
- `CHAT_ID não configurado`: ID do canal ausente;
- `PEER_ID_INVALID`: ID incorreto ou bot sem acesso ao canal;
- `CHAT_ADMIN_REQUIRED`: faltam permissões administrativas;
- falha ao apagar mensagens: conceda permissão para excluir mensagens.

Referências oficiais: `https://core.telegram.org/bots` e
`https://core.telegram.org/bots/tutorial`.
