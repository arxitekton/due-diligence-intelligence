import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT  # company-due-diligence/


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/install_skill.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_install_creates_symlink(tmp_path: Path) -> None:
    r = _run(["--skills-dir", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    link = tmp_path / "company-due-diligence"
    assert link.is_symlink()
    assert link.resolve() == PKG.resolve()


def test_install_idempotent(tmp_path: Path) -> None:
    _run(["--skills-dir", str(tmp_path)])
    r = _run(["--skills-dir", str(tmp_path)])
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "company-due-diligence").is_symlink()


def test_refuses_real_dir_even_with_force(tmp_path: Path) -> None:
    (tmp_path / "company-due-diligence").mkdir()
    r = _run(["--skills-dir", str(tmp_path), "--force"])
    assert r.returncode == 1
    assert (tmp_path / "company-due-diligence").is_dir()
    assert not (tmp_path / "company-due-diligence").is_symlink()


def test_force_replaces_foreign_symlink(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    link = tmp_path / "company-due-diligence"
    link.symlink_to(other)
    r = _run(["--skills-dir", str(tmp_path), "--force"])
    assert r.returncode == 0, r.stderr
    assert link.resolve() == PKG.resolve()


def test_foreign_symlink_without_force_fails(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (tmp_path / "company-due-diligence").symlink_to(other)
    r = _run(["--skills-dir", str(tmp_path)])
    assert r.returncode == 1
