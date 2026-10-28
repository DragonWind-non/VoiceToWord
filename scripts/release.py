"""Build only committed files; inspect the executable before creating release ZIPs."""

import hashlib
import subprocess
import sys
import tempfile
import types
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

import tomllib
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_SUFFIXES = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".wma", ".mp4", ".log", ".pem", ".key", ".pfx", ".p12"}


def check_names(names):
    for name in names:
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or PureWindowsPath(name).drive or ".." in path.parts:
            raise ValueError(f"Unsafe archive path: {name}")
        if any(part in {".git", ".venv", "__pycache__", "build", "dist"} for part in path.parts):
            raise ValueError(f"Private/generated path in source: {name}")
        if path.name.startswith(".env") and path.name != ".env.example":
            raise ValueError(f"Private configuration in archive: {name}")
        if path.suffix.lower() in BLOCKED_SUFFIXES:
            raise ValueError(f"Private data in archive: {name}")


def code_signature(code):
    return (code.co_code, code.co_names, code.co_varnames, code.co_freevars, code.co_cellvars,
            tuple(code_signature(value) if isinstance(value, types.CodeType) else value for value in code.co_consts))


def inspect_exe(exe, source):
    archive = CArchiveReader(str(exe))
    names = list(archive.toc)
    if any(PurePosixPath(name.replace("\\", "/")).name == ".env" for name in names):
        raise ValueError("Private .env embedded in executable")
    lowered = "\n".join(names).lower()
    for required in ("portaudio", "certifi", "tcl", "tk"):
        if required not in lowered:
            raise ValueError(f"Missing runtime: {required}")
    modules = archive.open_embedded_archive("PYZ.pyz")
    for path in (source / "voicetoword").glob("*.py"):
        module = "voicetoword" if path.stem == "__init__" else f"voicetoword.{path.stem}"
        if path.stem == "__main__":
            continue
        expected = compile(path.read_bytes(), str(path), "exec", optimize=0)
        if code_signature(modules.extract(module)) != code_signature(expected):
            raise ValueError(f"Bundled module does not match source: {module}")


def checksums(files):
    return "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files)


def main():
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--"], cwd=ROOT, check=True)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    name = f"VoiceToWord-{version}"
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    source_zip = output / f"{name}-source.zip"
    subprocess.run(["git", "archive", "--format=zip", f"--output={source_zip}", "HEAD"], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix="voicetoword-build-") as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(source_zip) as archive:
            check_names(archive.namelist())
            if archive.testzip() is not None:
                raise ValueError("Source ZIP failed CRC check")
            archive.extractall(stage)
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
            "--distpath", str(stage / "output"), "--workpath", str(stage / "work"),
            str(stage / "VoiceToWord.spec"),
        ], cwd=stage, check=True)
        exe = stage / "output/VoiceToWord.exe"
        inspect_exe(exe, stage)
        final_exe = output / f"{name}.exe"
        final_exe.write_bytes(exe.read_bytes())
        readme = stage / "README.txt"
        readme.write_bytes((stage / "docs/USAGE.txt").read_bytes())
        example = stage / ".env.example"
        inner_sums = stage / "SHA256SUMS.txt"
        inner_sums.write_text(checksums([final_exe, example, readme]), encoding="utf-8")
        binary_zip = output / f"{name}-win-x64.zip"
        with zipfile.ZipFile(binary_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in (final_exe, example, readme, inner_sums):
                archive.write(path, path.name)
        with zipfile.ZipFile(binary_zip) as archive:
            check_names(archive.namelist())
            if archive.testzip() is not None:
                raise ValueError("Binary ZIP failed CRC check")
    (output / "SHA256SUMS.txt").write_text(checksums([final_exe, binary_zip, source_zip]), encoding="utf-8")
    print(f"Release built and archive checks passed: {binary_zip}")


if __name__ == "__main__":
    main()
