"""배치 모드 엔트리포인트: CLI 인자로 프로필을 받아 JSON 결과를 출력합니다."""
from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from pathlib import Path


def _ensure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


_ensure_utf8_stdio()

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from career_agent.pipeline import generate_report


def _parse_optional_json(raw_value: str | None) -> dict[str, list[str]] | None:
    if not raw_value:
        return None

    try:
        parsed = json.loads(raw_value)
    except Exception:
        return None

    return parsed if isinstance(parsed, dict) else None


def run_batch(
    user_profile: str,
    supplemental_selections: dict[str, list[str]] | None = None,
    analysis_phase: str = "initial",
) -> str:
    try:
        with redirect_stdout(sys.stderr):
            report = generate_report(
                user_profile,
                supplemental_selections=supplemental_selections,
                analysis_phase=analysis_phase,
            )
        return json.dumps(report, ensure_ascii=False)
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "error": str(exc),
                "recommended_institutions": [],
            },
            ensure_ascii=False,
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "프로필 입력이 필요합니다."}, ensure_ascii=False))
        sys.exit(1)

    profile = sys.argv[1]
    supplemental = _parse_optional_json(sys.argv[2] if len(sys.argv) > 2 else None)
    analysis_phase = sys.argv[3] if len(sys.argv) > 3 else "initial"
    output = run_batch(profile, supplemental, analysis_phase=analysis_phase)
    print(output)
