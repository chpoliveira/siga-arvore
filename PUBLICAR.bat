@echo off
rem -------------------------------------------------------
rem PREMISSAS ATIVAS:
rem 1. Objetivo: publicar os HTML de out\ no GitHub Pages (pasta docs\ do repo), com um duplo clique
rem 2. Constraint: repo publico chpoliveira/siga-arvore criado no GitHub; Pages com Source "Deploy from a branch", branch main, pasta /docs
rem 3. Stack: Windows 11 batch + Git para Windows logado no GitHub
rem 4. Teste: NAO TESTADO
rem -------------------------------------------------------
chcp 65001 >nul
setlocal
set "RAIZ=%~dp0"
set "REPO=https://github.com/chpoliveira/siga-arvore.git"
set "PAGES=https://chpoliveira.github.io/siga-arvore/"
cd /d "%RAIZ%"

where git >nul 2>&1 || (echo Git nao encontrado no PATH. Instale o Git para Windows. & pause & exit /b 1)

if not exist ".git" (
  echo Primeira publicacao: iniciando o repositorio local...
  git init -b main
  git remote add origin "%REPO%"
)

if not exist "docs" mkdir "docs"
copy /y "out\*.html" "docs\" >nul
for %%F in ("out\*.html") do set "ULTIMO=%%~nxF"
copy /y "out\%ULTIMO%" "docs\index.html" >nul

git add -A
git commit -m "Publica arvore %date% %time%" >nul 2>&1
if errorlevel 1 echo Nada novo para publicar.
git push -u origin main
if errorlevel 1 (
  echo.
  echo Falha no push. Confira se o repositorio existe em %REPO% e se o Git esta logado.
  pause & exit /b 1
)

echo.
echo Publicado. Em cerca de 1 minuto a pagina estara em:
echo   %PAGES%
echo.
pause
