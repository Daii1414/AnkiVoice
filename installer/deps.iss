// ======================================================================
//  Страница «Что нужно для работы» (подключается в [Code] AnkiVoice.iss).
//
//  Установщик проверяет Anki, AnkiConnect, движок GPT-SoVITS и драйвер
//  NVIDIA. Для недостающего пользователь ДО любой загрузки выбирает:
//  скачать и установить — или указать папку, где оно уже стоит (например,
//  на другом диске). Затем общий план и подтверждение; загрузка — по
//  кнопке «Установить» (NextButtonClick на wpReady). Ошибка загрузки не
//  срывает установку самой программы: недостающее подскажет её мастер.
// ======================================================================
const
  DEP_ANKI = 0; DEP_CONNECT = 1; DEP_ENGINE = 2; DEP_GPU = 3; DEP_COUNT = 4;

var
  DepPage: TWizardPage;
  DepFound: array[0..3] of String;        // где нашлось ('' — не найдено)
  DepStatus: array[0..3] of TNewStaticText;
  DepInstall: array[0..3] of TNewCheckBox;
  DepHave: array[0..3] of TNewCheckBox;
  DepDir: array[0..3] of TNewEdit;
  DepBrowseBtn: array[0..3] of TNewButton;
  DownloadPage: TDownloadWizardPage;

function DepName(I: Integer): String;
begin
  case I of
    DEP_ANKI: Result := CustomMessage('DepAnki');
    DEP_CONNECT: Result := CustomMessage('DepConnect');
    DEP_ENGINE: Result := CustomMessage('DepEngine');
  else
    Result := CustomMessage('DepGpu');
  end;
end;

function DepHint(I: Integer): String;
begin
  case I of
    DEP_ANKI: Result := CustomMessage('DepAnkiHint');
    DEP_CONNECT: Result := CustomMessage('DepConnectHint');
    DEP_ENGINE: Result := CustomMessage('DepEngineHint');
  else
    Result := CustomMessage('DepGpuHint');
  end;
end;

function Anki2Dir: String;
begin
  Result := ExpandConstant('{userappdata}\Anki2');
end;

// годится ли папка, которую указал пользователь
function DirFits(I: Integer; Dir: String): Boolean;
begin
  Dir := RemoveBackslashUnlessRoot(Trim(Dir));
  if Dir = '' then
  begin
    Result := False;
    Exit;
  end;
  case I of
    DEP_ANKI: Result := FileExists(Dir + '\anki.exe');
    DEP_CONNECT: Result := DirExists(Dir + '\addons21') or FileExists(Dir + '\prefs21.db');
    DEP_ENGINE: Result := FileExists(Dir + '\api_v2.py') and DirExists(Dir + '\GPT_SoVITS');
  else
    Result := True;
  end;
end;

function DirNeeds(I: Integer): String;
begin
  case I of
    DEP_ANKI: Result := 'anki.exe';
    DEP_CONNECT: Result := 'addons21';
    DEP_ENGINE: Result := 'api_v2.py, GPT_SoVITS';
  else
    Result := '';
  end;
end;

// движок: прошлая установка, затем папки GPT-SoVITS* в корнях дисков
// и в папках пользователя (так его обычно распаковывают)
function FindEngineIn(const Root: String): String;
var
  FR: TFindRec;
