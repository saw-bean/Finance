import os
import tempfile

# Tests must never touch the live paper-trading database or audit log.
# Environment variables take priority over .env in pydantic-settings, and this runs before backend imports.
_tmp = tempfile.mkdtemp(prefix="alphaforge-test-")
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["LOG_FILE_PATH"] = f"{_tmp}/test_audit.log"
