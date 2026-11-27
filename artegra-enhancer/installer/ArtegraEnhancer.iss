; Guided per-user installation of Artegra Enhancer (Beta), including verified Redux and Bolt AI files, and its uninstaller.
#ifndef AppVersion
  #define AppVersion "5.0.2-beta.2"
#endif
#ifndef FileVersion
  #define FileVersion "5.0.2b2"
#endif
#ifndef VersionInfo
  #define VersionInfo "5.0.2.102"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\ArtegraEnhancer"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
[Setup]
; The AppId, the folder and the data keys stay as they were, so installing the Beta over an alpha upgrades it in place.
AppId={{2B6628CA-E890-46BF-A894-E5D1E004707F}
AppName=Artegra Enhancer (Beta)
AppVersion={#AppVersion}
AppVerName=Artegra Enhancer (Beta) {#AppVersion}
AppPublisher=Studio Artegra
AppPublisherURL=https://www.studio-artegra.com
AppSupportURL=https://github.com/freddiefiasco/STUDIO-ARTEGRA/issues
AppUpdatesURL=https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases
DefaultDirName={localappdata}\Programs\ArtegraEnhancer
DefaultGroupName=Artegra Enhancer (Beta)
UsePreviousGroup=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19045
OutputDir={#OutputDir}
OutputBaseFilename=ArtegraEnhancer-{#FileVersion}-Setup
SetupIconFile=ArtegraEnhancer.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110
DisableWelcomePage=no
DisableDirPage=yes
DisableProgramGroupPage=yes
LicenseFile=TERMS.txt
UninstallDisplayName=Artegra Enhancer (Beta)
UninstallDisplayIcon={app}\ArtegraEnhancer.exe
VersionInfoVersion={#VersionInfo}
VersionInfoCompany=Studio Artegra
VersionInfoProductName=Artegra Enhancer (Beta)
VersionInfoProductTextVersion={#AppVersion}
CloseApplications=yes
RestartApplications=no
[Messages]
WelcomeLabel1=Welcome to Artegra Enhancer (Beta)
WelcomeLabel2=Enhance your images on your own computer.%n%nSetup installs the app and prepares everything needed for Redux and Bolt enhancement. Keep an internet connection available and allow about 40 GB of free space.%n%nYou can keep the recommended settings. Setup takes care of the rest.
LicenseLabel=Read the software and model terms before you continue.
LicenseAccepted=I accept the software and model terms
LicenseNotAccepted=I do not accept the terms
ReadyLabel1=Ready to install Artegra Enhancer (Beta)
ReadyLabel2a=Click Install to begin. Setup downloads and checks the required AI files automatically.
ReadyLabel2b=Click Install to begin. Setup downloads and checks the required AI files automatically.
FinishedHeadingLabel=Artegra Enhancer (Beta) is ready
FinishedLabel=Installation is complete. Open Artegra Enhancer to add your first image.
ConfirmUninstall=Uninstall %1?%n%nYour enhanced images are never removed. Next, you can choose whether to also remove the downloaded enhancement files and your settings.
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[InstallDelete]
Type: files; Name: "{app}\SetupRuntime.exe"
; The alpha's shortcuts, by their exact names, so an upgrade leaves no stale ones.
Type: files; Name: "{userprograms}\Artegra Enhancer\Artegra Enhancer.lnk"
Type: files; Name: "{userprograms}\Artegra Enhancer\Uninstall Artegra Enhancer.lnk"
Type: dirifempty; Name: "{userprograms}\Artegra Enhancer"
Type: files; Name: "{autodesktop}\Artegra Enhancer.lnk"
[Icons]
Name: "{group}\Artegra Enhancer (Beta)"; Filename: "{app}\ArtegraEnhancer.exe"
Name: "{group}\Uninstall Artegra Enhancer (Beta)"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Artegra Enhancer (Beta)"; Filename: "{app}\ArtegraEnhancer.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\ArtegraEnhancer.exe"; Parameters: "{code:LaunchParameters}"; Description: "Open Artegra Enhancer"; Flags: nowait postinstall skipifsilent; Check: PreparationSucceeded

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{2B6628CA-E890-46BF-A894-E5D1E004707F}_is1';
  StillRunningCode = 2;

var
  StoragePage: TInputDirWizardPage;
  StateDirectory, CancelFile, PreparationError: String;
  PreparingFiles, PreparationComplete, PreparationCancelled: Boolean;
  RemoveFiles, RemoveSettings: Boolean;
  UninstallStateRoot: String;

function LaunchParameters(Param: String): String;
begin
  Result := '--state ' + AddQuotes(ExtractFileDir(StateDirectory));
end;

function PreparationSucceeded(): Boolean;
begin
  Result := PreparationComplete;
end;

function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  Result := not ((Version.Build >= 22000) and (Version.Build < 22621));
  if not Result then
    MsgBox('Artegra Enhancer needs Windows 10 22H2, or Windows 11 22H2 or newer. Update Windows, then run setup again.', mbError, MB_OK);
end;

procedure InitializeWizard();
var
  DefaultData: String;
begin
  StateDirectory := ExpandConstant('{param:STATE|{localappdata}\Studio Artegra\Artegra Enhancer\production}');
  DefaultData := AddBackslash(ExtractFileDir(StateDirectory)) + 'data';
  StoragePage := CreateInputDirPage(wpLicense, 'Installation location',
    'Keep the recommended location, or choose another drive.',
    'Artegra Enhancer manages its AI files here. Allow about 40 GB of free space for installation.'#13#10#13#10 +
    'Your enhanced images are saved separately in Pictures. They are kept when you update or uninstall.',
    False, 'Artegra Enhancer');
  StoragePage.Add('AI files:');
  StoragePage.Values[0] := ExpandConstant('{param:DATADIR|' + GetPreviousData('AIDataDirectory', DefaultData) + '}');
  CancelFile := ExpandConstant('{tmp}\artegra-setup-cancel.flag');
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'AIDataDirectory', StoragePage.Values[0]);
  // The uninstaller reads this to close and clean up the right state folder, even one chosen with /STATE=.
  SetPreviousData(PreviousDataKey, 'StateDirectory', StateDirectory);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Folder: String;
begin
  Result := True;
  if CurPageID = StoragePage.ID then begin
    Folder := Trim(StoragePage.Values[0]);
    if (Folder = '') or not PathIsRooted(Folder) then begin
      MsgBox('Choose a folder on a drive with enough free space, or keep the recommended location.', mbError, MB_OK);
      Result := False;
    end else
      StoragePage.Values[0] := Folder;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := 'Artegra Enhancer (Beta)' + NewLine + Space + 'Redux and Bolt enhancement' + NewLine + NewLine +
    'AI files' + NewLine + Space + StoragePage.Values[0] + NewLine + NewLine +
    'Setup downloads and checks the required files automatically.' + NewLine +
    'Downloads resume if your connection is interrupted.';
end;

procedure SetupProgress(const S: String; const Error, FirstLine: Boolean);
var
  Payload: String;
  Separator, Percent: Integer;
begin
  if Error then begin
    PreparationError := 'Setup could not read its progress. Close setup and open Artegra Enhancer to continue.';
    Exit;
  end;
  if Copy(S, 1, 14) = 'ARTEGRA-ERROR|' then begin
    PreparationError := Copy(S, 15, Length(S));
    Log(PreparationError);
  end else if Copy(S, 1, 8) = 'ARTEGRA|' then begin
    Payload := Copy(S, 9, Length(S));
    Separator := Pos('|', Payload);
    if Separator > 0 then begin
      Percent := StrToIntDef(Copy(Payload, 1, Separator - 1), 0);
      if Percent < 0 then Percent := 0;
      if Percent > 100 then Percent := 100;
      WizardForm.ProgressGauge.Position := Percent;
      if not PreparationCancelled then
        WizardForm.StatusLabel.Caption := Copy(Payload, Separator + 1, Length(Payload));
    end;
  end;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if PreparingFiles then begin
    Cancel := False;
    Confirm := False;
    if not PreparationCancelled then begin
      PreparationCancelled := True;
      SaveStringToFile(CancelFile, 'cancel', False);
      WizardForm.StatusLabel.Caption := 'Pausing setup safely...';
      WizardForm.CancelButton.Enabled := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params: String;
  Launched, RetrySetup: Boolean;
begin
  if CurStep <> ssPostInstall then Exit;
  PreparingFiles := True;
  WizardForm.StatusLabel.Caption := 'Preparing Artegra Enhancer...';
  WizardForm.FilenameLabel.Caption := 'This can take a while. You can keep using your computer.';
  WizardForm.ProgressGauge.Min := 0;
  WizardForm.ProgressGauge.Max := 100;
  WizardForm.ProgressGauge.Position := 0;
  repeat
    PreparationError := '';
    PreparationCancelled := False;
    DeleteFile(CancelFile);
    WizardForm.CancelButton.Enabled := True;
    Params := '--state ' + AddQuotes(StateDirectory) +
      ' --data-directory ' + AddQuotes(StoragePage.Values[0]) +
      ' --accept-terms --cancel-file ' + AddQuotes(CancelFile);
    ResultCode := -1;
    Launched := False;
    try
      Launched := ExecAndLogOutput(ExpandConstant('{app}\setup-internal\PrepareArtegra.exe'),
        Params, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated,
        ResultCode, @SetupProgress);
    except
      Log(GetExceptionMessage);
      PreparationError := 'Windows could not complete setup. Close other installations and try again.';
    end;
    PreparationComplete := Launched and (ResultCode = 0) and not PreparationCancelled;
    if ResultCode = 130 then PreparationCancelled := True;
    RetrySetup := False;
    if not PreparationComplete and not PreparationCancelled then begin
      if PreparationError = '' then
        PreparationError := 'Setup could not finish preparing the required files. Check your internet connection and free space, then try again.';
      if not WizardSilent then
        RetrySetup := MsgBox(PreparationError + #13#10#13#10 +
          'Retry continues with the files already downloaded. Cancel closes setup; open Artegra Enhancer later to continue.',
          mbError, MB_RETRYCANCEL) = IDRETRY;
    end;
  until not RetrySetup;
  PreparingFiles := False;
  WizardForm.CancelButton.Enabled := True;
  if PreparationComplete then begin
    WizardForm.ProgressGauge.Position := 100;
    WizardForm.StatusLabel.Caption := 'Artegra Enhancer is ready.';
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and not PreparationComplete then begin
    WizardForm.FinishedHeadingLabel.Caption := 'Setup needs to finish';
    if PreparationCancelled then
      WizardForm.FinishedHeadingLabel.Caption := 'Setup is paused';
    WizardForm.FinishedLabel.Caption := 'The app is installed, but its AI files are not ready yet.'#13#10#13#10 +
      'Open Artegra Enhancer from your desktop or Start menu to continue. Checked downloads are kept.';
    WizardForm.RunList.Visible := False;
  end;
end;

function GetCustomSetupExitCode(): Integer;
begin
  Result := 0;
  if not PreparationComplete then begin
    Result := 10;
    if PreparationCancelled then Result := 130;
  end;
end;

{ ---- Uninstall ------------------------------------------------------------------------------------------------------
  Order: Windows (or the app's own Settings entry) starts the uninstaller; Inno Setup asks once (ConfirmUninstall);
  then the options form below (a choice, not a second confirmation; the app's Settings entry starts the uninstaller
  with /SILENT /ASKOPTIONS=1 after its own confirmation, so it is never asked twice); then the app is closed, only its
  own recorded processes (--quit-running); then the chosen clean-up runs before Inno Setup removes the app's files.
  Silent uninstall (/SILENT, /VERYSILENT) keeps everything optional unless /REMOVEFILES=1 or /REMOVESETTINGS=1 is given.
  Enhanced images are never in scope. }

function HasParam(const Name: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Name) = 0 then
      Result := True;
end;

function StateRootForUninstall(): String;
var
  Value: String;
begin
  Result := ExpandConstant('{localappdata}\Studio Artegra\Artegra Enhancer');
  if RegQueryStringValue(HKCU, UninstallKey, 'Inno Setup CodeFile: StateDirectory', Value) and (Value <> '') then
    Result := ExtractFileDir(Value);
end;

function MeasuredFilesText(const Exe: String): String;
var
  ResultCode: Integer;
  OutFile: String;
  Text: AnsiString;
  Bytes, Gib: Int64;
begin
  // What the files option would free, measured now (the models and the managed image engine).
  Result := 'about 14 GiB';
  OutFile := ExpandConstant('{tmp}\artegra-files-size.txt');
  if Exec(Exe, '--uninstall-cleanup --measure --state ' + AddQuotes(UninstallStateRoot) + ' --out ' + AddQuotes(OutFile),
          ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0)
     and LoadStringFromFile(OutFile, Text) then begin
    Bytes := StrToInt64Def(Trim(String(Text)), -1);
    if Bytes = 0 then
      Result := 'none found'
    else if Bytes > 0 then begin
      Gib := (Bytes + 536870912) div 1073741824;
      if Gib < 1 then
        Result := 'less than 1 GiB'
      else
        Result := 'about ' + IntToStr(Gib) + ' GiB';
    end;
  end;
end;

procedure AskUninstallOptions(const Exe: String);
var
  Form: TSetupForm;
  Intro: TNewStaticText;
  FilesBox, SettingsBox: TNewCheckBox;
  ContinueButton: TNewButton;
begin
  // Inno Setup 7: the form scales the client size it is given; scaling it again here would double it at 125 % and 150 %.
  Form := CreateCustomForm(440, 176, False, True);
  try
    Form.Caption := 'Uninstall Artegra Enhancer (Beta)';
    Intro := TNewStaticText.Create(Form);
    Intro.Parent := Form;
    Intro.AutoSize := False;
    Intro.WordWrap := True;
    Intro.Left := ScaleX(16);
    Intro.Top := ScaleY(16);
    Intro.Width := Form.ClientWidth - ScaleX(32);
    Intro.Height := ScaleY(36);
    Intro.Caption := 'This removes the app. Your enhanced images are never removed.';
    FilesBox := TNewCheckBox.Create(Form);
    FilesBox.Parent := Form;
    FilesBox.Left := ScaleX(16);
    FilesBox.Top := ScaleY(56);
    FilesBox.Width := Form.ClientWidth - ScaleX(32);
    FilesBox.Height := ScaleY(20);
    FilesBox.Caption := 'Also remove downloaded enhancement files (' + MeasuredFilesText(Exe) + ')';
    FilesBox.Checked := False;
    SettingsBox := TNewCheckBox.Create(Form);
    SettingsBox.Parent := Form;
    SettingsBox.Left := ScaleX(16);
    SettingsBox.Top := ScaleY(84);
    SettingsBox.Width := Form.ClientWidth - ScaleX(32);
    SettingsBox.Height := ScaleY(20);
    SettingsBox.Caption := 'Also remove settings and logs';
    SettingsBox.Checked := False;
    ContinueButton := TNewButton.Create(Form);
    ContinueButton.Parent := Form;
    ContinueButton.Caption := 'Uninstall';
    ContinueButton.Width := ScaleX(96);
    ContinueButton.Height := ScaleY(26);
    ContinueButton.Left := Form.ClientWidth - ContinueButton.Width - ScaleX(16);
    ContinueButton.Top := Form.ClientHeight - ContinueButton.Height - ScaleY(16);
    ContinueButton.ModalResult := mrOk;
    ContinueButton.Default := True;
    Form.ActiveControl := ContinueButton;
    // Closing the form keeps everything optional: the person has already confirmed the uninstall itself.
    if Form.ShowModal() = mrOk then begin
      RemoveFiles := FilesBox.Checked;
      RemoveSettings := SettingsBox.Checked;
    end;
  finally
    Form.Free();
  end;
end;

function InitializeUninstall(): Boolean;
begin
  // Nothing is closed or removed here: the person has not confirmed yet.
  Result := True;
  UninstallStateRoot := StateRootForUninstall();
  RemoveFiles := HasParam('/REMOVEFILES=1');
  RemoveSettings := HasParam('/REMOVESETTINGS=1');
  if FileExists(AddBackslash(UninstallStateRoot) + 'production\run\host.json') then
    Log('Artegra Enhancer may be open; it is closed after the uninstall is confirmed.');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Exe, Params: String;
begin
  Exe := ExpandConstant('{app}\ArtegraEnhancer.exe');
  if CurUninstallStep = usAppMutexCheck then begin
    if (not UninstallSilent) or HasParam('/ASKOPTIONS=1') then
      AskUninstallOptions(Exe);
    // Close the app: only the processes its own run record names (never by name); its engine ends with it.
    if Exec(Exe, '--quit-running --state ' + AddQuotes(UninstallStateRoot) + ' --timeout 30',
            ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = StillRunningCode) then begin
      if not UninstallSilent then
        MsgBox('Artegra Enhancer (Beta) is still running. Close it, then try again.', mbError, MB_OK);
      Abort;
    end;
  end else if CurUninstallStep = usUninstall then begin
    // Before Inno Setup removes the app's files, while the helper can still run.
    if RemoveFiles or RemoveSettings then begin
      Params := '--uninstall-cleanup --state ' + AddQuotes(UninstallStateRoot);
      if RemoveFiles then Params := Params + ' --remove-files';
      if RemoveSettings then Params := Params + ' --remove-settings';
      Exec(Exe, Params, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Log('Clean-up finished with code ' + IntToStr(ResultCode));
    end;
  end;
end;
