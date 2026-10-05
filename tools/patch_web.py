"""
Script to patch Pygbag's generated web assets for robust Android WebView execution.
Fixes:
1. Multi-format archive extraction (handles .apk, .tar.gz, and uncompressed .tar).
2. Sets autorun: 1, ume_block: 0, gui_divider: 1, xtermjs: 0.
3. Automatically unlocks audio/media on touch/click.
4. Ensures both .tar.gz and .tar exist so no matter what AAPT does, assets load.
"""

import os
import re
import gzip
import shutil
from pathlib import Path

def patch_web(web_dir="build/web"):
    web_path = Path(web_dir)
    index_file = web_path / "index.html"
    if not index_file.exists():
        print(f"Error: {index_file} not found")
        return False

    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Patch config block
    content = re.sub(r'xtermjs\s*:\s*["\']1["\']', 'xtermjs : "0"', content)
    content = re.sub(r'gui_divider\s*:\s*2', 'gui_divider : 1', content)
    content = re.sub(r'ume_block\s*:\s*1', 'ume_block : 0', content)
    content = re.sub(r'autorun\s*:\s*0', 'autorun : 1', content)
    content = re.sub(r'gui_debug\s*:\s*2', 'gui_debug : 0', content)

    # 2. Patch archive extraction in python custom_site()
    old_unpack_pattern = r"# unpack filesystem from compressed archive into work dir.*?platform\.run_main"
    new_unpack_code = '''# unpack filesystem from compressed archive into work dir
    import zipfile, tarfile
    candidates = [
        f"{bundle}.apk",
        f"{bundle}.tar.gz",
        f"{bundle}.tar",
        "faith.apk",
        "faith.tar.gz",
        "faith.tar",
        "faith-of-surviving.apk",
        "faith-of-surviving.tar.gz",
        "faith-of-surviving.tar"
    ]
    unpacked = False
    for archive_name in candidates:
        try:
            async with platform.fopen(archive_name, "rb") as archive:
                if archive_name.endswith(".apk") or archive_name.endswith(".zip"):
                    with zipfile.ZipFile(archive) as zip_ref:
                        zip_ref.extractall(appdir.as_posix())
                    unpacked = True
                    print(f"Successfully extracted {archive_name} via zipfile")
                    break
                elif archive_name.endswith(".gz") or archive_name.endswith(".tgz"):
                    with tarfile.open(fileobj=archive, mode="r:gz") as tar:
                        tar.extractall(path=appdir.as_posix(), filter='tar')
                    unpacked = True
                    print(f"Successfully extracted {archive_name} via tarfile gz")
                    break
                else:
                    with tarfile.open(fileobj=archive, mode="r:") as tar:
                        tar.extractall(path=appdir.as_posix(), filter='tar')
                    unpacked = True
                    print(f"Successfully extracted {archive_name} via tarfile plain")
                    break
        except Exception as e:
            print(f"Candidate {archive_name} skipped: {e}")
            pass

    platform.run_main'''

    content = re.sub(old_unpack_pattern, new_unpack_code, content, flags=re.DOTALL)

    # 3. Add auto-touch audio engagement script before </head>
    touch_helper = '''
    <script>
    (function() {
        function unlock() {
            if (window.MM) { window.MM.UME = true; }
        }
        window.addEventListener("touchstart", unlock, { passive: true });
        window.addEventListener("pointerdown", unlock, { passive: true });
        window.addEventListener("click", unlock, { passive: true });
    })();
    </script>
</head>'''
    if "</head>" in content and "window.MM.UME" not in content[:content.find("</head>")]:
        content = content.replace("</head>", touch_helper)

    with open(index_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully patched {index_file}")

    # 4. If any .tar.gz exists, also decompress a .tar copy so both exist
    for f in web_path.glob("*.tar.gz"):
        tar_out = f.with_suffix("") # removes .gz, leaving .tar
        if not tar_out.exists():
            try:
                with gzip.open(f, "rb") as gz_in:
                    with open(tar_out, "wb") as tar_file:
                        shutil.copyfileobj(gz_in, tar_file)
                print(f"Created fallback uncompressed {tar_out.name}")
            except Exception as e:
                print(f"Could not create .tar fallback for {f.name}: {e}")

    return True

if __name__ == "__main__":
    patch_web()
