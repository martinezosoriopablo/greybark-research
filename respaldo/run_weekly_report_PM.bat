@echo off
REM ============================================
REM GREYBARK – INFORME SEMANAL PM (VIERNES)
REM ============================================

REM Ajusta este path si cambias la carpeta base
SET BASE_DIR=C:\Users\I7 8700\OneDrive\Documentos\proyectos
SET PYTHON_EXE=python

cd /d "%BASE_DIR%"

echo ============================================
echo INICIO INFORME SEMANAL GREYBARK - %DATE% %TIME%
echo ============================================

REM --------------------------------------------
REM 1) Generar informe semanal – VERSION PRO
REM --------------------------------------------
echo Generando informe semanal PRO...
%PYTHON_EXE% generate_weekly_report.py finanzas
IF ERRORLEVEL 1 (
    echo ERROR generando weekly PRO
    goto :END
)

REM --------------------------------------------
REM 2) Generar informe semanal – VERSION NO FINANZAS
REM --------------------------------------------
echo Generando informe semanal NO FINANZAS...
%PYTHON_EXE% generate_weekly_report.py no_finanzas
IF ERRORLEVEL 1 (
    echo ERROR generando weekly NO FINANZAS
    goto :END
)

REM --------------------------------------------
REM 3) Convertir Markdown -> HTML
REM --------------------------------------------
echo Convirtiendo informes semanales a HTML...
%PYTHON_EXE% html_formatter_weekly.py
IF ERRORLEVEL 1 (
    echo ERROR en conversion HTML semanal
    goto :END
)

REM --------------------------------------------
REM 4) Enviar correos – VERSION PRO
REM --------------------------------------------
echo Enviando correo semanal PRO...
%PYTHON_EXE% send_email_weekly.py finanzas
IF ERRORLEVEL 1 (
    echo ERROR enviando correo semanal PRO
    goto :END
)

REM --------------------------------------------
REM 5) Enviar correos – VERSION NO FINANZAS
REM --------------------------------------------
echo Enviando correo semanal NO FINANZAS...
%PYTHON_EXE% send_email_weekly.py no_finanzas
IF ERRORLEVEL 1 (
    echo ERROR enviando correo semanal NO FINANZAS
    goto :END
)

:END
echo ============================================
echo FIN INFORME SEMANAL GREYBARK - %DATE% %TIME%
echo ============================================

pause
