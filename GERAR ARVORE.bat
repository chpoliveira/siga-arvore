@echo off
rem -------------------------------------------------------
rem PREMISSAS ATIVAS:
rem 1. Objetivo: rodar src\arvore_df.py sem abrir o cmd na mao
rem 2. Constraint: arrastar um ou mais YAML sobre o .bat gera so esses; duplo clique gera todos os YAML de out\
rem 3. Stack: Windows 11 batch + Python (py launcher ou python no PATH)
rem 4. Teste: NAO TESTADO
rem -------------------------------------------------------
chcp 65001 >nul
setlocal
set "RAIZ=%~dp0"
set "PY=python"
where py >nul 2>&1 && set "PY=py"

if not "%~1"=="" (
  for %%F in (%*) do (
    %PY% "%RAIZ%src\arvore_df.py" "%%~fF"
    if exist "%%~dpnF.html" start "" "%%~dpnF.html"
  )
) else (
  for %%F in ("%RAIZ%out\*.yaml") do (
    %PY% "%RAIZ%src\arvore_df.py" "%%~fF"
  )
  start "" "%RAIZ%out"
)

echo.
pause
