@echo off
REM ============================================================================
REM GREY BARK ADVISORS - GENERADOR AUTOMATICO DE REPORTES
REM Version: 5.0 ULTIMATE (Enero 2026)
REM 
REM FUNCIONALIDADES:
REM - Auto-deteccion AM/PM segun hora Chile
REM - Captura de datos: Equity, Bonds, FX, Commodities, Newsletters
REM - Generacion de reportes: Finanzas + No Finanzas
REM - Conversion HTML profesional
REM - Envio automatico por email con base de datos de clientes
REM - Sistema de logs completo
REM ============================================================================

echo.
echo ============================================================================
echo GREY BARK ADVISORS - SISTEMA DE REPORTES AUTOMATICO
echo ============================================================================
echo.

REM ============================================================================
REM CONFIGURACION
REM ============================================================================

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Crear carpetas necesarias
if not exist "logs" mkdir logs
if not exist "html_out" mkdir html_out
if not exist "history" mkdir history

REM Python executable
set PYTHON=python

REM ============================================================================
REM DETECTAR MODO (AM/PM) SEGUN HORA
REM ============================================================================

REM Extraer hora actual (formato 24h)
for /f "tokens=1-3 delims=:" %%a in ("%time%") do (
    set HORA=%%a
    set MINUTO=%%b
)

REM Eliminar espacios en blanco (si la hora es < 10)
set HORA=%HORA: =%

REM Determinar modo
if %HORA% LSS 14 (
    set MODE=AM
    set MODE_LABEL=Apertura de Mercados
    set EMOJI=🌅
) else (
    set MODE=PM
    set MODE_LABEL=Cierre de Mercados
    set EMOJI=🌆
)

REM Registrar inicio
echo ================================================ >> logs\report_log.txt
echo [%date% %time%] Iniciando proceso %MODE% >> logs\report_log.txt
echo ================================================ >> logs\report_log.txt

echo [MODO DETECTADO] %MODE% - %MODE_LABEL%
echo [HORA ACTUAL] %time%
echo [DIRECTORIO] %cd%
echo.

REM ============================================================================
REM PASO 0: DESCARGA WSJ PRINT EDITION PDF (OPCIONAL)
REM ============================================================================

echo ============================================================================
echo PASO 0: DESCARGANDO WSJ PRINT EDITION PDF 📰
echo ============================================================================
echo.

echo [%date% %time%] PASO 0: Descargando WSJ PDF... >> logs\report_log.txt

%PYTHON% download_wsj_pdf.py >> logs\wsj_download.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] WARN: No se pudo descargar WSJ PDF >> logs\report_log.txt
    echo [WARN] No se pudo descargar el WSJ PDF - continuando sin el...
) else (
    echo [%date% %time%] WSJ PDF descargado OK >> logs\report_log.txt
    echo [OK] WSJ PDF descargado exitosamente
)

echo.

REM ============================================================================
REM PASO 1: CAPTURA DE DATOS
REM ============================================================================

echo ============================================================================
echo PASO 1/5: CAPTURANDO DATOS DE MERCADOS %EMOJI%
echo ============================================================================
echo.
echo Recopilando datos de:
echo   - Equity: S^&P 500, NASDAQ, Dow Jones, indices globales
echo   - Chile: IPSA ^(BCCh + Yahoo^), USD/CLP
echo   - Renta Fija: Treasuries 2Y/10Y/30Y, AGG, HYG, VIX
echo   - Commodities: Oro, Plata, Cobre, Petroleo WTI
echo   - Sentiment: Sectores AlphaVantage
echo   - Newsletters: WSJ, FT, DF Primer Click
echo.
echo Ventana de busqueda:
if "%MODE%"=="AM" (
    echo   AM: 19:00 ^(ayer^) --^> 10:00 ^(hoy^)
) else (
    echo   PM: 10:00 ^(hoy^) --^> 20:00 ^(hoy^)
)
echo.

echo [%date% %time%] PASO 1: Capturando datos %MODE%... >> logs\report_log.txt

%PYTHON% daily_market_snapshot.py %MODE% >> logs\snapshot_%MODE%.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo captura de datos >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al capturar datos
    echo Ver: logs\snapshot_%MODE%.log
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] Datos capturados OK >> logs\report_log.txt
echo [OK] Datos capturados exitosamente
echo [OK] Historial guardado en history\
echo.

REM ============================================================================
REM PASO 2: GENERACION DE REPORTES MARKDOWN
REM ============================================================================

echo ============================================================================
echo PASO 2/5: GENERANDO REPORTES MARKDOWN 📝
echo ============================================================================
echo.
echo Generando 2 versiones:
echo   1. Reporte Profesional (gestores, AFPs, institucionales)
echo   2. Reporte General (clientes, inversionistas individuales)
echo.
echo Estructura:
echo   - Dashboard compacto con sentiment sectorial
echo   - Resumen ejecutivo
echo   - Analisis por activos
echo   - Tablas detalladas al final
echo.

echo [%date% %time%] PASO 2: Generando reportes MD... >> logs\report_log.txt

REM Usar daily_market_snapshot.json (el archivo principal, sin sufijo)
%PYTHON% generate_daily_report.py daily_market_snapshot.json %MODE% >> logs\generate_%MODE%.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo generacion reportes >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al generar reportes
    echo Ver: logs\generate_%MODE%.log
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] Reportes MD generados OK >> logs\report_log.txt
echo [OK] Reportes markdown generados
echo.

