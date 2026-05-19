"""로컬 커리어-잡 매칭 엔진"""

from __future__ import annotations

import os
from pathlib import Path

try:
	from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional runtime dependency
	load_dotenv = None


def _load_project_environment() -> None:
	root = Path(__file__).resolve().parents[2]
	workspace_root = Path(__file__).resolve().parents[3]

	candidate_paths = [
		workspace_root / ".env",
		root / ".env",
		root / "config" / ".env",
	]

	loaded = False
	if load_dotenv is not None:
		for env_path in candidate_paths:
			if env_path.exists():
				load_dotenv(env_path, override=False)
				loaded = True

	if loaded:
		os.environ.setdefault("JOB_CAREER_ENV_LOADED", "1")


_load_project_environment()

from .pipeline import generate_report, build_fallback_report
from .tools import OntologyCheckTool, WikiReadOnlyTool

__all__ = ["generate_report", "build_fallback_report", "OntologyCheckTool", "WikiReadOnlyTool"]
