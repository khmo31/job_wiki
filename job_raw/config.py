import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = "00_Raw"
JSON_ARCHIVE_DIR = "json_archive"
INDEX_FILE = "index.json"

# User preferences
USER_INTERESTS = [s.strip() for s in (os.getenv("USER_INTERESTS") or "").split(",") if s.strip()]

# Behavior
MOCK_MODE = True

# ALIO / API settings - prefer environment variables, fallback to .env in project root
ALIO_API_KEY = os.getenv("ALIO_API_KEY")
ALIO_ENDPOINT = os.getenv("ALIO_ENDPOINT") or "https://opendata.alio.go.kr/new/v1/recruit/list.do"
ALIO_PAGE_SIZE = int(os.getenv("ALIO_PAGE_SIZE", "50"))
ALIO_MAX_PAGES = int(os.getenv("ALIO_MAX_PAGES", "1"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "1.5"))

# Try to load .env files: project root → job_raw/ → job_raw/config/
_PROJECT_ROOT = BASE_DIR.parent
env_candidates = [_PROJECT_ROOT / ".env", BASE_DIR / ".env", BASE_DIR / "config" / ".env"]
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

# Detail endpoint & fetching policy
# If not provided via environment, set defaults
ALIO_DETAIL_ENDPOINT = os.getenv("ALIO_DETAIL_ENDPOINT") or "https://opendata.alio.go.kr/new/v1/recruit/detail.do"
# Candidate parameter names that detail endpoint might accept for an item id
ALIO_DETAIL_PARAM_NAMES = ["idx", "noticeNo", "recruitmentNo", "postNo", "jobId", "num", "recruitNo"]

# Request header defaults (many public portals block non-browser UA or require Referer)
ALIO_USER_AGENT = os.getenv("ALIO_USER_AGENT") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
ALIO_REFERER = os.getenv("ALIO_REFERER") or "https://opendata.alio.go.kr/new/v1/recruit/list.do"
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
# Maximum number of detail calls per run (None = unlimited)
DETAIL_MAX_DETAIL_CALLS = int(os.getenv("DETAIL_MAX_DETAIL_CALLS", "0")) or None  # 0 = unlimited


