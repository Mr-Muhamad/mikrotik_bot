import os
import secrets
import sys

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN") or ""
if not BOT_TOKEN:
    print("FATAL: BOT_TOKEN is not set in .env file", file=sys.stderr)
    sys.exit(1)

raw_admin_ids = os.getenv("ADMIN_IDS", "")
try:
    ADMIN_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip()]
except ValueError:
    print("FATAL: ADMIN_IDS contains non-integer values", file=sys.stderr)
    sys.exit(1)
if not ADMIN_IDS:
    print("FATAL: ADMIN_IDS is not set or empty in .env file", file=sys.stderr)
    sys.exit(1)

ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY") or ""
if not ENCRYPTION_KEY:
    print("FATAL: ENCRYPTION_KEY is not set in .env file", file=sys.stderr)
    sys.exit(1)

# Validate Fernet key format and usability at startup
try:
    Fernet(ENCRYPTION_KEY.encode())
except ValueError as e:
    print(f"FATAL: ENCRYPTION_KEY is invalid: {e}", file=sys.stderr)
    sys.exit(1)

if len(ENCRYPTION_KEY) < 32:
    print("FATAL: ENCRYPTION_KEY must be at least 32 characters", file=sys.stderr)
    sys.exit(1)

BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")

DEFAULT_API_PORT = 8728
ROUTER_KEY_PREFIX = "discovered_"

# File transfer server settings (replaces plaintext FTP)
FILE_SERVER_PORT = int(os.getenv("FILE_SERVER_PORT", "8729"))
_env_file_secret = os.getenv("FILE_SERVER_SECRET", "")
FILE_SERVER_SECRET: str = _env_file_secret if _env_file_secret else secrets.token_urlsafe(32)
BOT_HOST = os.getenv("BOT_HOST", "")

# إعدادات المراقبة الدورية (بالثواني)
WATCHDOG_INTERVAL = 300
WATCHDOG_FIRST_DELAY = 1

# When True, the daily scheduled backup also performs a full system backup
# (system/backup/save + export). When False (default), the scheduler only
# backs up User Manager users and profiles. The full backup relies on FTP
# download which transmits the router password in cleartext; keep this
# disabled unless the bot runs inside an isolated management network.
SCHEDULE_FULL_BACKUP = os.getenv("SCHEDULE_FULL_BACKUP", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
