@echo off
echo ============================================
echo GREYBARK RESEARCH - PIPELINE MENSUAL
echo ============================================
echo.
echo Verificando prerequisitos...
echo.

cd /d "C:\Users\I7 8700\onedrive\documentos\wealth\estructuras\consejo_ia"

REM Verificar que Python existe
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado en PATH
    pause
    exit /b 1
)

REM Verificar que hay research files
dir input\research\*.txt >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] No hay archivos de research en input\research\
    echo Coloque los extractos de research antes de continuar.
    echo.
) else (
    echo [OK] Research files encontrados
)

REM Verificar user_directives
if exist input\user_directives.txt (
    echo [OK] user_directives.txt encontrado
) else (
    echo [ADVERTENCIA] No hay user_directives.txt
)

REM Verificar API key
if defined ANTHROPIC_API_KEY (
    echo [OK] ANTHROPIC_API_KEY configurada
) else (
    echo [ADVERTENCIA] ANTHROPIC_API_KEY no esta definida como variable de entorno
    echo El pipeline intentara leerla del archivo de config.
)

echo.
echo Iniciando pipeline...
echo.

python run_monthly.py %*

echo.
echo Pipeline completado.
pause
