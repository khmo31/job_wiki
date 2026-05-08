import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = "00_Raw"
JSON_ARCHIVE_DIR = "json_archive"
INDEX_FILE = "index.json"

# User preferences
USER_INTERESTS = ["아두이노", "공장 게임", "자동화 로직"]

# Behavior
MOCK_MODE = True
TOP_N_SKILLS = 4

# Analysis / LLM settings
# Preferred low-cost analysis model (override via environment)
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL") or "gpt-4o-mini"
# Estimated cost per 1k tokens (USD) for the chosen model; override with env var if you know exact pricing
ANALYSIS_COST_PER_1K_TOKENS = float(os.getenv("ANALYSIS_COST_PER_1K_TOKENS", "0.003"))
# Maximum number of input characters to send to LLM (trim for cost). Set conservatively.
ANALYSIS_MAX_INPUT_CHARS = int(os.getenv("ANALYSIS_MAX_INPUT_CHARS", "4000"))
# Minimum characters required before considering an LLM call (avoid tiny prompts)
ANALYSIS_MIN_CHARS_TO_CALL_LLM = int(os.getenv("ANALYSIS_MIN_CHARS_TO_CALL_LLM", "80"))

# LLM request timeout (seconds) used by analyzer LLM calls. Increase to 60 for unstable networks.
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))

# LLM provider config: supports 'openai' or 'nvidia' (default: nvidia)
LLM_PROVIDER = os.getenv("LLM_PROVIDER") or "nvidia"

# NVIDIA Integrate API settings (used when LLM_PROVIDER=nvidia)
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL") or "deepseek-ai/deepseek-v4-flash"
NVIDIA_TIMEOUT = int(os.getenv("NVIDIA_TIMEOUT", "20"))

# NCS filtering mode for LLM invocation: 'off'|'soft'|'hard'
# - 'off' : do not short-circuit any job; LLM may be called for all eligible items (default)
# - 'soft': for non-technical NCS, sample a small fraction for LLM calls (audit), otherwise skip
# - 'hard': skip LLM for non-technical NCS items
NCS_FILTER_MODE = os.getenv("NCS_FILTER_MODE") or "off"
# When in 'soft' mode, sample rate for calling LLM on filtered items
SAMPLE_FILTERED_RATE = float(os.getenv("SAMPLE_FILTERED_RATE", "0.1"))
# Allow forcing LLM calls via environment/CLI for debugging
FORCE_LLM_OVERRIDE = str(os.getenv("FORCE_LLM_OVERRIDE", "0") or "0").lower() in ("1", "true", "yes")

# When building fallback context for LLM, target minimum characters
ANALYSIS_MIN_INPUT_CHARS = int(os.getenv("ANALYSIS_MIN_INPUT_CHARS", "800"))
# Force compose minimal context when building LLM payloads. Default: True
FORCE_COMPOSE_CONTEXT = str(os.getenv("FORCE_COMPOSE_CONTEXT", "1") or "1").lower() in ("1", "true", "yes")

# ALIO / API settings - prefer environment variables, fallback to .env in project root
ALIO_API_KEY = os.getenv("ALIO_API_KEY")
ALIO_ENDPOINT = os.getenv("ALIO_ENDPOINT")  # set to the ALIO endpoint if known
ALIO_PAGE_SIZE = int(os.getenv("ALIO_PAGE_SIZE", "50"))
ALIO_MAX_PAGES = int(os.getenv("ALIO_MAX_PAGES", "20"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "1.5"))

# Default number of items to process in batch reanalysis (can be overridden via .env)
REANALYZE_TARGET = int(os.getenv("REANALYZE_TARGET", "20"))

