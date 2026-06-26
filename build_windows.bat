@echo off
setlocal EnableDelayedExpansion
echo.
echo  PDF Manager Pro - CCV / Camara de Comercio de Valledupar
echo  ============================================================
echo  Compilando ejecutable con icono institucional...
echo.

:: ── [1/5] Dependencias Python ────────────────────────────────────────────────
echo  [1/5] Instalando dependencias Python...
pip install pypdf pillow pyinstaller reportlab requests --quiet
if errorlevel 1 (
    echo  ERROR: Fallo instalando dependencias.
    pause & exit /b 1
)
echo       Dependencias instaladas correctamente.
echo.

:: ── [2/5] Verificar Ghostscript ──────────────────────────────────────────────
echo  [2/5] Verificando Ghostscript...
where gswin64c >nul 2>&1
if not errorlevel 1 (
    echo       Ghostscript detectado en PATH.
    goto :prep_dist
)
set GS_BIN=
for /d %%D in ("C:\Program Files\gs\gs*") do (
    if exist "%%D\bin\gswin64c.exe" set GS_BIN=%%D\bin
)
if defined GS_BIN (
    echo       Ghostscript encontrado en: %GS_BIN%
    set PATH=%PATH%;%GS_BIN%
    goto :prep_dist
)
echo  ADVERTENCIA: Ghostscript no encontrado.
echo  La compresion de imagenes no estara disponible en esta sesion.
echo  El instalador ofrece instalarlo al usuario final.
echo.

:prep_dist
:: ── [3/5] Preparar archivos de distribucion ──────────────────────────────────
echo  [3/5] Preparando archivos de distribucion...

:: Crear carpeta redist si no existe
if not exist "redist" mkdir redist

:: Copiar instalador de Ghostscript a redist\
if exist "gs10071w64.exe" (
    copy /Y "gs10071w64.exe" "redist\gs_setup.exe" >nul
    echo       gs10071w64.exe copiado a redist\gs_setup.exe
) else (
    echo  ADVERTENCIA: gs10071w64.exe no encontrado en esta carpeta.
    echo  El instalador de Ghostscript NO se incluira en el paquete de instalacion.
    echo  Coloca gs10071w64.exe junto a este .bat y vuelve a ejecutar.
)

:: Crear version.json (Python maneja el encoding correctamente)
python -c "import json; open('version.json','w').write(json.dumps({'version':'1.0.0'}, indent=2))"
echo       version.json creado.
echo.

:compile
:: ── [4/5] Compilar ejecutable con PyInstaller ────────────────────────────────
echo  [4/5] Compilando ejecutable...

if not exist "ccv_icon.ico" (
    echo  ADVERTENCIA: ccv_icon.ico no encontrado en esta carpeta.
    echo  Compilando sin icono personalizado...
    pyinstaller --onefile --windowed ^
        --name "PDF Manager Pro - CCV" ^
        --add-data "updater.py;." ^
        pdf_manager.py
) else (
    pyinstaller --onefile --windowed ^
        --icon="ccv_icon.ico" ^
        --name "PDF Manager Pro - CCV" ^
        --add-data "updater.py;." ^
        pdf_manager.py
)

if errorlevel 1 (
    echo  ERROR: Fallo la compilacion con PyInstaller.
    pause & exit /b 1
)

:: ── Limpieza de archivos temporales de PyInstaller ───────────────────────────
echo.
echo  Limpiando temporales...
if exist "PDF Manager Pro - CCV.spec" del /q "PDF Manager Pro - CCV.spec"
if exist "build" rmdir /s /q build

echo.

:: ── [5/5] Instrucciones post-compilacion ─────────────────────────────────────
echo  [5/5] Compilacion completada exitosamente.
echo.
echo  ============================================================
echo   Archivos generados:
echo     dist\PDF Manager Pro - CCV.exe   ^<-- ejecutable final
echo     redist\gs_setup.exe              ^<-- redistribuible Ghostscript
echo     version.json                     ^<-- numero de version
echo.
echo   SIGUIENTE PASO — Compilar el instalador con Inno Setup 6:
echo.
echo   Opcion A (linea de comandos):
echo     "C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
echo.
echo   Opcion B (interfaz grafica):
echo     1. Abre Inno Setup IDE
echo     2. Archivo > Abrir > selecciona installer.iss
echo     3. Presiona F9 para compilar
echo.
echo   El instalador se generara en:
echo     installer_output\PDFManagerPro_Setup_1.0.0.exe
echo.
echo   Si no tienes Inno Setup 6, descargalo en:
echo     jrsoftware.org/isinfo.php  (gratuito)
echo  ============================================================
echo.
pause
