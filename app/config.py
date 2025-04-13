from fastapi import FastAPI, HTTPException, APIRouter, Query
from fastapi.middleware.cors import CORSMiddleware
import time
import logging
from async_substrate_interface.async_substrate import AsyncSubstrateInterface
from bittensor.core.chain_data import decode_account_id
from bittensor.core.settings import SS58_FORMAT
from typing import List, Tuple
import redis
from datetime import timedelta
import json
from app.utils import get_current_user
from fastapi import Depends, HTTPException, status
from app.utils import fake_users_db
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError # type: ignore
from fastapi import HTTPException, Security
import aiohttp
import asyncio

from passlib.context import CryptContext # type: ignore
import os
from dotenv import load_dotenv
from datetime import datetime
from datura_py import Datura # type: ignore

load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

DATURA_API_KEY = os.getenv("DATURA_API_KEY")
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY")

BITTENSOR_WALLET_NAME = os.getenv("BITTENSOR_WALLET_NAME", "default")
BITTENSOR_WALLET_HOTKEY = os.getenv("BITTENSOR_WALLET_HOTKEY", "default")
BITTENSOR_MNEMONIC = os.getenv("BITTENSOR_MNEMONIC", None)

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

def get_sentiment_cache_key(netuid: int) -> str:
    return f"divident_sentiment:{netuid}"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Initialize Redis client
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    redis_client.ping()  # Test connection
    logger.info("Successfully connected to Redis")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    raise

router = APIRouter()
app = FastAPI()

