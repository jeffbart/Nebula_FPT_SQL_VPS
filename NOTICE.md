# Créditos e origem

`Nebula_FPT_SQL_VPS` é uma vertente independente de
[`jeffbart/NebulaFTP`](https://github.com/jeffbart/NebulaFTP), mantida por
Jefferson.

O NebulaFTP foi criado originalmente por Samuel de Sousa Santos a partir de
componentes cuja licença preservada neste repositório atribui copyright a
RuslanUC. Esta distribuição mantém a licença MIT original em `LICENSE`.

Principais alterações desta vertente:

- Microsoft SQL Server para catálogo e usuários;
- FTPS explícito com TLS 1.2 ou superior;
- senhas protegidas com bcrypt;
- execução nativa em Windows VPS;
- persistência e recuperação de uploads multipartes;
- exclusão das mensagens correspondentes no Telegram;
- liberação progressiva do espaço físico do staging em volumes compatíveis.

Esta vertente não é uma versão oficial dos autores dos projetos de origem.
