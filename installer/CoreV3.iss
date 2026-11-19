; CoreV3.iss — скрипт Inno Setup для Core V3.1
;
; Версия программы берётся из константы AppVersion ниже.
; Обновляйте её при выпуске новой версии.
;
; Сборка:
;   1. py -3.13 -m PyInstaller CoreV3.spec --noconfirm
;   2. Открыть этот файл в Inno Setup Compiler и нажать Compile
;      (или: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" CoreV3.iss)
;
; Результат: Output\CoreV3_Setup_3.1.exe

#define AppName "Core V3"
#define AppVersion "3.1"
#define AppPublisher "Сильченко Алексей"
#define AppExeName "CoreV3.exe"
#define SourceDir "..\dist\CoreV3"

[Setup]
AppId={{8E4F2A61-3C7D-4B15-9A2E-6D8C1F0B5A73}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Core - Корпоративный аудит
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}

; Установка в папку пользователя — без прав администратора
DefaultDirName={localappdata}\Programs\CoreV3
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Сжатие
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Оформление
WizardStyle=modern
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
ShowLanguageDialog=no

; Выход
OutputDir=Output
OutputBaseFilename=CoreV3_Setup_{#AppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=no
AllowNoIcons=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "Создать ярлык в панели задач"; GroupDescription: "Дополнительно:"; Flags: unchecked

[Files]
; Вся папка сборки PyInstaller
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Пустая папка data — если её нет, программа создаст сама,
; но так надёжнее при первом запуске
Source: "..\data\.keep"; DestDir: "{app}\data"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Логи и временные файлы удаляем, данные пользователя — нет
Type: filesandordirs; Name: "{app}\Logs"
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
// ---------------------------------------------------------------
// Проверка разрядности и наличия WebView2 Runtime
// ---------------------------------------------------------------
function IsWebView2Installed(): Boolean;
var
  Installed: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Installed)
    or RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Installed)
    or RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Installed);
end;

function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;

  if not IsWebView2Installed() then
  begin
    if MsgBox(
      'Не найден Microsoft Edge WebView2 Runtime.' + #13#10 + #13#10 +
      'Он нужен для работы виджета погоды. Без него программа запустится,' + #13#10 +
      'но погода отображаться не будет.' + #13#10 + #13#10 +
      'Скачать и установить сейчас?' + #13#10 +
      '(Evergreen Bootstrapper с сайта Microsoft)',
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
        '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Создаём папку data, если её не было
    ForceDirectories(ExpandConstant('{app}\data'));
  end;
end;