begin
  Result := '';
  if FindFirst(Root + '\GPT-SoVITS*', FR) then
  begin
    try
      repeat
        if DirFits(DEP_ENGINE, Root + '\' + FR.Name) then
        begin
          Result := Root + '\' + FR.Name;
          Exit;
        end;
      until not FindNext(FR);
    finally
      FindClose(FR);
    end;
  end;
end;

function FindEngine: String;
var
  D: AnsiString;
  Drive: Char;
begin
  Result := '';
  if LoadStringFromFile(ExpandConstant('{app}\app\gptsovits_path.txt'), D) then
    if DirFits(DEP_ENGINE, String(D)) then
    begin
      Result := Trim(String(D));
      Exit;
    end;
  for Drive := 'C' to 'H' do
    if DirExists(Drive + ':\') then
    begin
      Result := FindEngineIn(Drive + ':');
      if Result <> '' then Exit;
    end;
  Result := FindEngineIn(ExpandConstant('{userdesktop}'));
  if Result = '' then Result := FindEngineIn(ExpandConstant('{userdocs}'));
  if Result = '' then Result := FindEngineIn(ExpandConstant('{%USERPROFILE}\Downloads'));
  if Result = '' then Result := FindEngineIn(ExpandConstant('{localappdata}\AnkiVoice'));
end;

procedure DetectDeps;
var
  S: String;
begin
  DepFound[DEP_ANKI] := '';
  if FileExists(ExpandConstant('{localappdata}\Programs\Anki\anki.exe')) then
    DepFound[DEP_ANKI] := ExpandConstant('{localappdata}\Programs\Anki')
  else if FileExists(ExpandConstant('{commonpf64}\Anki\anki.exe')) then
    DepFound[DEP_ANKI] := ExpandConstant('{commonpf64}\Anki')
  else if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\anki.exe', '', S) then
  begin
    if FileExists(S) then DepFound[DEP_ANKI] := ExtractFileDir(S);
  end;
  DepFound[DEP_CONNECT] := '';
  if FileExists(Anki2Dir + '\addons21\2055492159\__init__.py') then
    DepFound[DEP_CONNECT] := Anki2Dir;
  DepFound[DEP_ENGINE] := FindEngine;
  DepFound[DEP_GPU] := '';
  if FileExists(ExpandConstant('{sys}\nvidia-smi.exe')) then
    DepFound[DEP_GPU] := 'NVIDIA';
end;

procedure DepSync;
var
  I: Integer;
begin
  for I := 0 to DEP_COUNT - 1 do
  begin
    DepDir[I].Enabled := DepHave[I].Checked;
    DepBrowseBtn[I].Enabled := DepHave[I].Checked;
  end;
end;

procedure DepCheckClick(Sender: TObject);
var
  I: Integer;
begin
  // «скачать» и «уже установлено» исключают друг друга
  for I := 0 to DEP_COUNT - 1 do
  begin
    if (Sender = DepInstall[I]) and DepInstall[I].Checked then DepHave[I].Checked := False;
    if (Sender = DepHave[I]) and DepHave[I].Checked then DepInstall[I].Checked := False;
  end;
  DepSync;
end;

procedure DepBrowseClick(Sender: TObject);
var
  I: Integer;
  D: String;
begin
  for I := 0 to DEP_COUNT - 1 do
    if Sender = DepBrowseBtn[I] then
    begin
      D := DepDir[I].Text;
      if BrowseForFolder(DepName(I), D, False) then
      begin
        DepDir[I].Text := D;
        DepHave[I].Checked := True;
        DepInstall[I].Checked := False;
        DepSync;
      end;
    end;
end;

procedure CreateDepPage;
var
  I, Y: Integer;
  Title, Hint: TNewStaticText;
begin
  DetectDeps;
  DepPage := CreateCustomPage(wpSelectTasks, CustomMessage('DepTitle'), CustomMessage('DepSub'));
  Y := 0;
  for I := 0 to DEP_COUNT - 1 do
  begin
    Title := TNewStaticText.Create(DepPage);
    Title.Parent := DepPage.Surface;
    Title.Top := Y;
    Title.Caption := DepName(I);
    Title.Font.Style := [fsBold];

    DepStatus[I] := TNewStaticText.Create(DepPage);
    DepStatus[I].Parent := DepPage.Surface;
    DepStatus[I].Top := Y;
    DepStatus[I].Left := DepPage.SurfaceWidth - ScaleX(170);
    if DepFound[I] <> '' then
    begin
      DepStatus[I].Caption := FmtMessage(CustomMessage('DepFound'), [ExtractFileName(DepFound[I])]);
      DepStatus[I].Font.Color := $00308030;
    end else begin
      DepStatus[I].Caption := CustomMessage('DepMissing');
      if I = DEP_GPU then
        DepStatus[I].Caption := DepStatus[I].Caption + ' (' + CustomMessage('DepOptional') + ')';
      DepStatus[I].Font.Color := $002020C0;
    end;

    Hint := TNewStaticText.Create(DepPage);
    Hint.Parent := DepPage.Surface;
    Hint.Top := Y + ScaleY(15);
    Hint.Width := DepPage.SurfaceWidth;
    Hint.AutoSize := False;
    Hint.Height := ScaleY(14);
    Hint.Caption := DepHint(I);
    Hint.Font.Color := $00808080;
    Y := Y + ScaleY(32);

    DepInstall[I] := TNewCheckBox.Create(DepPage);
    DepInstall[I].Parent := DepPage.Surface;
    DepInstall[I].Top := Y;
    DepInstall[I].Width := ScaleX(170);
    if I = DEP_GPU then
      DepInstall[I].Caption := CustomMessage('DepGpuOpen')
    else
      DepInstall[I].Caption := CustomMessage('DepInstall');
    DepInstall[I].Checked := (DepFound[I] = '') and (I <> DEP_GPU);
    DepInstall[I].OnClick := @DepCheckClick;

    DepHave[I] := TNewCheckBox.Create(DepPage);
    DepHave[I].Parent := DepPage.Surface;
    DepHave[I].Top := Y;
    DepHave[I].Left := ScaleX(176);
    DepHave[I].Width := ScaleX(150);
    DepHave[I].Caption := CustomMessage('DepHaveDir');
    DepHave[I].Checked := DepFound[I] <> '';
    DepHave[I].OnClick := @DepCheckClick;

    DepDir[I] := TNewEdit.Create(DepPage);
    DepDir[I].Parent := DepPage.Surface;
    DepDir[I].Top := Y - ScaleY(2);
    DepDir[I].Left := ScaleX(330);
    DepDir[I].Width := DepPage.SurfaceWidth - ScaleX(330) - ScaleX(82);
    DepDir[I].Text := DepFound[I];

    DepBrowseBtn[I] := TNewButton.Create(DepPage);
    DepBrowseBtn[I].Parent := DepPage.Surface;
    DepBrowseBtn[I].Top := Y - ScaleY(3);
    DepBrowseBtn[I].Left := DepPage.SurfaceWidth - ScaleX(76);
    DepBrowseBtn[I].Width := ScaleX(76);
    DepBrowseBtn[I].Height := ScaleY(23);
    DepBrowseBtn[I].Caption := CustomMessage('DepBrowse');
    DepBrowseBtn[I].OnClick := @DepBrowseClick;

    if I = DEP_GPU then
    begin
      // драйвер не ставим сами — только открываем страницу NVIDIA
      DepHave[I].Visible := False;
      DepDir[I].Visible := False;
      DepBrowseBtn[I].Visible := False;
      DepInstall[I].Width := DepPage.SurfaceWidth;
      DepInstall[I].Visible := DepFound[I] = '';
    end;
    Y := Y + ScaleY(30);
  end;
  DepSync;
end;

// нужно ли что-то скачивать для зависимости
function DepWanted(I: Integer): Boolean;
begin
  Result := DepInstall[I].Checked and (DepFound[I] = '') and (I <> DEP_GPU);
end;

function DepPageNext: Boolean;
var
  I: Integer;
  Plan, Skip: String;
begin
  Result := True;
  Plan := '';
  Skip := '';
  for I := 0 to DEP_COUNT - 1 do
  begin
    if (I <> DEP_GPU) and DepHave[I].Checked then
    begin
      if Trim(DepDir[I].Text) = '' then
      begin
        MsgBox(FmtMessage(CustomMessage('DepEmptyDir'), [DepName(I)]), mbError, MB_OK);
        Result := False;
        Exit;
      end;
      if not DirFits(I, DepDir[I].Text) then
      begin
        MsgBox(FmtMessage(CustomMessage('DepBadDir'), [Trim(DepDir[I].Text), DirNeeds(I)]), mbError, MB_OK);
        Result := False;
        Exit;
      end;
    end
    else if DepWanted(I) then
      Plan := Plan + #13#10 + '  • ' + DepName(I)
    else if (DepFound[I] = '') and (I <> DEP_GPU) then
      Skip := Skip + #13#10 + '  • ' + DepName(I);
  end;
  // перед любой загрузкой — общий план и подтверждение
  if Plan = '' then
    Plan := CustomMessage('DepPlanNone')
  else
    Plan := CustomMessage('DepPlan') + Plan;
  if Skip <> '' then
    Plan := Plan + #13#10#13#10 + CustomMessage('DepPlanSkip') + Skip;
  Result := MsgBox(CustomMessage('DepPlanTitle') + #13#10#13#10 + Plan, mbConfirmation, MB_OKCANCEL) = IDOK;
end;

function OnDepDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

function RunHidden(const Exe, Params: String): Boolean;
var
  Code: Integer;
begin
  Result := Exec(Exe, Params, '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

// скачать и поставить выбранное — до копирования файлов программы
procedure DepPrepare;
var
  Code: Integer;
  Dest, Target: String;
begin
  if DepPage = nil then Exit;
  if DepInstall[DEP_GPU].Checked and (DepFound[DEP_GPU] = '') then
    ShellExec('open', '{#NvidiaUrl}', '', '', SW_SHOWNORMAL, ewNoWait, Code);
  if not (DepWanted(DEP_ANKI) or DepWanted(DEP_CONNECT) or DepWanted(DEP_ENGINE)) then Exit;
  DownloadPage.Clear;
  if DepWanted(DEP_ANKI) then DownloadPage.Add('{#AnkiUrl}', 'anki-setup.msi', '');
  if DepWanted(DEP_CONNECT) then DownloadPage.Add('{#AnkiConnectUrl}', 'ankiconnect.zip', '');
  if DepWanted(DEP_ENGINE) then DownloadPage.Add('{#EngineUrl}', 'gpt-sovits.7z', '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
    except
      if not DownloadPage.AbortedByUser then
        MsgBox(FmtMessage(CustomMessage('DepFailed'), ['', GetExceptionMessage]), mbError, MB_OK);
      Exit;              // сама программа ставится и без зависимостей
    end;
  finally
    DownloadPage.Hide;
  end;

  if DepWanted(DEP_ANKI) then
  begin
    WizardForm.StatusLabel.Caption := FmtMessage(CustomMessage('DepRunning'), ['Anki']);
    if not Exec('msiexec.exe', '/i "' + ExpandConstant('{tmp}\anki-setup.msi') + '" /passive',
                '', SW_SHOWNORMAL, ewWaitUntilTerminated, Code) or (Code <> 0) then
      MsgBox(FmtMessage(CustomMessage('DepFailed'), ['Anki', IntToStr(Code)]), mbError, MB_OK);
  end;

  if DepWanted(DEP_CONNECT) then
  begin
    Dest := Anki2Dir;
    if DepHave[DEP_CONNECT].Checked and DirFits(DEP_CONNECT, DepDir[DEP_CONNECT].Text) then
      Dest := Trim(DepDir[DEP_CONNECT].Text);
    Target := Dest + '\addons21\2055492159';
    ForceDirectories(Target);
    // .ankiaddon — это zip; распаковываем средствами Windows
    if not RunHidden('powershell.exe', '-NoProfile -ExecutionPolicy Bypass -Command ' +
        AddQuotes('Expand-Archive -LiteralPath ''' + ExpandConstant('{tmp}\ankiconnect.zip') +
        ''' -DestinationPath ''' + Target + ''' -Force')) then
      MsgBox(FmtMessage(CustomMessage('DepFailed'), ['AnkiConnect', 'Expand-Archive']), mbError, MB_OK)
    else
      DepFound[DEP_CONNECT] := Dest;
  end;

  if DepWanted(DEP_ENGINE) then
  begin
    Dest := ExpandConstant('{localappdata}\AnkiVoice');
    ForceDirectories(Dest);
    WizardForm.StatusLabel.Caption := FmtMessage(CustomMessage('DepExtracting'), ['GPT-SoVITS']);
    // tar.exe (libarchive) есть в Windows 10 1803+ и читает .7z
    if RunHidden(ExpandConstant('{sys}\tar.exe'), '-xf "' + ExpandConstant('{tmp}\gpt-sovits.7z') +
                 '" -C "' + Dest + '"') and DirFits(DEP_ENGINE, Dest + '\{#EngineDirName}') then
      DepFound[DEP_ENGINE] := Dest + '\{#EngineDirName}'
    else
    begin
      FileCopy(ExpandConstant('{tmp}\gpt-sovits.7z'), Dest + '\{#EngineDirName}.7z', False);
      MsgBox(FmtMessage(CustomMessage('DepNeedTar'), [Dest + '\{#EngineDirName}']), mbInformation, MB_OK);
      ShellExec('open', Dest, '', '', SW_SHOWNORMAL, ewNoWait, Code);
    end;
  end;
end;

procedure DepInit;
begin
  CreateDepPage;
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing),
    SetupMessage(msgPreparingDesc), @OnDepDownloadProgress);
end;

// после копирования файлов: язык интерфейса и выбранные папки — программе
procedure DepSaveChoices;
var
  AppDir, Eng: String;
begin
  AppDir := ExpandConstant('{app}\app');
  ForceDirectories(AppDir);
  SaveStringToFile(AppDir + '\default_lang.txt', CustomMessage('AppLang'), False);
  Eng := '';
  if DepHave[DEP_ENGINE].Checked and DirFits(DEP_ENGINE, DepDir[DEP_ENGINE].Text) then
    Eng := Trim(DepDir[DEP_ENGINE].Text)
  else if DirFits(DEP_ENGINE, DepFound[DEP_ENGINE]) then
    Eng := DepFound[DEP_ENGINE];
  if Eng <> '' then
    SaveStringToFile(AppDir + '\gptsovits_path.txt', Eng, False);
  if DepHave[DEP_CONNECT].Checked and DirFits(DEP_CONNECT, DepDir[DEP_CONNECT].Text) then
    SaveStringToFile(AppDir + '\anki2_dir.txt', Trim(DepDir[DEP_CONNECT].Text), False);
end;