REM ============================================================================
REM PASO 3: CONVERSION A HTML
REM ============================================================================

echo ============================================================================
echo PASO 3/5: CONVIRTIENDO A HTML PROFESIONAL 🎨
echo ============================================================================
echo.
echo Generando HTML con:
echo   - Dashboard visual compacto
echo   - Tablas profesionales con fuentes pequenas
echo   - Colores para cambios positivos/negativos
echo   - Logo Grey Bark Advisors
echo   - Compatible con Gmail, Outlook, Apple Mail
echo.

echo [%date% %time%] PASO 3: Convirtiendo a HTML... >> logs\report_log.txt

%PYTHON% html_formatter.py >> logs\html_formatter_%MODE%.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: Fallo conversion HTML >> logs\report_log.txt
    echo.
    echo ========================================
    echo ERROR: Fallo al convertir a HTML
    echo Ver: logs\html_formatter_%MODE%.log
    echo ========================================
    pause
    exit /b 1
)

echo [%date% %time%] HTML generados OK >> logs\report_log.txt
echo [OK] Archivos HTML generados en html_out\
echo.

REM ============================================================================
REM PASO 4: ENVIO DE EMAILS
REM ============================================================================

echo ============================================================================
echo PASO 4/5: ENVIANDO REPORTES POR EMAIL 📧
echo ============================================================================
echo.
echo Sistema de distribucion:
echo   - Base de datos de clientes ^(clients_database.json^)
echo   - Segmentacion automatica por audiencia
echo   - Tracking de envios
echo.

echo [%date% %time%] PASO 4: Enviando emails... >> logs\report_log.txt

REM Enviar reporte profesional
echo Enviando reporte PROFESIONAL...
%PYTHON% send_email_report_improved.py %MODE%_pro >> logs\email_%MODE%.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ADVERTENCIA: Fallo envio reporte PRO >> logs\report_log.txt
    echo [WARN] Error al enviar reporte profesional
) else (
    echo [OK] Reporte profesional enviado
)

REM Enviar reporte general
echo Enviando reporte GENERAL...
%PYTHON% send_email_report_improved.py %MODE%_general >> logs\email_%MODE%.log 2>&1

if %errorlevel% neq 0 (
    echo [%date% %time%] ADVERTENCIA: Fallo envio reporte GENERAL >> logs\report_log.txt
    echo [WARN] Error al enviar reporte general
) else (
    echo [OK] Reporte general enviado
)

echo [%date% %time%] Proceso de emails completado >> logs\report_log.txt

echo.

REM ============================================================================
REM PASO 5: ARCHIVAR REPORTES GENERADOS
REM ============================================================================

echo ============================================================================
echo PASO 5/5: ARCHIVANDO REPORTES 📁
echo ============================================================================
echo.

if not exist "archivo_reportes\md" mkdir "archivo_reportes\md"
if not exist "archivo_reportes\html" mkdir "archivo_reportes\html"

REM Mover archivos .md del dia a archivo_reportes/md/
set MD_MOVED=0
for %%f in (daily_report_%MODE%_*.md) do (
    move "%%f" "archivo_reportes\md\" >nul 2>&1
    if not errorlevel 1 set /a MD_MOVED+=1
)

REM Mover archivos .html del dia a archivo_reportes/html/
set HTML_MOVED=0
for %%f in (html_out\daily_report_%MODE%_*.html) do (
    move "%%f" "archivo_reportes\html\" >nul 2>&1
    if not errorlevel 1 set /a HTML_MOVED+=1
)

echo [OK] Archivados: %MD_MOVED% archivos MD, %HTML_MOVED% archivos HTML
echo   - MD:   archivo_reportes\md\
echo   - HTML: archivo_reportes\html\
echo [%date% %time%] Archivados %MD_MOVED% MD y %HTML_MOVED% HTML >> logs\report_log.txt

echo.

REM ============================================================================
REM RESUMEN FINAL
REM ============================================================================

echo [%date% %time%] Proceso %MODE% completado >> logs\report_log.txt
echo. >> logs\report_log.txt

echo ============================================================================
echo PROCESO COMPLETADO EXITOSAMENTE ✅
echo ============================================================================
echo Fin: %date% %time%
echo.

echo [ARCHIVOS GENERADOS]
echo.
echo Reportes Markdown:
for %%f in (daily_report_%MODE%_*.md) do (
    if not "%%f"=="daily_report_%MODE%_*_1.md" (
        echo   - %%f
    )
)

echo.
echo Reportes HTML:
for %%f in (html_out\daily_report_%MODE%_*.html) do (
    echo   - %%f
)

echo.
echo [ESTADISTICAS]
echo - Costo estimado: ~$0.28 USD
echo - Destinatarios: Ver clients_database.json
echo - Logs detallados: logs\
echo.

echo [SIGUIENTE PASO]
echo Los archivos HTML estan listos para distribucion
echo Ubicacion: %cd%\html_out\
echo.

REM ============================================================================
REM OPCIONES POST-EJECUCION
REM ============================================================================

echo ============================================================================
echo Presiona cualquier tecla para finalizar...
echo ============================================================================

REM NO hacer pause si ejecutado por Task Scheduler (automatico)
REM Para testing manual, descomentar la siguiente linea:
REM pause

exit /b 0
