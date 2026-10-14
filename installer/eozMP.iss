; eozMP installer (Inno Setup 6). Build with build_setup.bat in the eozMP folder.
; Asks step by step: what to install (eozMP, Soulseek/slskd, VLC), shortcuts, and the Soulseek account.

#define AppVersion "1.3"
#define VlcUrl "https://get.videolan.org/vlc/3.0.24/win64/vlc-3.0.24-win64.exe"
#define VlcSha256 "d711e1e1fe52052748c39080c7dce63f6b7e4c315efedf1774a3f1957b782ff3"

[Setup]
AppId={{6F2C1B7E-3A54-4E0B-9C41-E0A5D7B2F1C3}
AppName=eozMP
AppVersion={#AppVersion}
AppPublisher=Eren
AppPublisherURL=https://github.com/erenoozr/eozMP
DefaultDirName={autopf}\eozMP
DefaultGroupName=eozMP
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=eozMP-Setup-{#AppVersion}
SetupIconFile=..\eozMP.ico
UninstallDisplayIcon={app}\eozMP.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=yes
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[CustomMessages]
english.CompMain=eozMP music player
english.CompSlskd=Soulseek support (slskd) - find and download music
english.CompVlc=VLC media player - needed only for the equalizer (downloaded during setup, about 45 MB)
english.TaskDesktop=Create a desktop shortcut
english.AccTitle=Your Soulseek account
english.AccDesc=eozMP downloads music through Soulseek. Pick a name and a password.
english.AccSub=The account is created automatically the first time eozMP connects - there is no separate sign-up. Pick an unusual name (add some numbers) so nobody else has it. Use only letters and numbers in the password.%n%nLeave the name empty to skip this; the Soulseek Guide explains how to do it later.
english.AccUser=Soulseek user name:
english.AccPass=Password:
english.AccBadUser=Use only letters, numbers, _ and - in the user name (3 to 30 characters).
english.AccBadPass=Use only letters and numbers in the password (at least 4).
english.AccSkipped=OK - Soulseek is installed but not logged in yet. The Soulseek Guide (Start menu > eozMP) explains how to finish it.
english.DirTitle=Where should downloads go?
english.DirDesc=Soulseek downloads land here first; eozMP then files them into your music library.
english.DirSub=Downloads folder:
english.OldTitle=Soulseek is already set up
english.OldDesc=Your existing slskd settings were found.
english.OldMsg=An slskd settings file already exists on this PC (%LOCALAPPDATA%\slskd\slskd.yml), so setup leaves it exactly as it is.%n%nTo connect eozMP to it, follow section 7 of the Soulseek Guide. You can open it at the end of setup.
english.VlcFail=VLC couldn't be downloaded (%1). eozMP works without it; only the equalizer needs VLC. You can install it later from videolan.org.
english.VlcRun=Installing VLC (Windows will ask for permission)...
english.RunGuide=Open the Soulseek Guide
english.IconGuide=Soulseek Guide
english.IconManual=eozMP User Manual
english.GuideFile=Soulseek Guide.txt
turkish.CompMain=eozMP müzik çalar
turkish.CompSlskd=Soulseek desteği (slskd) - müzik bul ve indir
turkish.CompVlc=VLC media player - sadece ekolayzır için gerekli (kurulum sırasında indirilir, yaklaşık 45 MB)
turkish.TaskDesktop=Masaüstüne kısayol oluştur
turkish.AccTitle=Soulseek hesabın
turkish.AccDesc=eozMP müzikleri Soulseek üzerinden indirir. Bir ad ve şifre seç.
turkish.AccSub=Hesap, eozMP ilk kez bağlandığında otomatik oluşturulur - ayrıca kayıt olman gerekmez. Başkasında olmayan sıra dışı bir ad seç (birkaç rakam ekle). Şifrede sadece harf ve rakam kullan.%n%nBunu atlamak için adı boş bırak; Soulseek Rehberi sonra nasıl yapılacağını anlatıyor.
turkish.AccUser=Soulseek kullanıcı adı:
turkish.AccPass=Şifre:
turkish.AccBadUser=Kullanıcı adında sadece harf, rakam, _ ve - kullan (3 ile 30 karakter arası).
turkish.AccBadPass=Şifrede sadece harf ve rakam kullan (en az 4 karakter).
turkish.AccSkipped=Tamam - Soulseek kuruldu ama henüz giriş yapılmadı. Soulseek Rehberi (Başlat menüsü > eozMP) nasıl tamamlanacağını anlatıyor.
turkish.DirTitle=İndirmeler nereye gitsin?
turkish.DirDesc=Soulseek indirmeleri önce buraya iner; eozMP sonra onları müzik kütüphanene yerleştirir.
turkish.DirSub=İndirme klasörü:
turkish.OldTitle=Soulseek zaten kurulu
turkish.OldDesc=Mevcut slskd ayarların bulundu.
turkish.OldMsg=Bu bilgisayarda zaten bir slskd ayar dosyası var (%LOCALAPPDATA%\slskd\slskd.yml), kurulum ona hiç dokunmayacak.%n%neozMP'yi ona bağlamak için Soulseek Rehberi'nin 7. bölümünü izle. Kurulumun sonunda açabilirsin.
turkish.VlcFail=VLC indirilemedi (%1). eozMP onsuz da çalışır; sadece ekolayzır VLC ister. Sonra videolan.org'dan kurabilirsin.
turkish.VlcRun=VLC kuruluyor (Windows izin isteyecek)...
turkish.RunGuide=Soulseek Rehberi'ni aç
turkish.IconGuide=Soulseek Rehberi
turkish.IconManual=eozMP Kullanım Kılavuzu
turkish.GuideFile=Soulseek Rehberi.txt

[Types]
Name: "custom"; Description: "Custom"; Flags: iscustom

[Components]
Name: "main"; Description: "{cm:CompMain}"; Types: custom; Flags: fixed
Name: "slskd"; Description: "{cm:CompSlskd}"; Types: custom
Name: "vlc"; Description: "{cm:CompVlc}"

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktop}"

[Files]
Source: "..\dist\eozMP.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: main
Source: "..\eozMP.ico"; DestDir: "{app}"; Components: main
Source: "..\MANUAL.md"; DestDir: "{app}"; DestName: "eozMP User Manual.md"; Components: main
Source: "Soulseek Guide.txt"; DestDir: "{app}"; Components: main
Source: "Soulseek Rehberi.txt"; DestDir: "{app}"; Components: main
Source: "vendor\fpcalc\fpcalc.exe"; DestDir: "{app}\fpcalc"; Flags: ignoreversion; Components: main
Source: "vendor\slskd\*"; DestDir: "{app}\slskd"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: slskd

[Icons]
Name: "{group}\eozMP"; Filename: "{app}\eozMP.exe"
Name: "{group}\{cm:IconGuide}"; Filename: "{app}\{cm:GuideFile}"
Name: "{group}\{cm:IconManual}"; Filename: "{app}\eozMP User Manual.md"
Name: "{group}\{cm:UninstallProgram,eozMP}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\eozMP"; Filename: "{app}\eozMP.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\eozMP.exe"; Description: "{cm:LaunchProgram,eozMP}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{cm:GuideFile}"; Description: "{cm:RunGuide}"; Flags: shellexec postinstall skipifsilent unchecked

[UninstallDelete]
Type: files; Name: "{app}\slskd_setup.json"

[Code]
var
  AccountPage: TInputQueryWizardPage;
  DirPage: TInputDirWizardPage;
  OldPage: TOutputMsgWizardPage;
  DownloadPage: TDownloadWizardPage;
  HasYml, VlcReady: Boolean;

function YmlPath: String;
begin
  Result := ExpandConstant('{localappdata}\slskd\slskd.yml');
end;

function OnlyChars(S, Allowed: String): Boolean;
var
  I: Integer;
begin
  Result := True;
  for I := 1 to Length(S) do
    if Pos(S[I], Allowed) = 0 then
      Result := False;
end;

procedure InitializeWizard;
begin
  HasYml := FileExists(YmlPath);
  AccountPage := CreateInputQueryPage(wpSelectTasks, CustomMessage('AccTitle'), CustomMessage('AccDesc'),
    CustomMessage('AccSub'));
  AccountPage.Add(CustomMessage('AccUser'), False);
  AccountPage.Add(CustomMessage('AccPass'), True);
  { silent installs can pass the account: /SOULUSER=name /SOULPASS=password }
  AccountPage.Values[0] := ExpandConstant('{param:SOULUSER|}');
  AccountPage.Values[1] := ExpandConstant('{param:SOULPASS|}');
  DirPage := CreateInputDirPage(AccountPage.ID, CustomMessage('DirTitle'), CustomMessage('DirDesc'),
    CustomMessage('DirSub'), False, '');
  DirPage.Add('');
  DirPage.Values[0] := ExpandConstant('{%USERPROFILE}\Music\Soulseek');
  OldPage := CreateOutputMsgPage(wpSelectTasks, CustomMessage('OldTitle'), CustomMessage('OldDesc'),
    CustomMessage('OldMsg'));
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = OldPage.ID then
    Result := not (WizardIsComponentSelected('slskd') and HasYml)
  else if PageID = AccountPage.ID then
    Result := (not WizardIsComponentSelected('slskd')) or HasYml
  else if PageID = DirPage.ID then
    Result := (not WizardIsComponentSelected('slskd')) or HasYml or (Trim(AccountPage.Values[0]) = '');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  User, Pass: String;
begin
  Result := True;
  if CurPageID = AccountPage.ID then
  begin
    User := Trim(AccountPage.Values[0]);
    Pass := AccountPage.Values[1];
    if User = '' then
      MsgBox(CustomMessage('AccSkipped'), mbInformation, MB_OK)
    else if (Length(User) < 3) or (Length(User) > 30) or
       not OnlyChars(User, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-') then
    begin
      MsgBox(CustomMessage('AccBadUser'), mbError, MB_OK);
      Result := False;
    end
    else if (Length(Pass) < 4) or
       not OnlyChars(Pass, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') then
    begin
      MsgBox(CustomMessage('AccBadPass'), mbError, MB_OK);
      Result := False;
    end;
  end
  else if (CurPageID = wpReady) and WizardIsComponentSelected('vlc') then
  begin
    VlcReady := False;
    DownloadPage.Clear;
    DownloadPage.Add('{#VlcUrl}', 'vlc-setup.exe', '{#VlcSha256}');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        VlcReady := True;
      except
        MsgBox(FmtMessage(CustomMessage('VlcFail'), [GetExceptionMessage]), mbInformation, MB_OK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure WriteSoulseekSettings;
var
  Lines: TArrayOfString;
  User, Pass, Dir, YDir, JDir, Key: String;
begin
  User := Trim(AccountPage.Values[0]);
  Pass := AccountPage.Values[1];
  Dir := DirPage.Values[0];
  { a fresh random key that only eozMP and slskd know }
  Key := GetSHA1OfString(GetDateTimeString('yyyymmddhhnnsszzz', #0, #0) + User + IntToStr(Random(2147483647))
    + ExpandConstant('{computername}{%PROCESSOR_IDENTIFIER}') + IntToStr(Random(2147483647)));
  ForceDirectories(Dir);
  ForceDirectories(ExtractFileDir(YmlPath));
  YDir := Dir;
  StringChangeEx(YDir, '''', '''''', True);   { YAML single-quoted string }
  SetArrayLength(Lines, 19);
  Lines[0] := '# Written by the eozMP installer. See "Soulseek Guide.txt" in the eozMP folder.';
  Lines[1] := 'soulseek:';
  Lines[2] := '  username: "' + User + '"';
  Lines[3] := '  password: "' + Pass + '"';
  Lines[4] := '';
  Lines[5] := 'directories:';
  Lines[6] := '  downloads: ''' + YDir + '''';
  Lines[7] := '';
  Lines[8] := 'web:';
  Lines[9] := '  authentication:';
  Lines[10] := '    username: slskd';
  Lines[11] := '    password: slskd';
  Lines[12] := '    api_keys:';
  Lines[13] := '      eozmp:';
  Lines[14] := '        key: ' + Key;
  Lines[15] := '        role: readwrite';
  Lines[16] := '        cidr: 127.0.0.1/32,::1/128';
  Lines[17] := '';
  Lines[18] := '# To share music with others, see section 6 of the Soulseek Guide.';
  SaveStringsToUTF8File(YmlPath, Lines, False);

  JDir := Dir;
  StringChangeEx(JDir, '\', '\\', True);
  SetArrayLength(Lines, 1);
  Lines[0] := '{"slskd_url": "http://localhost:5030", "slskd_key": "' + Key + '", "downloads_dir": "' + JDir + '"}';
  SaveStringsToUTF8File(ExpandConstant('{app}\slskd_setup.json'), Lines, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
begin
  if CurStep <> ssPostInstall then
    Exit;
  if WizardIsComponentSelected('slskd') and (not HasYml) and (Trim(AccountPage.Values[0]) <> '') then
    WriteSoulseekSettings;
  if WizardIsComponentSelected('vlc') and VlcReady then
  begin
    WizardForm.StatusLabel.Caption := CustomMessage('VlcRun');
    ShellExec('runas', ExpandConstant('{tmp}\vlc-setup.exe'), '/L=1033 /S', '', SW_SHOW,
      ewWaitUntilTerminated, Code);
  end;
end;
