# Publicação no GitHub

O repositório público planejado é `Nebula_FPT_SQL_VPS`, uma vertente de
`jeffbart/NebulaFTP`.

Antes do primeiro commit, revise [SECURITY.md](SECURITY.md) e confirme que os
segredos estão ignorados. A publicação deve ser feita somente depois dessa
verificação.

Identidade Git sugerida para este repositório:

```powershell
git config user.name "Jefferson"
git config user.email "jefferson_bartalo@hotmail.com"
```

## Procedimento

1. No GitHub, crie `Nebula_FPT_SQL_VPS` vazio, sem README, licença ou
   `.gitignore` automáticos.
2. Na raiz local, configure sua identidade somente para este repositório:

```powershell
git config user.name "Jefferson"
git config user.email "jefferson_bartalo@hotmail.com"
```

3. Preserve o remoto do projeto-base como `upstream` e adicione o novo remoto:

```powershell
git remote rename origin upstream
git remote add origin https://github.com/jeffbart/Nebula_FPT_SQL_VPS.git
git remote -v
```

4. Revise o que será publicado:

```powershell
git status --short
git check-ignore -v config\.env certs\nebulaftp.key data\NebulaFTP.session
git diff --check
```

5. Somente depois da revisão:

```powershell
git add -A
git status --short
git commit -m "Create SQL Server and FTPS Windows VPS variant"
git branch -M main
git push -u origin main
```

Se o GitHub solicitar autenticação via HTTPS, use o navegador/Git Credential
Manager ou um token; não use a senha da conta como senha Git.