# Try to load .env files in the project root and config/ subfolder
env_candidates = [BASE_DIR / ".env", BASE_DIR / "config" / ".env"]
for env_path in env_candidates:
	if env_path.exists():
		try:
			with open(env_path, encoding="utf-8") as fh:
				for raw in fh:
					line = raw.strip()
					if not line or line.startswith("#") or "=" not in line:
						continue
					k, v = line.split("=", 1)
					k = k.strip()
					v = v.strip().strip('"').strip("'")
					# inject into os.environ so later os.getenv calls can pick up values
					import os as _os
					_os.environ.setdefault(k, v)
					if k == "ALIO_API_KEY" and not ALIO_API_KEY:
						ALIO_API_KEY = v
					if k == "ALIO_ENDPOINT" and not ALIO_ENDPOINT:
						ALIO_ENDPOINT = v
					if k == "ALIO_DETAIL_ENDPOINT":
						# allow explicit detail endpoint from .env
						try:
							ALIO_DETAIL_ENDPOINT = v
						except NameError:
							# variable might be defined later; env injected into os.environ is primary
							pass
		except Exception:
			pass

# Simple example NCS -> tags map (extend as needed)
NCS_MAP = {
	"자동화": ["자동화", "제어", "제어시스템", "제어로직", "공정제어"],
	"로봇": ["로봇", "임베디드", "로봇제어"],
	"생산관리": ["생산관리", "생산계획", "APS", "생산 스케줄", "자원 배분", "생산 계획"],
	"물류": ["물류", "로지스틱", "물류최적화", "물류관리", "풀필먼트", "배송", "창고관리", "재고"],
	"공정관리": ["공정관리", "공정", "공정최적화", "공정개선", "품질관리", "MES"],
	"시뮬레이션": ["시뮬레이션", "시뮬레이터", "제조 시뮬레이션", "디지털 트윈"],
	"PLC": ["PLC", "플라스틱로직컨트롤러"],
}

# Detail endpoint & fetching policy
# If not provided via environment, set defaults
ALIO_DETAIL_ENDPOINT = os.getenv("ALIO_DETAIL_ENDPOINT") or "https://opendata.alio.go.kr/openapi/service/rest/RecruitService/getRecruitDetail"
# Candidate parameter names that detail endpoint might accept for an item id
ALIO_DETAIL_PARAM_NAMES = ["idx", "noticeNo", "recruitmentNo", "postNo", "jobId", "num", "recruitNo"]

# Request header defaults (many public portals block non-browser UA or require Referer)
ALIO_USER_AGENT = os.getenv("ALIO_USER_AGENT") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
ALIO_REFERER = os.getenv("ALIO_REFERER") or "https://opendata.alio.go.kr/new/odaApiUserInqDataMng/openApiRecrutDetail.do"
# How to send request body: 'data' (form-encoded), 'json' (application/json), or 'params' (query string)
ALIO_REQUEST_BODY_MODE = os.getenv("ALIO_REQUEST_BODY_MODE", "data").lower()

# Build default headers dict; Content-Type is only set for form-encoded or params modes
ALIO_REQUEST_HEADERS = {}
ALIO_REQUEST_HEADERS["User-Agent"] = os.getenv("ALIO_USER_AGENT") or ALIO_USER_AGENT
ALIO_REQUEST_HEADERS["Referer"] = os.getenv("ALIO_REFERER") or ALIO_REFERER
if ALIO_REQUEST_BODY_MODE in ("data", "params"):
	ALIO_REQUEST_HEADERS.setdefault("Content-Type", "application/x-www-form-urlencoded")

# Candidate names for the API key parameter (some endpoints expect 'serviceKey' instead of 'apikey')
ALIO_API_KEY_PARAM_NAMES = [s for s in (os.getenv("ALIO_API_KEY_PARAM_NAMES") or "apikey,serviceKey,ServiceKey,service_key").split(",") if s]

# When to fetch detail: window in days from posted_date
DETAIL_FETCH_WINDOW_DAYS = int(os.getenv("DETAIL_FETCH_WINDOW_DAYS", "7"))
# Optional keywords (or NCS) to force detail fetch if matched in the list item
DETAIL_KEYWORDS = ["아두이노", "자동화", "로봇", "PLC"]
# Maximum number of detail calls per run (None = unlimited)
DETAIL_MAX_DETAIL_CALLS = int(os.getenv("DETAIL_MAX_DETAIL_CALLS", "0")) or None


