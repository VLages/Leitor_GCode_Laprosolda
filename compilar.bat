@echo off
echo ===================================================
echo     COMPILANDO: Leitor_GCode_Laprosolda
echo     Isso pode levar alguns minutos...
echo ===================================================
echo.

:: 1. Executa o PyInstaller definindo o nome e o ICONE
C:\Users\Vitor\AppData\Local\Programs\Python\Python313\python.exe -m PyInstaller --noconsole --onefile --hidden-import PyQt5 --hidden-import OpenGL -n Leitor_GCode_Laprosolda --icon=icone.ico mainGL.py

:: 2. Move o executavel pronto para a pasta raiz do projeto
echo.
echo ===================================================
echo     ORGANIZANDO OS ARQUIVOS...
echo ===================================================
move dist\Leitor_GCode_Laprosolda.exe .\Leitor_GCode_Laprosolda.exe

:: 3. Limpa os rastros da compilacao
rmdir /s /q build
rmdir /s /q dist
del Leitor_GCode_Laprosolda.spec

echo.
echo ===================================================
echo     SUCESSO! O Leitor_GCode_Laprosolda.exe esta pronto.
echo ===================================================
pause