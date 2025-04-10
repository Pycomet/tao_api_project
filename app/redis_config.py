import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Cache settings
CACHE_TTL = 240  # 2 minutes in seconds

# Cache key patterns
def get_dividend_cache_key(netuid: int, hotkey: str) -> str:
    return f"tao_dividend:{netuid}:{hotkey}"

def get_block_hash_cache_key() -> str:
    return "tao_dividend:block_hash"

def get_update_status_key() -> str:
    return "tao_dividend:update_status"

def get_update_start_time_key() -> str:
    return "tao_dividend:update_start_time"

def get_update_progress_key() -> str:
    return "tao_dividend:update_progress" 