"""
Script to patch Pygbag's generated web assets for robust Android WebView execution.
Fixes:
1. Uses Pygbag's zip archive (*.apk) which Android AAPT does not strip or decompress.
2. Removes .tar and .tar.gz so Android Gradle asset merger never fails on duplicate resources.
3. Sets autorun: 1, ume_block: 0, gui_divider: 1, xtermjs: 0.
4. Adds auto-unlock for media/audio on touch.
"""

import os
import re
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

    # 2. Patch archive extraction in python custom_site() to use the .apk zip archive
    old_unpack_pattern = r"# unpack filesystem from compressed archive into work dir.*?platform\.run_main"
    new_unpack_code = '''# unpack filesystem from compressed archive into work dir
    import zipfile
    apk_candidates = ["faith.apk", "faith-of-surviving.apk", f"{bundle}.apk"]
    extracted = False
    for apk_name in apk_candidates:
        try:
            async with platform.fopen(apk_name, "rb") as archive:
                with zipfile.ZipFile(archive) as zip_ref:
                    zip_ref.extractall(appdir.as_posix())
                extracted = True
                print(f"Successfully extracted {apk_name}")
                break
        except Exception as e:
            print(f"Attempt on {apk_name}: {e}")
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

    # 4. Remove .tar and .tar.gz so Android Gradle asset merger doesn't encounter duplicate resource collisions
    for f in list(web_path.glob("*.tar")) + list(web_path.glob("*.tar.gz")):
        try:
            f.unlink()
            print(f"Removed redundant archive {f.name} to prevent AAPT merger collision")
        except Exception as e:
            print(f"Could not remove {f.name}: {e}")

    return True

if __name__ == "__main__":
    patch_web()
