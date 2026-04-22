@echo off
echo ===================================================
echo     COMPILANDO O SIMULADOR LAPROSOLDA...
echo     Isso pode levar alguns minutos. Aguarde.
echo ===================================================
echo.

:: 1. Executa o PyInstaller
C:\Users\Vitor\AppData\Local\Programs\Python\Python313\python.exe -m PyInstaller --noconsole --onefile --hidden-import PyQt5 --hidden-import OpenGL mainGL.py

:: 2. Move o executavel pronto para a pasta principal (e ja renomeia ele)
echo.
echo ===================================================
echo     ORGANIZANDO OS ARQUIVOS...
echo ===================================================
move dist\mainGL.exe .\Leitor_GCode_Laprosolda.exe

:: 3. Apaga os arquivos e pastas temporarias
rmdir /s /q build
rmdir /s /q dist
del mainGL.spec

echo.
echo ===================================================
echo     SUCESSO! O Leitor_GCode_Laprosolda.exe esta pronto!
echo ===================================================
pause