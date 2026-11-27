; Installateur Windows de Vision Sentinel (Inno Setup 6).
; Compilation : packaging\build.bat (ou ISCC.exe packaging\installer.iss) après PyInstaller.
; Installe pour l'utilisateur courant (pas de droits administrateur) dans %LOCALAPPDATA%\Programs.
; Les données restent dans %LOCALAPPDATA%\VisionSentinel (proposées à la suppression à la désinstallation).

#define AppName "Vision Sentinel"
#define AppVersion "1.3.0"
#define AppExe "VisionSentinel.exe"

[Setup]
AppId={{6F2B1C7E-4A3D-4E8B-9C21-5D7A0B3E9F14}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
DefaultDirName={localappdata}\Programs\VisionSentinel
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=VisionSentinel-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
; Plusieurs Go de PyTorch : compression rapide et non « solide » (sinon la création prend des heures)
Compression=lzma2/fast
SolidCompression=no
LZMANumBlockThreads=8
CloseApplications=yes
; Découpage en morceaux de moins de 2 Go (limite des fichiers de « release » GitHub) :
; Setup.exe + Setup-1.bin, Setup-2.bin... à placer dans le même dossier avant de lancer l'installation.
DiskSpanning=yes
DiskSliceSize=1900000000
SlicesPerDisk=1
ShowLanguageDialog=auto

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.WebView2Missing=Le composant Microsoft Edge WebView2 n'a pas été trouvé. Il sert à afficher la fenêtre de Vision Sentinel.%n%nIl est présent sur Windows 11 et la plupart des Windows 10. Sinon, installez-le depuis :%nhttps://go.microsoft.com/fwlink/p/?LinkId=2124703%n%nContinuer l'installation ?
nl.WebView2Missing=Het onderdeel Microsoft Edge WebView2 werd niet gevonden. Het toont het venster van Vision Sentinel.%n%nHet is aanwezig op Windows 11 en de meeste Windows 10-pc's. Installeer het anders via:%nhttps://go.microsoft.com/fwlink/p/?LinkId=2124703%n%nDoorgaan met de installatie?
en.WebView2Missing=The Microsoft Edge WebView2 component was not found. It is used to display the Vision Sentinel window.%n%nIt comes with Windows 11 and most Windows 10 PCs. Otherwise, install it from:%nhttps://go.microsoft.com/fwlink/p/?LinkId=2124703%n%nContinue the installation?
fr.DeleteData=Supprimer aussi les données de Vision Sentinel (caméras, journal, captures, visages enregistrés, réglages) ?%n%n%1%n%nChoisissez « Non » pour les garder en vue d'une réinstallation.
nl.DeleteData=Ook de gegevens van Vision Sentinel verwijderen (camera's, logboek, opnames, geregistreerde gezichten, instellingen)?%n%n%1%n%nKies « Nee » om ze te bewaren voor een herinstallatie.
en.DeleteData=Also delete the Vision Sentinel data (cameras, log, snapshots, registered faces, settings)?%n%n%1%n%nChoose « No » to keep them for a reinstall.
fr.Launch=Lancer Vision Sentinel
nl.Launch=Vision Sentinel starten
en.Launch=Launch Vision Sentinel

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\VisionSentinel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2Key = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2: Boolean;
var
  Version: String;
begin
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\' + WebView2Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM, 'SOFTWARE\' + WebView2Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\' + WebView2Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if not HasWebView2 then
    Result := MsgBox(CustomMessage('WebView2Missing'), mbConfirmation, MB_YESNO) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\VisionSentinel');
    if DirExists(DataDir) and not UninstallSilent then
      if MsgBox(FmtMessage(CustomMessage('DeleteData'), [DataDir]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
