@echo off
REM ============================================
REM Quantitative Weekly Report - VIERNES 6:00 PM
REM 1. Recopila datos de Alpha Vantage
REM 2. Genera reporte cuantitativo markdown
REM 3. Convierte a HTML
REM 4. Envia por email
REM ============================================

REM Cambiar al directorio donde están los scripts
cd /d "%~dp0"

REM Crear carpeta de logs si no existe
if not exist "logs" mkdir logs

REM Registrar inicio
echo ================================================ >> logs\report_log.txt
echo [%date% %time%] Iniciando REPORTE CUANTITATIVO SEMANAL >> logs\report_log.txt
echo ================================================ >> logs\report_log.txt

echo.
echo ========================================
echo GREY BARK - REPORTE CUANTITATIVO SEMANAL
echo ========================================
echo Inicio: %date% %time%
echo ========================================
echo.

REM ============================================
REM PASO 1: Recopilar datos de Alpha Vantage
REM ============================================
echo [%date% %time%] PASO 1: Recopilando datos Alpha Vantage... >> logs\report_log.txt
echo [1/4] RECOPILANDO DATOS DE ALPHA VANTAGE...
echo       Esto tomara aproximadamente 5 minutos (rate limit)...
echo.
python quantitative_data_collector.py >> logs\quantitative_collector.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo al recopilar datos >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al recopilar datos
    echo Ver logs\quantitative_collector.log
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] Datos recopilados OK >> logs\report_log.txt
echo       [OK] Datos de Alpha Vantage recopilados
echo.

REM ============================================
REM PASO 2: Generar reporte markdown
REM ============================================
echo [%date% %time%] PASO 2: Generando reporte cuantitativo... >> logs\report_log.txt
echo [2/4] GENERANDO REPORTE CUANTITATIVO...
echo.
python generate_quantitative_report.py >> logs\quantitative_generate.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo al generar reporte >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al generar reporte
    echo Ver logs\quantitative_generate.log
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] Reporte generado OK >> logs\report_log.txt
echo       [OK] Reporte markdown generado
echo.

REM ============================================
REM PASO 3: Convertir a HTML
REM ============================================
echo [%date% %time%] PASO 3: Convirtiendo a HTML... >> logs\report_log.txt
echo [3/4] CONVIRTIENDO REPORTE A HTML...
echo.

REM Buscar el archivo markdown más reciente
for /f "delims=" %%i in ('dir /b /o-d quantitative_weekly_report_*.md 2^>nul') do (
    set LATEST_MD=%%i
    goto :found
)
:found

if not defined LATEST_MD (
    echo [%date% %time%] ERROR: No se encontro archivo markdown >> logs\report_log.txt
    echo       [ERROR] No se encontro el archivo markdown
    pause
    exit /b 1
)

echo       Convirtiendo: %LATEST_MD%
python html_formatter_quantitative.py %LATEST_MD% >> logs\quantitative_html.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo conversion HTML >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al convertir a HTML
    echo Ver logs\quantitative_html.log
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] HTML generado OK >> logs\report_log.txt
echo       [OK] Reporte HTML generado
echo.

REM ============================================
REM PASO 4: Enviar email
REM ============================================
echo [%date% %time%] PASO 4: Enviando email... >> logs\report_log.txt
echo [4/4] ENVIANDO REPORTE POR EMAIL...
echo.

python send_quantitative_email.py >> logs\quantitative_email.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ADVERTENCIA: Fallo al enviar email >> logs\report_log.txt
    echo       [WARN] Error al enviar email (ver log)
) else (
    echo [%date% %time%] Email enviado OK >> logs\report_log.txt
    echo       [OK] Email enviado correctamente
)

REM ============================================
REM Resumen final
REM ============================================
echo.
echo [%date% %time%] Reporte cuantitativo semanal completado >> logs\report_log.txt
echo. >> logs\report_log.txt

echo ========================================
echo REPORTE CUANTITATIVO SEMANAL COMPLETADO
echo ========================================
echo Fin: %date% %time%
echo.
echo Archivos generados:
for %%f in (quantitative_weekly_report_*.md) do (
    echo   MD:   %%f
)
for %%f in (html_out\quantitative_weekly_report_*.html) do (
    echo   HTML: %%f
)
echo.
echo Ver carpeta logs\ para detalles
echo ========================================
echo.

REM NO hacer pause para que Task Scheduler funcione
REM pause

exit /b 0
