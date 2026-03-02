@echo off
REM ============================================
REM Daily Market Report - AM Edition COMPLETO
REM Ejecuta a las 8:15 AM
REM 1. Recopila datos
REM 2. Genera reportes MD (finanzas + no_finanzas)
REM 3. Convierte a HTML
REM 4. Envia por email (NUEVO SISTEMA con DB)
REM ============================================

REM Cambiar al directorio donde estan los scripts
cd /d "%~dp0"

REM Crear carpeta de logs si no existe
if not exist "logs" mkdir logs

REM Registrar inicio de ejecucion
echo ================================================ >> logs\report_log.txt
echo [%date% %time%] Iniciando proceso AM COMPLETO >> logs\report_log.txt
echo ================================================ >> logs\report_log.txt

echo.
echo ========================================
echo GREY BARK ADVISORS - REPORTE AM
echo ========================================
echo Inicio: %date% %time%
echo ========================================
echo.

REM ============================================
REM PASO 1: Recopilar datos de mercados
REM ============================================
echo [%date% %time%] PASO 1: Recopilando datos... >> logs\report_log.txt
echo [1/4] RECOPILANDO DATOS DE MERCADOS...
echo.
python daily_market_snapshot.py AM >> logs\snapshot_AM.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo al recopilar datos >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al recopilar datos
    echo Ver logs\snapshot_AM.log para detalles
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] Datos recopilados OK >> logs\report_log.txt
echo       [OK] Datos recopilados exitosamente
echo       [OK] Historial guardado en history\
echo.

REM ============================================
REM PASO 2: Generar reportes markdown
REM ============================================
echo [%date% %time%] PASO 2: Generando reportes MD... >> logs\report_log.txt
echo [2/4] GENERANDO REPORTES MARKDOWN...
echo       - Reporte para Profesionales
echo       - Reporte para Cliente General
echo.
python generate_daily_report.py AM >> logs\generate_AM.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo al generar reportes >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al generar reportes
    echo Ver logs\generate_AM.log para detalles
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] Reportes MD generados OK >> logs\report_log.txt
echo       [OK] Reportes markdown generados
echo.

REM ============================================
REM PASO 3: Convertir a HTML
REM ============================================
echo [%date% %time%] PASO 3: Convirtiendo a HTML... >> logs\report_log.txt
echo [3/4] CONVIRTIENDO REPORTES A HTML...
echo.
python html_formatter.py >> logs\html_formatter_AM.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo al convertir HTML >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al convertir a HTML
    echo Ver logs\html_formatter_AM.log para detalles
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] HTML generados OK >> logs\report_log.txt
echo       [OK] Reportes HTML generados
echo.

REM ============================================
REM PASO 4: Enviar emails (NUEVO SISTEMA)
REM ============================================
echo [%date% %time%] PASO 4: Enviando emails... >> logs\report_log.txt
echo [4/4] ENVIANDO REPORTES POR EMAIL...
echo       Usando sistema de base de datos de clientes
echo.
python send_email_v2.py auto >> logs\email_AM.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ADVERTENCIA: Fallo al enviar emails >> logs\report_log.txt
    echo       [WARN] Error al enviar emails (ver logs\email_AM.log)
) else (
    echo [%date% %time%] Emails enviados OK >> logs\report_log.txt
    echo       [OK] Reportes AM enviados a destinatarios
)

REM ============================================
REM Resumen final
REM ============================================
echo.
echo [%date% %time%] Proceso AM completado >> logs\report_log.txt
echo. >> logs\report_log.txt

echo ========================================
echo PROCESO AM COMPLETADO
echo ========================================
echo Fin: %date% %time%
echo.
echo Archivos generados:
for %%f in (daily_report_AM_*.md) do (
    echo   MD:   %%f
)
for %%f in (html_out\daily_report_AM_*.html) do (
    echo   HTML: %%f
)
echo.
echo Destinatarios: Ver clients_database.json
echo Dashboard: http://localhost:5000
echo Ver carpeta logs\ para detalles
echo ========================================
echo.

REM NO hacer pause para que Task Scheduler funcione automaticamente
REM Si quieres probarlo manualmente, descomenta la linea siguiente:
REM pause

exit /b 0
