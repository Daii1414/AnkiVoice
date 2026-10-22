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
#define MyAppVersion "1.8"
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
OutputBaseFilename=AnkiVoice-Setup-1.8
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
Source: "app\anki_gui.py";        DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\sudachi_g2p.py";     DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\g2p_core.py";        DestDir: "{app}\app"; Flags: ignoreversion
Source: "app\kana_stress.py";     DestDir: "{app}\app"; Flags: ignoreversion
; модули системы чтения и QC v2 — без них в установленном приложении
; молча отключаются подстановка чтения из фуриганы, доменный словарь
; и многосигнальная проверка качества звука
Source: "lab\g2p_provenance.py"; DestDir: "{app}\lab"; Flags: ignoreversion
Source: "lab\domain_dict.py";     DestDir: "{app}\lab"; Flags: ignoreversion
Source: "lab\g2p_candidates.py";  DestDir: "{app}\lab"; Flags: ignoreversion
Source: "lab\g2p_resolver.py";    DestDir: "{app}\lab"; Flags: ignoreversion
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
; при обновлении убираем файлы прежней раскладки (код лежал в корне)
Type: files; Name: "{app}\anki_gui.py"
Type: files; Name: "{app}\anki_web.py"
Type: files; Name: "{app}\voice_pipeline.py"
Type: files; Name: "{app}\sudachi_g2p.py"
Type: files; Name: "{app}\g2p_core.py"
Type: files; Name: "{app}\kana_stress.py"
Type: files; Name: "{app}\voices.json"
Type: files; Name: "{app}\pyruntime.zip"
Type: files; Name: "{app}\sudachidict.zip"

[UninstallDelete]
; pyruntime и логи создаёт сама программа — установщик о них не знает
Type: filesandordirs; Name: "{app}\pyruntime"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\lab"
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\bundled"
Type: files; Name: "{app}\gptsovits_path.txt"
