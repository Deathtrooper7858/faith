[app]

# (str) Title of your application
title = Faith of Surviving

# (str) Package name
package.name = faithofsurviving

# (str) Package domain (needed for android/ios packaging)
package.domain = org.deathtrooper.faith

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,jpeg,json,txt

# (list) List of directory to include
source.include_dirs = assets, faith

# (list) List of exclusions using pattern matching
source.exclude_dirs = tests, docs, bin, .git, .github, dist, build, saves

# (str) Application versioning
version = 2.0.0

# (list) Application requirements (usar 'pygame' para activar la receta oficial de SDL2 de p4a)
requirements = python3,pygame

# (str) Bootstrap to use (sdl2 para pygame)
p4a.bootstrap = sdl2

# (str) Supported orientation
orientation = landscape

# (bool) Indicate if the application should be fullscreen
fullscreen = 1

# (list) Permissions
android.permissions = WAKE_LOCK

# (int) Target Android API
android.api = 33

# (int) Minimum API supported
android.minapi = 21

# (int) Android SDK version to use
android.sdk = 33

# (str) The Android NDK version to use
android.ndk = 25b

# (bool) Use --private data storage
android.private_storage = True

# (list) The Android archs to build for (arm64-v8a es compatible con prácticamente todos los teléfonos modernos)
android.archs = arm64-v8a

# (bool) enables Android auto backup feature
android.allow_backup = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug when possible)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1
