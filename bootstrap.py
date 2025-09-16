#!/usr/bin/env python3
import os
import sys
import platform
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# -----------------------
# Utility helpers
# -----------------------

def is_windows():
    return platform.system().lower().startswith("win")

def log(msg):
    print(msg)

def err(msg):
    print(msg, file=sys.stderr)

def run_checked(cmd, env=None, cwd=None, input_bytes=None, shell=False):
    if isinstance(cmd, str) and not shell:
        cmd = cmd.split()
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if input_bytes else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=cwd,
        shell=shell,
        text=False,
    )
    out, _ = p.communicate(input=input_bytes)
    text = out.decode("utf-8", errors="ignore")
    if p.returncode != 0:
        err(text)
        raise RuntimeError(f"Command failed: {cmd}")
    else:
        sys.stdout.write(text)

def have_cmd(name):
    return shutil.which(name) is not None

def load_env_file(path=".env"):
    m = {}
    p = Path(path)
    if not p.exists():
        return m
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        v = v.strip().strip("'").strip('"')
        m[k.strip()] = v
    return m

def download(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"Downloading: {url}")
    urllib.request.urlretrieve(url, dest)

def unzip(zip_path: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest)

def flutter_bin(flutter_root: Path):
    return str(flutter_root / "bin" / ("flutter.bat" if is_windows() else "flutter"))

def sdkmanager_bin(android_sdk_root: Path):
    base = android_sdk_root / "cmdline-tools" / "latest" / "bin"
    return str(base / ("sdkmanager.bat" if is_windows() else "sdkmanager"))

# -----------------------
# Install steps
# -----------------------

def ensure_prereqs():
    # Git
    if not have_cmd("git"):
        raise SystemExit("Git not found. Install Git and re-run.\nWindows: winget install -e --id Git.Git\nLinux: sudo apt install git")
    # Java 17
    if not have_cmd("java"):
        if is_windows() and have_cmd("winget"):
            log("Java 17 not found. Installing Microsoft OpenJDK 17 via winget...")
            try:
                run_checked(["winget","install","-e","--id","Microsoft.OpenJDK.17","--silent","--accept-package-agreements","--accept-source-agreements"])
            except Exception:
                pass
        if not have_cmd("java"):
            raise SystemExit("Java 17 not found on PATH. Install JDK 17 and re-run.\nLinux: sudo apt install openjdk-17-jdk")

def install_flutter(flutter_root: Path, env_map):
    flutter_exe = flutter_bin(flutter_root)
    if Path(flutter_exe).exists():
        log(f"Flutter already present at {flutter_root}")
        return
    channel = env_map.get("FLUTTER_CHANNEL","stable")
    ref = env_map.get("FLUTTER_REF","").strip()
    log(f"Installing Flutter into {flutter_root} ...")
    flutter_root.parent.mkdir(parents=True, exist_ok=True)
    if ref:
        run_checked(["git","clone","--depth","1","https://github.com/flutter/flutter", str(flutter_root)])
        run_checked(["git","fetch","origin", ref, "--depth","1"], cwd=str(flutter_root))
        run_checked(["git","checkout", ref], cwd=str(flutter_root))
    else:
        run_checked(["git","clone","--depth","1","-b", channel, "https://github.com/flutter/flutter", str(flutter_root)])

def install_android_cmdline(android_sdk: Path, env_map):
    sdk_mgr = Path(sdkmanager_bin(android_sdk))
    if sdk_mgr.exists():
        log("Android cmdline-tools already present.")
        return
    cmd_ver = env_map.get("ANDROID_CMDLINE_TOOLS","11076708")
    base = "win" if is_windows() else "linux"
    url = f"https://dl.google.com/android/repository/commandlinetools-{base}-{cmd_ver}_latest.zip"
    log(f"Installing Android cmdline-tools {cmd_ver} into {android_sdk} ...")
    android_sdk.mkdir(parents=True, exist_ok=True)
    latest = android_sdk / "cmdline-tools" / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        zpath = Path(td) / "cmdline-tools.zip"
        download(url, zpath)
        tmp_extract = Path(td) / "extract"
        unzip(zpath, tmp_extract)
        src = tmp_extract / "cmdline-tools"
        # Move contents under latest/
        for item in src.iterdir():
            dst = latest / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)

