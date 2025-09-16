# Local (per-project) Flutter + Android SDK bootstrap

This project includes:
- `bootstrap.py` — downloads Flutter + Android SDK into `.tooling/` inside this repo, installs the required Android components, and (on Windows) installs Visual Studio Build Tools (Desktop C++) using winget if missing.
- `.vscode/settings.json` — points the Flutter VS Code extension to the project-local Flutter SDK and sets environment variables so terminals use the local Android SDK.

Works on:
- Windows: Android + Windows builds (MSVC required; auto-installs with winget if missing)
- Linux: Android builds (install your distro’s dev packages if you also want Linux desktop builds)

## Quick start
1) Optional: pin versions in `.env` (copy from `.env.example`). Defaults are provided.
2) Run bootstrap:
   ```
   python3 bootstrap.py
   ```
   - On first run, it will download Flutter and Android SDK into `.tooling/`.
   - On Windows, if MSVC Build Tools are not installed, it will try to install them with winget.

3) Open VS Code in this folder (or run `code .`). The Flutter extension will use:
   - Flutter SDK: `${workspaceFolder}/.tooling/flutter`
   - Terminals will have `ANDROID_SDK_ROOT` and PATH set to `.tooling/android-sdk`.

4) Build:
   - Android:
     ```
     flutter pub get
     flutter build apk --release
     ```
   - Windows (on Windows):
     ```
     flutter config --enable-windows-desktop
     flutter build windows --release
     ```

## Notes
- All tooling is inside this repo’s `.tooling/` folder — easy to delete/recreate per project.
- `flutter config --android-sdk` is set to this project’s SDK to keep the extension happy. It’s a user-level setting; re-running bootstrap in another project will update it again.
- On Linux, to also build Linux desktop apps, install system packages (example for Ubuntu):
  ```
  sudo apt update
  sudo apt install -y git curl unzip zip openjdk-17-jdk clang cmake ninja-build pkg-config libgtk-3-dev
  ```
