@echo off
REM ============================================================================
REM GREY BARK ADVISORS - GENERADOR DE REPORTE SEMANAL
REM ============================================================================

echo.
echo ============================================================================
echo GREY BARK ADVISORS - REPORTE SEMANAL
echo ============================================================================
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Crear carpetas necesarias
if not exist "logs" mkdir logs
if not exist "html_out" mkdir html_out

REM Python executable
set PYTHON=python

echo [INFO] Generando reporte semanal...
echo [INFO] Analizando snapshots de la semana...
echo.

%PYTHON% generate_weekly_report.py >> logs\weekly_report.log 2>&1

if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo ERROR: Fallo al generar reporte semanal
    echo Ver: logs\weekly_report.log
    echo ========================================
    pause
    exit /b 1
)

echo [OK] Reporte semanal generado exitosamente
echo.

echo [ARCHIVOS GENERADOS]
for %%f in (weekly_report_semana_*.md) do (
    echo   - %%f
)
echo.

echo ============================================================================
echo Presiona cualquier tecla para finalizar...
echo ============================================================================
pause

exit /b 0
