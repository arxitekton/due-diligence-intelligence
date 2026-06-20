"""Resolver for the deterministic output tree (no I/O)."""

from dataclasses import dataclass
from pathlib import Path

RUN_SUBDIRS = (
    "raw_sources",
    "raw_artifacts",
    "extracted_tables",
    "structured",
    "reports",
    "logs",
)


@dataclass(frozen=True)
class OutputPaths:
    root: Path
    company_slug: str
    run_id: str

    @property
    def company_dir(self) -> Path:
        return self.root / "companies" / self.company_slug

    @property
    def source_registry(self) -> Path:
        return self.company_dir / "source_registry.jsonl"

    @property
    def artifact_registry(self) -> Path:
        return self.company_dir / "artifact_registry.jsonl"

    @property
    def manifest(self) -> Path:
        return self.company_dir / "manifest.json"

    @property
    def latest_dir(self) -> Path:
        return self.company_dir / "latest"

    @property
    def history_dir(self) -> Path:
        return self.company_dir / "history"

    @property
    def run_dir(self) -> Path:
        return self.company_dir / "runs" / self.run_id

    def run_subdir(self, name: str) -> Path:
        if name not in RUN_SUBDIRS:
            raise ValueError(f"unknown run subdir: {name!r}")
        return self.run_dir / name
