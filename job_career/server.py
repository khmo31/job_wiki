"""
Flask 서버: 채용공고 Wiki 매칭 API + 프론트엔드 UI

환경변수:
  JOB_CAREER_PYTHON  - 분석 서브프로세스용 Python 실행기 (기본: sys.executable)
  HOST               - 서버 바인딩 주소 (기본: 0.0.0.0)
  PORT               - 서버 포트 (기본: 5000)
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import json
import sys
import re
import socket
from functools import lru_cache
from pathlib import Path
import os
import importlib.util

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional runtime dependency
    load_dotenv = None


def _ensure_utf8_stdio() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


_ensure_utf8_stdio()


def _load_project_environment() -> None:
    if load_dotenv is None:
        return

    project_root = Path(__file__).resolve().parent
    workspace_root = project_root.parent
    candidate_paths = [
        workspace_root / ".env",
        project_root / ".env",
        project_root / "config" / ".env",
    ]

    for env_path in candidate_paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)


_load_project_environment()


def _mask_env_value(value: str | None) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "<set>"
    return f"{value[:4]}...{value[-4:]}"


def _log_env_state(prefix: str) -> None:
    print(
        f"[server] {prefix} OPENCODE_API_KEY={_mask_env_value(os.getenv('OPENCODE_API_KEY'))} "
        f"GROQ_API_KEY={_mask_env_value(os.getenv('GROQ_API_KEY'))} "
        f"OPENAI_API_KEY={_mask_env_value(os.getenv('OPENAI_API_KEY'))} "
        f"NVIDIA_API_KEY={_mask_env_value(os.getenv('NVIDIA_API_KEY'))} "
        f"OPENCODE_BASE_URL={os.getenv('OPENCODE_BASE_URL', 'https://opencode.ai/zen/go/v1')} "
        f"LLM_EXTRACT_MODEL={os.getenv('LLM_EXTRACT_MODEL', 'deepseek-v4-flash')}",
        file=sys.stderr,
    )

# 서브프로세스 Python 실행기: 환경변수 우선, 없으면 현재 인터프리터 사용
PY_EXEC = os.getenv("JOB_CAREER_PYTHON") or sys.executable

# 프로젝트 루트 (job_career/)
PROJECT_ROOT = Path(__file__).resolve().parent
# 채용공고 Raw 데이터 경로 (job_wiki/00_Raw)
RAW_ROOT = PROJECT_ROOT.parent / "job_wiki" / "00_Raw"


_log_env_state("startup")


def _parse_last_json_blob(text: str):
    decoder = json.JSONDecoder()
    for start_index in range(len(text) - 1, -1, -1):
        if text[start_index] != "{":
            continue
        try:
            payload, end_index = decoder.raw_decode(text[start_index:])
        except Exception:
            continue
        trailing = text[start_index + end_index :].strip()
        if not trailing:
            return payload
    raise ValueError("no json object found in subprocess output")


def _analysis_serial_from_name(file_name: str) -> str | None:
    match = re.search(r"_(\d+)\.md$", file_name.strip())
    if not match:
        return None
    return match.group(1)


def _extract_raw_archive_section(text: str) -> str | None:
    start_match = re.search(r"(?m)^## 원본 공고\(아카이브\)\s*$", text)
    if not start_match:
        return None

    start_index = start_match.start()
    end_match = re.search(r"(?m)^### Raw JSON\s*$", text[start_index:])
    end_index = start_index + end_match.start() if end_match else len(text)

    archive = text[start_index:end_index].strip()
    return archive or None


@lru_cache(maxsize=256)
def _resolve_raw_archive(analysis_file: str) -> dict[str, str] | None:
    serial = _analysis_serial_from_name(analysis_file)
    if not serial or not RAW_ROOT.exists():
        return None

    serial_pattern = re.compile(rf'"recrutPblntSn"\s*:\s*{re.escape(serial)}\b')

    for raw_path in RAW_ROOT.rglob("*.md"):
        try:
            raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if not serial_pattern.search(raw_text):
            continue

        archive = _extract_raw_archive_section(raw_text)
        if not archive:
            continue

        try:
            relative_path = raw_path.relative_to(PROJECT_ROOT.parent)
        except Exception:
            relative_path = raw_path

        return {
            "analysis_file": analysis_file,
            "raw_file": str(relative_path).replace("\\", "/"),
            "archive": archive,
        }

    return None


# Flask 앱 초기화 (정적 파일 제공)
app = Flask(__name__, static_folder=str(PROJECT_ROOT / "frontend"), static_url_path="")

# CORS 설정
CORS(app)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """사용자 커리어 프로필을 입력받아 분석을 실행합니다."""
    try:
        data = request.get_json() or {}
        profile = (data.get("profile") or "").strip()

        if not profile:
            return jsonify({"status": "error", "error": "프로필이 필요합니다"}), 400

        _log_env_state("analyze request")

        # subprocess 실행
        cmd_list = [str(PY_EXEC), str(PROJECT_ROOT / "src" / "career_agent" / "main_batch.py"), profile]
        env_copy = os.environ.copy()
        env_copy.setdefault("PYTHONIOENCODING", "utf-8")
        env_copy.setdefault("PYTHONUTF8", "1")

        print(
            f"[server] subprocess env OPENCODE_API_KEY={_mask_env_value(env_copy.get('OPENCODE_API_KEY'))} "
            f"LLM_EXTRACT_MODEL={env_copy.get('LLM_EXTRACT_MODEL', 'deepseek-v4-flash')}",
            file=sys.stderr,
        )

        proc = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=env_copy,
        )

        if proc.stderr:
            print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n")

        if proc.returncode != 0:
            return jsonify({"status": "error", "error": f"subprocess failed: {proc.stderr[:200]}"}), 500

        # 출력 파싱
        try:
            result_data = _parse_last_json_blob(proc.stdout.strip())
            return jsonify({"status": "success", "data": result_data}), 200
        except Exception as e:
            return jsonify({"status": "error", "error": f"parse error: {str(e)}"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "error": "timeout"}), 504
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/archive", methods=["POST"])
def archive_detail():
    """분석 카드의 상세보기 버튼용: 00_Raw 원문 공고 아카이브를 반환합니다."""
    payload = request.get_json() or {}
    analysis_file = (payload.get("file") or "").strip()

    if not analysis_file:
        return jsonify({"status": "error", "error": "분석 파일명이 필요합니다."}), 400

    resolved = _resolve_raw_archive(analysis_file)
    if not resolved:
        return jsonify({"status": "error", "error": "원문 공고 아카이브를 찾지 못했습니다."}), 404

    return jsonify({"status": "success", "data": resolved}), 200


@app.route("/api/debug-run", methods=["POST"])
def debug_run():
    """디버그용: main_batch.run_batch를 직접 호출하고 raw 출력을 반환합니다."""
    payload = request.get_json() or {}
    profile = (payload.get("profile") or "").strip()
    if not profile:
        return jsonify({"status": "error", "error": "프로필 입력이 필요합니다."}), 400
    try:
        mb_path = PROJECT_ROOT / "src" / "career_agent" / "main_batch.py"
        spec = importlib.util.spec_from_file_location("career_agent_main_batch", str(mb_path))
        mb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mb)  # type: ignore
        output = mb.run_batch(profile)
        try:
            data = json.loads(output)
            return jsonify({"status": "success", "data": data, "raw": output}), 200
        except Exception:
            return jsonify({"status": "partial", "error": "파싱 실패", "raw": output}), 200
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        try:
            with open(PROJECT_ROOT / "server_debug.log", "a", encoding="utf-8") as fh:
                fh.write("--- DEBUG-RUN ERROR ---\n")
                fh.write(repr(exc) + "\n")
                fh.write(tb + "\n")
        except Exception:
            pass
        return jsonify({"status": "error", "error": str(exc), "trace": tb}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """헬스 체크 엔드포인트"""
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def index():
    """프론트엔드 UI 제공"""
    return send_from_directory(PROJECT_ROOT / "frontend", "index.html")


if __name__ == "__main__":
    def _port_in_use(host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((host, port)) == 0

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))

    if _port_in_use("127.0.0.1", port):
        print(f"포트 {port}가 이미 사용 중입니다. 기존 서버가 실행 중일 수 있어 새 서버를 시작하지 않습니다.")
        sys.exit(0)

    print("=" * 60)
    print("Job Wiki - 매칭 서버")
    print("=" * 60)
    print(f"  서버: http://localhost:{port}")
    print(f"  Python: {PY_EXEC}")
    print(f"  Raw 데이터: {RAW_ROOT}")
    print(f"  OPENCODE_API_KEY: {_mask_env_value(os.getenv('OPENCODE_API_KEY'))}")
    print(f"  LLM_EXTRACT_MODEL: {os.getenv('LLM_EXTRACT_MODEL', 'deepseek-v4-flash')}")
    print(f"  API: POST /api/analyze")
    print("=" * 60)
    app.run(debug=False, use_reloader=False, host=host, port=port)
