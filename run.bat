@echo off
setlocal
rem Bu dosyanin bulundugu klasore gec (bosluklu yollar icin tirnakli).
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py -3"
where wt.exe >nul 2>nul
if errorlevel 1 (
  echo Windows Terminal bulunamadi, mevcut konsolda calistiriliyor...
  %PY% main.py
  goto :end
)
rem "%CD%." : sonuna nokta eklemek, kok dizinde "C:\" + kapanis tirnagi (ters bolu tuzagi) sorununu onler.
wt.exe -w new --size 125,38 -d "%CD%." %PY% main.py
:end
endlocal