def install_android_packages(android_sdk: Path, env_map, flutter_root: Path):
    env = os.environ.copy()
    env["ANDROID_SDK_ROOT"] = str(android_sdk)
    env["ANDROID_HOME"] = str(android_sdk)
    env["PATH"] = os.pathsep.join([
        str(android_sdk / "cmdline-tools" / "latest" / "bin"),
        str(android_sdk / "platform-tools"),
        env.get("PATH",""),
    ])

    sdkmanager = sdkmanager_bin(android_sdk)
    if not Path(sdkmanager).exists():
        raise RuntimeError(f"sdkmanager not found at {sdkmanager}")

    # Accept licenses
    log("Accepting Android licenses...")
    try:
        run_checked([sdkmanager, f"--sdk_root={android_sdk}", "--licenses"], env=env, input_bytes=("y\n"*200).encode("utf-8"))
    except Exception as e:
        err(f"License acceptance had warnings: {e}")

    # Install packages
    platform_id    = env_map.get("ANDROID_PLATFORM", "android-34")
    build_tools_id = env_map.get("ANDROID_BUILD_TOOLS", "34.0.0")
    ndk_id         = env_map.get("ANDROID_NDK", "26.1.10909125")
    cmake_id       = env_map.get("ANDROID_CMAKE", "3.22.1")

    log("Installing Android SDK components...")
    pkgs = [
        "platform-tools",
        f"platforms;{platform_id}",
        f"build-tools;{build_tools_id}",
        f"cmake;{cmake_id}",
        f"ndk;{ndk_id}",
    ]
    run_checked([sdkmanager, f"--sdk_root={android_sdk}", *pkgs], env=env)

    # Configure Flutter + precache
    fl = flutter_bin(flutter_root)
    log("Configuring Flutter and precaching artifacts...")
    run_checked([fl, "config", "--android-sdk", str(android_sdk)], env=env)
    precache_args = ["--android"]
    if is_windows():
        precache_args.append("--windows")
    run_checked([fl, "precache", *precache_args], env=env)

def ensure_msvc_on_windows():
    if not is_windows():
        return
    # Detect via vswhere if VC tools are present
    vswhere_paths = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe",
    ]
    vswhere = next((p for p in vswhere_paths if p.exists()), None)
    have_vc_tools = False
    if vswhere:
        try:
            out = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True, stderr=subprocess.STDOUT).strip()
            have_vc_tools = len(out) > 0
        except subprocess.CalledProcessError:
            have_vc_tools = False

    if have_vc_tools:
        log("MSVC Build Tools detected.")
        return

    log("MSVC Build Tools not found. Attempting installation via winget (requires Admin)...")
    if not have_cmd("winget"):
        err("winget is not available. Please install Visual Studio 2022 Build Tools manually.")
        return

    try:
        # Minimal C++ workload; includeRecommended adds CMake/MSBuild helpers and Windows SDK.
        run_checked([
            "winget","install","-e","--id","Microsoft.VisualStudio.2022.BuildTools",
            "--override",
            "--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --passive --norestart --wait",
            "--accept-package-agreements","--accept-source-agreements"
        ])
        log("Winget install command issued. If it required elevation, re-run this script as Administrator or install manually.")
    except Exception as e:
        err(f"Winget installation failed or needs elevation. You can run this from an elevated PowerShell:\n"
            "winget install -e --id Microsoft.VisualStudio.2022.BuildTools --override \"--add Microsoft.VisualStudio.Workload.VCTools --includeRecommended --passive --norestart --wait\" --accept-package-agreements --accept-source-agreements")
        err(str(e))

# -----------------------
# Main
# -----------------------

def main():
    # Versions via .env
    env_map = load_env_file(".env")

    repo_root = Path.cwd()
    tooling = repo_root / ".tooling"
    flutter_root = tooling / "flutter"
    android_sdk  = tooling / "android-sdk"

    log(f"Tooling directory: {tooling}")
    tooling.mkdir(parents=True, exist_ok=True)

    ensure_prereqs()
    install_flutter(flutter_root, env_map)
    install_android_cmdline(android_sdk, env_map)
    install_android_packages(android_sdk, env_map, flutter_root)
    ensure_msvc_on_windows()

    # Final hints
    log("\nBootstrap complete.")
    log("Next steps:")
    log("  - Open VS Code here (settings already configured for local SDKs).")
    log("  - Run: flutter doctor -v")
    log("  - Android: flutter pub get && flutter build apk --release")
    if is_windows():
        log("  - Windows: flutter config --enable-windows-desktop && flutter build windows --release")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
