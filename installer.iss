; ============================================================
;  Inno Setup 6 — PDF Manager Pro
;  Cámara de Comercio de Valledupar
;
;  Para compilar:
;    "C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
;  O desde el IDE de Inno Setup (abrir este archivo y presionar F9)
; ============================================================

#define AppName      "PDF Manager Pro"
#define AppVersion   "1.1.3"
#define AppPublisher "Cámara de Comercio de Valledupar"
#define AppURL       "https://ccvalledupar.org.co"
#define AppExeName   "PDF Manager Pro - CCV.exe"

[Setup]
; NOTA: Genera un nuevo GUID con: [guid]::NewGuid() en PowerShell
;       y reemplaza el valor de AppId antes de distribuir.
AppId={{B7E1A2F3-C4D5-4E6F-A7B8-C9D0E1F2A3B4}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; Directorio de instalación
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; Salida
OutputDir=installer_output
OutputBaseFilename=PDFManagerPro_Setup_{#AppVersion}
SetupIconFile=ccv_icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; Compresión
Compression=lzma2
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Arquitectura — solo 64 bits
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Requiere privilegios de administrador (necesario para instalar en Program Files
; y para que Ghostscript pueda instalarse)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Apariencia del asistente
WizardStyle=modern
WizardSizePercent=110

; Licencia (opcional — descomenta y crea el archivo si tienes una)
; LicenseFile=LICENSE.txt

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; \
    Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; \
    Flags: unchecked

[Files]
; Ejecutable principal
Source: "dist\{#AppExeName}"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; Icono institucional (para el acceso directo y propiedades)
Source: "ccv_icon.ico"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; Instalador de Ghostscript — se extrae a una carpeta temporal y se borra al terminar.
; El usuario verá la ventana de instalación normal de Ghostscript (no silenciosa,
; requerido por la licencia GPL de Ghostscript 10.x).
Source: "redist\gs_setup.exe"; \
    DestDir: "{tmp}"; \
    Flags: deleteafterinstall

[Icons]
; Menú Inicio
Name: "{group}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\ccv_icon.ico"

Name: "{group}\{cm:UninstallProgram,{#AppName}}"; \
    Filename: "{uninstallexe}"

; Escritorio (solo si el usuario marcó la tarea)
Name: "{autodesktop}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\ccv_icon.ico"; \
    Tasks: desktopicon

[Run]
; Ofrecer instalar Ghostscript al finalizar (solo si no está ya instalado).
; waituntilterminated: espera a que el instalador de GS termine antes de cerrar el Setup.
; skipifsilent: no se ejecuta en instalaciones silenciosas (/SILENT /VERYSILENT).
; postinstall: aparece como checkbox en la página de finalización del asistente.
Filename: "{tmp}\gs_setup.exe"; \
    Description: "Instalar Ghostscript 10 (recomendado para comprimir imágenes en PDFs)"; \
    Flags: postinstall waituntilterminated skipifsilent; \
    Check: NeedsGhostscript

[Code]
// ─── Detección de Ghostscript ───────────────────────────────────────────────
// Ghostscript 10.x se registra bajo HKLM\SOFTWARE\GPL Ghostscript\{version}.
// Como el instalador corre en modo 64-bit (ArchitecturesInstallIn64BitMode),
// HKLM aquí apunta al hive de 64 bits — donde GS escribe su entrada.

function GhostscriptInstalled(): Boolean;
var
  SubKeys: TArrayOfString;
begin
  Result := RegGetSubkeyNames(HKLM, 'SOFTWARE\GPL Ghostscript', SubKeys)
            and (GetArrayLength(SubKeys) > 0);
end;

function NeedsGhostscript(): Boolean;
begin
  Result := not GhostscriptInstalled();
end;
