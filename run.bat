@echo off
title Earnings Call NLP Pipeline
color 0A

echo.
echo  =====================================================
echo    EARNINGS CALL NLP PIPELINE - Iniciando...
echo  =====================================================
echo.

:: Lanzar el servidor en segundo plano en una nueva ventana
echo  [1/2] Arrancando servidor FastAPI (puerto 8085)...
start "NLP Server" venv\Scripts\python.exe server.py

echo  [2/2] Esperando a que el servidor levante...
echo.

:: Esperar hasta 30 segundos a que el servidor responda
set /a intentos=0

:LOOP
ping localhost -n 2 > nul
curl -s http://localhost:8085 > nul 2>&1
if %ERRORLEVEL% == 0 goto OPEN
set /a intentos+=1
if %intentos% GEQ 15 goto TIMEOUT
echo        Esperando... (%intentos%/15)
goto LOOP

:OPEN
echo.
echo  Servidor listo! Abriendo el navegador...
start http://localhost:8085
echo.
echo  Dashboard disponible en: http://localhost:8085
echo  Cierra la ventana "NLP Server" para detener la aplicacion.
echo.
goto END

:TIMEOUT
echo.
echo  AVISO: El servidor tarda mas de lo esperado.
echo  Abriendo el navegador de todas formas...
start http://localhost:8085
echo.

:END
pause
