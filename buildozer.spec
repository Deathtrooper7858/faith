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

# (str) Application versioning (method 1)
version = 2.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,pygame-ce

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = landscape

# (bool) Indicate if the application should be fullscreen to not
fullscreen = 1

# (list) Permissions
android.permissions = WAKE_LOCK

# (int) Target Android API, should be as high as possible.
android.api = 34

# (int) Minimum API your APK / AAB will support.
android.minapi = 21

# (int) Android SDK version to use
android.sdk = 34

# (str) The Android NDK version to use
android.ndk = 25b

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (list) List of Java .jar files to add to the libs so that pyjnius can access
# their classes. Don't add jars that you do not need, since extra jars can slow
# down the build process.
# android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# (list) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (list) Gradle dependencies to add
# android.gradle_dependencies =

# (bool) Skip byte compile for .py files
# android.no-byte-compile-python = False

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug when possible)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
