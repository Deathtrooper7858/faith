"""
Script to patch Pygbag's generated web assets for robust Android WebView execution.
Fixes:
1. Ensures both faith.apk and faith-of-surviving.apk exist so no 404 occurs.
2. Direct extraction of {bundle}.apk using zipfile.
3. Automatically sets MM.UME = True so it never blocks waiting for a touch.
4. Removes .tar and .tar.gz so Android Gradle asset merger never fails on duplicate resources.
5. Sets autorun: 1, ume_block: 0, gui_divider: 1, xtermjs: 0, gui_debug: 0.
"""

import os
import re
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

    # 2. Patch archive extraction in python custom_site() to use the exact matching .apk
    old_unpack_pattern = r"# unpack filesystem from compressed archive into work dir.*?platform\.run_main"
    new_unpack_code = '''# unpack filesystem from compressed archive into work dir
    import zipfile
    archive_name = f"{bundle}.apk"
    print(f"Opening archive: {archive_name}")
    async with platform.fopen(archive_name, "rb") as archive:
        with zipfile.ZipFile(archive) as zip_ref:
            zip_ref.extractall(appdir.as_posix())
    print(f"Successfully extracted {archive_name}")

    platform.run_main'''

    content = re.sub(old_unpack_pattern, new_unpack_code, content, flags=re.DOTALL)

    # 3. Prevent UME blocking loop by forcing MM.UME = True
    content = content.replace("if not platform.window.MM.UME:", "platform.window.MM.UME = True\n    if False:")

    # 4. Add error interceptor and auto-touch audio engagement script before </head>
    touch_helper = '''
    <script>
    window.addEventListener("error", function (e) {
        console.error("Intercepted Web Error:", e.message, e.filename, e.lineno);
        if (e.error && e.error.stack) { console.error(e.error.stack); }
        e.stopImmediatePropagation();
        e.preventDefault();
        return true;
    }, true);
    window.addEventListener("unhandledrejection", function (e) {
        console.error("Intercepted Promise Rejection:", e.reason);
        e.stopImmediatePropagation();
        e.preventDefault();
        return true;
    }, true);
    (function() {
        function unlock() {
            if (window.MM) { window.MM.UME = true; }
        }
        window.addEventListener("touchstart", unlock, { passive: true });
        window.addEventListener("pointerdown", unlock, { passive: true });
        window.addEventListener("click", unlock, { passive: true });
        unlock();
    })();
    </script>
</head>'''
    if "</head>" in content and "window.addEventListener(\"error\"" not in content:
        content = content.replace("</head>", touch_helper)

    with open(index_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully patched {index_file}")

    # 5. Ensure both faith.apk and faith-of-surviving.apk exist and are identical
    apk1 = web_path / "faith.apk"
    apk2 = web_path / "faith-of-surviving.apk"
    if apk2.exists():
        shutil.copy2(apk2, apk1)
        print(f"Synced {apk2.name} -> {apk1.name}")
    elif apk1.exists():
        shutil.copy2(apk1, apk2)
        print(f"Synced {apk1.name} -> {apk2.name}")

    # 6. Remove .tar and .tar.gz so Android Gradle asset merger doesn't encounter duplicate resource collisions
    for f in list(web_path.glob("*.tar")) + list(web_path.glob("*.tar.gz")):
        try:
            f.unlink()
            print(f"Removed redundant archive {f.name} to prevent AAPT merger collision")
        except Exception as e:
            print(f"Could not remove {f.name}: {e}")

    return True

if __name__ == "__main__":
    patch_web()
