"""Exercise the Docker staging relocation code against real copied stamps."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

INIT = Path(__file__).resolve().parents[1] / "docker_init.bash"


def run_relocation(stage):
    source = INIT.read_text()
    marker = "<<'HERMES_PM_RELOCATE'"
    assert marker in source, "Docker staging must relocate the copied PM runtime"
    code = source.split(marker, 1)[1].split("\n", 1)[1].split("\nHERMES_PM_RELOCATE", 1)[0]
    return subprocess.run([sys.executable, "-", str(stage)], input=code,
                          text=True, capture_output=True)


def test_copied_docker_stamp_points_at_stage_without_changing_mount(tmp_path):
    mount = tmp_path / "mount"
    mount.mkdir()
    stamp = {"distribution": "docker", "baseVersion": "0.22.5",
             "pmRuntime": "/opt/hermes/pm-runtime"}
    (mount / "install-stamp.json").write_text(json.dumps(stamp))
    (mount / "pm-runtime").mkdir()
    (mount / "pm-runtime/pm-runtime.json").write_text("{}")
    stage = tmp_path / "writable stage"
    shutil.copytree(mount, stage)
    result = run_relocation(stage)
    assert result.returncode == 0, result.stderr
    relocated = json.loads((stage / "install-stamp.json").read_text())
    assert relocated == {**stamp, "pmRuntime": str(stage / "pm-runtime")}
    assert json.loads((mount / "install-stamp.json").read_text()) == stamp
    first = (stage / "install-stamp.json").read_bytes()
    assert run_relocation(stage).returncode == 0
    assert (stage / "install-stamp.json").read_bytes() == first


@pytest.mark.parametrize("distribution", [None, "git"])
def test_missing_or_non_docker_stamp_is_unchanged(tmp_path, distribution):
    path = tmp_path / "install-stamp.json"
    if distribution:
        path.write_text(json.dumps({"distribution": distribution, "pmRuntime": "keep"}))
    before = path.read_bytes() if path.exists() else None
    result = run_relocation(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (path.read_bytes() if path.exists() else None) == before


def test_missing_copied_runtime_fails_without_rewriting_stamp(tmp_path):
    path = tmp_path / "install-stamp.json"
    original = json.dumps({"distribution": "docker", "pmRuntime": "/opt/hermes/pm-runtime"})
    path.write_text(original)
    result = run_relocation(tmp_path)
    assert result.returncode != 0
    assert path.read_text() == original
