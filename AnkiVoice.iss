; -- AnkiVoice.iss -------------------------------------------------------------
; Сборка установщика AnkiVoice для Windows (Inno Setup 6).
;
;   Скомпилировать:  ISCC.exe AnkiVoice.iss
;   На выходе:       dist\AnkiVoice-Setup-1.6.exe  — один файл, всё внутри.
;
; Установка — профильная, в папку пользователя ({localappdata}\Programs):
; без запроса прав администратора и без UAC. Это принципиально: пайплайн при
; первом запуске распаковывает pyruntime.zip/sudachidict.zip РЯДОМ с exe,
; а в Program Files обычный пользователь писать не может.

#define MyAppName "AnkiVoice"
#define MyAppVersion "1.9.1"
#define MyAppPublisher "Daii1414"
#define MyAppURL "https://github.com/Daii1414/AnkiVoice"
; Исходники берём из каталога этого скрипта ({src}) — сборка одинаково
; работает локально и в CI, без жёстких путей.

[Setup]
AppId={{6D8C4A52-73E1-4E49-9C2F-0B1E2A9C7D31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=AnkiVoice-Setup-1.9.1
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\AnkiVoice.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; \
  GroupDescription: "Дополнительные значки:"

[Files]
; сама программа и её памятки
Source: "AnkiVoice.exe";         DestDir: "{app}"; Flags: ignoreversion
Source: "pipeline.bat";          DestDir: "{app}"; Flags: ignoreversion
Source: "README.md";            DestDir: "{app}"; Flags: ignoreversion
Source: "README.en.md";         DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md";         DestDir: "{app}"; Flags: ignoreversion
Source: "PROJECT.md";           DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE";              DestDir: "{app}"; Flags: ignoreversion
; пайплайн (exe только запускает его — живёт на диске, обновляется git pull)
Source: "app\voice_pipeline.py";  DestDir: "{app}\app"; Flags: ignoreversion
; модули пайплайна (разбивка 1.9.2): фасад импортирует их при старте
Source: "app\paths.py";           DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\av_state.py";        DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\fields_config.py";   DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\anki_api.py";        DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\engines.py";         DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\voices.py";          DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\kana_reading.py";    DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\tts.py";             DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\jobs.py";            DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\voicing.py";         DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\anki_gui.py";        DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\sudachi_g2p.py";     DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\g2p_core.py";        DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\kana_stress.py";     DestDir: "{app}\app"; Flags: ignoreversion
; QC v2 и проверка произношения — без них в установленном приложении
; молча отключается многосигнальная проверка качества звука
; (бывшая «система чтения» — provenance/доменный словарь/резолвер —
; удалена как мёртвый код, аудит v1.9)
Source: "lab\quality_v2.py";       DestDir: "{app}\lab"; Flags: ignoreversion
Source: "lab\pron_check.py";       DestDir: "{app}\lab"; Flags: ignoreversion
Source: "lab\align_ja.py";         DestDir: "{app}\lab"; Flags: ignoreversion
  Source: "lab\indextts_service.py";  DestDir: "{app}\lab"; Flags: ignoreversion
  Source: "lab\indextts_fast.py";     DestDir: "{app}\lab"; Flags: ignoreversion
  Source: "lab\indextts_norm.py";     DestDir: "{app}\lab"; Flags: ignoreversion
; голоса и словарь чтения
Source: "app\voices.json";        DestDir: "{app}\app"; Flags: ignoreversion
; встроенный Python и словарь Sudachi (распакуются при первом запуске)
Source: "bundled\pyruntime.zip";   DestDir: "{app}\bundled"; Flags: ignoreversion
Source: "bundled\sudachidict.zip"; DestDir: "{app}\bundled"; Flags: ignoreversion

[Icons]
Name: "{userstartmenu}\{#MyAppName}"; Filename: "{app}\AnkiVoice.exe"
Name: "{userstartmenu}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\AnkiVoice.exe"; \
  Tasks: desktopicon

[Run]
Filename: "{app}\AnkiVoice.exe"; Description: "Запустить {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent

[InstallDelete]
; при обновлении убираем файлы прежней раскладки (код лежал в корне).
; voices.json здесь НЕ удаляем: в 1.8 он лежал в корне и был ПОЛЬЗОВАТЕЛЬСКИМ
; (реестр голосов) — удалять его значит молча терять настройки. Переносит его
; на новое место CurStepChanged в [Code] ниже.
Type: files; Name: "{app}\anki_gui.py"
Type: files; Name: "{app}\anki_web.py"
Type: files; Name: "{app}\voice_pipeline.py"
Type: files; Name: "{app}\sudachi_g2p.py"
Type: files; Name: "{app}\g2p_core.py"
Type: files; Name: "{app}\kana_stress.py"
Type: files; Name: "{app}\pyruntime.zip"
Type: files; Name: "{app}\sudachidict.zip"

[Code]
// Обновление с 1.8: реестр голосов жил в {app}\voices.json, теперь живёт в
// {app}\app\voices.json. Копируем старый на новое место до установки файлов
// (ssInstall срабатывает раньше [InstallDelete] и [Files]), только если
// своего ещё нет — свежий установочный не затираем.
procedure CurStepChanged(CurStep: TSetupStep);
var
  OldVoices, NewVoices: String;
begin
  if CurStep = ssInstall then
  begin
    OldVoices := ExpandConstant('{app}\voices.json');
    NewVoices := ExpandConstant('{app}\app\voices.json');
    if FileExists(OldVoices) and not FileExists(NewVoices) then
    begin
      ForceDirectories(ExpandConstant('{app}\app'));
      FileCopy(OldVoices, NewVoices, True);   // True: не перезаписывать
    end;
  end;
end;

// При удалении программы {app}\app вычищается ВРУЧНУЮ: у [UninstallDelete]
// нет параметра Excludes, а voices.json там — пользовательский реестр
// голосов, его терять нельзя. Всё прочее удаляется, сам каталог снимается,
// только если опустел.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: String;
  FindRec: TFindRec;
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  AppDir := ExpandConstant('{app}\app');
  if not DirExists(AppDir) then
    Exit;
  if FindFirst(AppDir + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
           (CompareText(FindRec.Name, 'voices.json') <> 0) then
        begin
          if DirExists(AppDir + '\' + FindRec.Name) then
            DelTree(AppDir + '\' + FindRec.Name, True, True, True)
          else
            DeleteFile(AppDir + '\' + FindRec.Name);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
  RemoveDir(AppDir);    // сработает, только если внутри остался voices.json
end;

[UninstallDelete]
; pyruntime и логи создаёт сама программа — установщик о ней не знает.
; {app}\app НЕ в списке: его содержимое (кроме пользовательского
; voices.json) вычищает CurUninstallStepChanged в [Code].
Type: filesandordirs; Name: "{app}\pyruntime"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\lab"
Type: filesandordirs; Name: "{app}\bundled"
Type: files; Name: "{app}\gptsovits_path.txt"
