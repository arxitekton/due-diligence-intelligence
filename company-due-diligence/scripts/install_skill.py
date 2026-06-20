"""Install the company-due-diligence skill by symlinking into a skills directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Package dir is the parent of the scripts/ directory.
_PKG_DIR: Path = Path(__file__).resolve().parent.parent
_SKILL_NAME: str = "company-due-diligence"


def install_skill(*, skills_dir: Path, force: bool) -> Path:
    """Create a symlink ``skills_dir/company-due-diligence`` → package dir.

    Args:
        skills_dir: Directory that will contain the symlink.
        force: Replace an existing foreign symlink when True.

    Returns:
        The path of the (created or already-existing) symlink.

    Raises:
        ValueError: Target is a real directory (refused even with --force).
        FileExistsError: Target is a foreign symlink and --force was not given.
    """
    skills_dir.mkdir(parents=True, exist_ok=True)
    target: Path = skills_dir / _SKILL_NAME
    pkg: Path = _PKG_DIR.resolve()

    if target.is_symlink():
        if target.resolve() == pkg:
            # Already correct — idempotent success.
            return target
        # Foreign symlink.
        if not force:
            raise FileExistsError(
                f"{target} is a symlink pointing elsewhere; use --force to replace it."
            )
        target.unlink()
    elif target.exists():
        # Real directory (or regular file) — refuse unconditionally.
        raise ValueError(
            f"{target} is a real directory; refusing to remove it (run cleanup manually)."
        )

    target.symlink_to(pkg)
    return target


def main() -> int:
    """CLI entry point; returns exit code."""
    parser = argparse.ArgumentParser(
        description="Symlink the company-due-diligence skill package into a skills directory."
    )
    parser.add_argument(
        "--skills-dir",
        required=True,
        metavar="DIR",
        help="Target skills directory (created if absent).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing foreign symlink.",
    )
    args = parser.parse_args()

    try:
        link = install_skill(skills_dir=Path(args.skills_dir), force=args.force)
    except (FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
