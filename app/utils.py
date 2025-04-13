# utiis.py
from app.config import *
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext # type: ignore
from fastapi import HTTPException, Security
from typing import Optional
from jose import jwt, JWTError # type: ignore
from datetime import datetime, timedelta, timezone
import json
import os

import subprocess
import time


# Usage
# balance_info = get_tao_balance()
# print(balance_info)


# Load fake users database
def load_fake_users_db():
    try:
        with open("fake_users_db.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading fake_users_db.json: {e}")
        return {}

fake_users_db = load_fake_users_db()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Use a secure secret in production!
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Function to decode JWT token and get current user
def get_current_user(token: str = Security(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return {"username": username}  # You can add more user info here
    except JWTError:
        raise credentials_exception

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Function to authenticate the user
def authenticate_user(username: str, password: str) -> Optional[dict]:
    # Reload the database in case it was updated
    users_db = load_fake_users_db()
    user = users_db.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    try:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logging.error(e)
        raise
    
def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    
    

# Function to exhaust the query map asynchronously
async def exhaust(qmr):
    r = []
    async for k, v in await qmr:
        r.append((k, v))
    return r

# Asynchronous function to fetch the TaoDividendsPerSubnet data
async def fetch_tao_dividends():
    start = time.time()
    try:
        async with AsyncSubstrateInterface("wss://entrypoint-finney.opentensor.ai:443",
                                       ss58_format=SS58_FORMAT) as substrate:
            block_hash = await substrate.get_chain_head()
            tasks = [
                (netuid, substrate.query_map(
                    "SubtensorModule",
                    "TaoDividendsPerSubnet",
                    [netuid],
                    block_hash=block_hash
                )) for netuid in range(1, 51)
            ]
            results_dicts_list = []
            for netuid, future in tasks:
                try:
                    result = await exhaust(future)
                    results_dicts_list.extend([(netuid, decode_account_id(k), v.value) for k, v in result])
                except Exception as e:
                    logger.error(f"Error processing query map result: {e}")
                    continue

        elapsed = time.time() - start
        logger.info(f"Time elapsed for fetch_tao_dividends: {elapsed:.2f}s")
        logger.info(f"{type(results_dicts_list)} Async Results count: {len(results_dicts_list)}")
        return results_dicts_list, block_hash
    except Exception as e:
        logger.error(f"Error in fetch_tao_dividends: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch dividends: {str(e)}")