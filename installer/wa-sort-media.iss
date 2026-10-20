; Inno Setup script for WhatsApp Media Suite.
;
; 1. Build the bundle first:  scripts\build.ps1   (produces dist\WhatsApp Media Suite\)
; 2. Compile this file with ISCC.exe (Inno Setup 6).
;
; IMPORTANT: this produces an UNSIGNED installer. For public distribution, sign
; both the app .exe and this installer (signtool.exe) so Windows SmartScreen does
; not scare users away.
;
; Note: the app renders through the Microsoft Edge WebView2 Runtime. It is present
; on most Windows 10/11 machines; the check below warns if it is missing.

#define AppName "WhatsApp Media Suite"
#define AppVersion "0.1.0"
#define AppExe "WhatsApp Media Suite.exe"
#define WebView2Url "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename=WhatsAppMediaSuite-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function WebView2Installed: Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
end;

procedure InitializeWizard;
begin
  if not WebView2Installed then
    MsgBox('Microsoft Edge WebView2 Runtime was not detected. The app needs it to display its window.'
      + #13#10 + 'Install it from: {#WebView2Url}', mbInformation, MB_OK);
end;
