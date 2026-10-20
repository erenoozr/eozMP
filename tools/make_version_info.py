"""eozMP.exe'nin Windows sürüm bilgisini (Özellikler > Ayrıntılar) musicplayer.py'deki APP_VERSION'dan yazar.
SignPath, imzaladığı dosyada ürün adı ve sürümün tutarlı olmasını ister.
Kullanım: python tools/make_version_info.py  ->  version_info.txt (PyInstaller --version-file)"""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
m = re.search(r'^APP_VERSION = "([0-9.]+)"', (root / "musicplayer.py").read_text(encoding="utf-8"), re.M)
if not m:
    sys.exit("APP_VERSION musicplayer.py içinde bulunamadı")
version = m.group(1)
nums = (version.split(".") + ["0"] * 4)[:4]
assert all(n.isdigit() for n in nums), version
t = ", ".join(nums)

(root / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({t}), prodvers=({t}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'eozMP'),
      StringStruct('FileDescription', 'eozMP music player'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'eozMP'),
      StringStruct('LegalCopyright', 'GPL-3.0'),
      StringStruct('OriginalFilename', 'eozMP.exe'),
      StringStruct('ProductName', 'eozMP'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")
print(version)
