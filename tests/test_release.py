import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("release", Path(__file__).resolve().parents[1] / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.mark.parametrize("name", [
    ".env", "data/.env.local", ".git/config", "data/voice.wav", "../escape", "/absolute", "C:/absolute",
])
def test_release_rejects_private_and_unsafe_paths(name):
    with pytest.raises(ValueError):
        release.check_names([name])


def test_release_accepts_source_and_example_configuration():
    release.check_names([".env.example", "voicetoword/config.py", "docs/USAGE.txt"])


def test_embedded_code_comparison_ignores_build_path_but_detects_changes():
    first = compile("def function():\n    return 'original'", "first.py", "exec")
    relocated = compile("def function():\n    return 'original'", "elsewhere.py", "exec")
    changed = compile("def function():\n    return 'changed'", "first.py", "exec")
    assert release.code_signature(first) == release.code_signature(relocated)
    assert release.code_signature(first) != release.code_signature(changed)
