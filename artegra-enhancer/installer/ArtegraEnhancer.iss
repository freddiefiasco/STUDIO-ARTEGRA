; Guided per-user installation, including verified Standard and Fast AI files.
#ifndef AppVersion
  #define AppVersion "0.1.0a4"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\ArtegraEnhancer"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
[Setup]
AppId={{2B6628CA-E890-46BF-A894-E5D1E004707F}
AppName=Artegra Enhancer
AppVersion={#AppVersion}
AppPublisher=Studio Artegra
AppPublisherURL=https://www.studio-artegra.com
AppSupportURL=https://github.com/freddiefiasco/STUDIO-ARTEGRA/issues
DefaultDirName={localappdata}\Programs\ArtegraEnhancer
DefaultGroupName=Artegra Enhancer
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19045
OutputDir={#OutputDir}
OutputBaseFilename=ArtegraEnhancer-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110
DisableWelcomePage=no
DisableDirPage=yes
DisableProgramGroupPage=yes
LicenseFile=TERMS.txt
UninstallDisplayIcon={app}\ArtegraEnhancer.exe
CloseApplications=yes
RestartApplications=no
[Messages]
WelcomeLabel1=Welcome to Artegra Enhancer
WelcomeLabel2=Enhance your images on your own computer.%n%nSetup will install the app and prepare everything needed for Standard and Fast enhancement. Keep an internet connection available and allow about 40 GB of free space.%n%nYou can keep the recommended settings. Setup takes care of the rest.
LicenseLabel=Please read the software and model terms before continuing.
LicenseAccepted=I accept the software and model terms
LicenseNotAccepted=I do not accept the terms
ReadyLabel1=Ready to install Artegra Enhancer
ReadyLabel2a=Click Install to begin. Setup will download and check the required AI files automatically.
ReadyLabel2b=Click Install to begin. Setup will download and check the required AI files automatically.
FinishedHeadingLabel=Artegra Enhancer is ready
FinishedLabel=Installation is complete. Open Artegra Enhancer to add your first image.
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[InstallDelete]
Type: files; Name: "{app}\SetupRuntime.exe"
[Icons]
Name: "{group}\Artegra Enhancer"; Filename: "{app}\ArtegraEnhancer.exe"
Name: "{autodesktop}\Artegra Enhancer"; Filename: "{app}\ArtegraEnhancer.exe"; Tasks: desktopicon
Name: "{group}\Uninstall Artegra Enhancer"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\ArtegraEnhancer.exe"; Parameters: "{code:LaunchParameters}"; Description: "Open Artegra Enhancer"; Flags: nowait postinstall skipifsilent; Check: PreparationSucceeded

[Code]
var
  StoragePage: TInputDirWizardPage;
  StateDirectory, CancelFile, PreparationError: String;
  PreparingFiles, PreparationComplete, PreparationCancelled: Boolean;

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
    MsgBox('Artegra Enhancer requires Windows 10 22H2 or Windows 11 22H2 or newer. Update Windows before installing.', mbError, MB_OK);
end;

procedure InitializeWizard();
var
  DefaultData: String;
begin
  StateDirectory := ExpandConstant('{param:STATE|{localappdata}\Studio Artegra\Artegra Enhancer\production}');
  DefaultData := AddBackslash(ExtractFileDir(StateDirectory)) + 'data';
  StoragePage := CreateInputDirPage(wpLicense, 'Installation location',
    'Keep the recommended location, or choose another drive.',
    'Artegra Enhancer will manage its AI files here. Allow about 40 GB of free space for installation.'#13#10#13#10 +
    'Your enhanced images are saved separately in Pictures. Existing images are kept when you update or uninstall.',
    False, 'Artegra Enhancer');
  StoragePage.Add('AI files:');
  StoragePage.Values[0] := ExpandConstant('{param:DATADIR|' + GetPreviousData('AIDataDirectory', DefaultData) + '}');
  CancelFile := ExpandConstant('{tmp}\artegra-setup-cancel.flag');
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'AIDataDirectory', StoragePage.Values[0]);
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
  Result := 'Artegra Enhancer' + NewLine + Space + 'Standard and Fast enhancement' + NewLine + NewLine +
    'AI files' + NewLine + Space + StoragePage.Values[0] + NewLine + NewLine +
    'Setup downloads and verifies the required files automatically.' + NewLine +
    'Downloads can resume if your connection is interrupted.';
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
        PreparationError := 'Setup could not finish preparing the required files. Check your internet connection and available storage, then try again.';
      if not WizardSilent then
        RetrySetup := MsgBox(PreparationError + #13#10#13#10 +
          'Retry continues with files already downloaded. Cancel closes setup; opening Artegra Enhancer later will let you continue.',
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
      'Open Artegra Enhancer from your desktop or Start menu to continue. Verified downloads have been kept.';
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
