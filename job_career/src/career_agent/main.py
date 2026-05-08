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


USER_PROFILE = (
    "저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. "
    "환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. "
    "공공기관 쪽으로 이직하고 싶습니다."
)


def run(user_profile: str | None = None) -> None:
    # If no profile provided, prompt user for input
    if user_profile is None:
        print("=" * 80)
        print("커리어 판단 에이전트")
        print("=" * 80)
        print("\n본인의 커리어 프로필을 입력해주세요.")
        print("(예시: 저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. ...)")
        print("\n엔터 두 번으로 입력 완료:")
        print("-" * 80)
        lines: list[str] = []
        empty_count = 0
        while True:
            try:
                line = input()
                if not line.strip():
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                    lines.append(line)
            except EOFError:
                break
        user_profile = "\n".join(lines).strip()
        if not user_profile:
            print("\n입력이 없어 기본 예시로 진행합니다.")
            user_profile = USER_PROFILE

    with redirect_stdout(sys.stderr):
        report = generate_report(user_profile)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
