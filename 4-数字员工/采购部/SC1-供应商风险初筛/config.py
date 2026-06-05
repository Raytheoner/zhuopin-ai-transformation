import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
AUDIT_LOG_PATH = BASE_DIR / "audit_log.jsonl"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-sonnet-4-6"

XKY_API_BASE = os.environ.get("XKY_API_BASE", "https://openapi.xiekeyun.com")
XKY_APP_KEY = os.environ.get("XKY_APP_KEY", "")
XKY_APP_SECRET = os.environ.get("XKY_APP_SECRET", "")
XKY_OWNER_COMPANY_CODE = os.environ.get("XKY_OWNER_COMPANY_CODE", "")
XKY_ERP_CODE = os.environ.get("XKY_ERP_CODE", "")

SCORING_WEIGHTS = {
    "delivery": 0.35,
    "iqc": 0.30,
    "financial": 0.20,
    "single_source": 0.15,
}
