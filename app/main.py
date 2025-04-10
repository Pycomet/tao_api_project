from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import logging
from async_substrate_interface.async_substrate import AsyncSubstrateInterface
from bittensor.core.chain_data import decode_account_id
from bittensor.core.settings import SS58_FORMAT
from typing import List, Tuple
import redis
import json
from app.redis_config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, CACHE_TTL,
    get_dividend_cache_key, get_block_hash_cache_key,
    get_update_status_key, get_update_start_time_key, get_update_progress_key
)
from tasks.worker import update_dividends_cache
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize Redis client
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    redis_client.ping()  # Test connection
    logger.info("Successfully connected to Redis")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    raise

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
async def root():
    return {"message": "Welcome to the TAO API Service"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/tao-dividends")
async def tao_dividends():
    """
    Endpoint to fetch Tao Dividends per Subnet with caching.
    """
    try:
        update_dividends_cache.delay()
        # Get cached block hash
        block_hash = redis_client.get(get_block_hash_cache_key())
        if not block_hash:
            logger.info("No cached block hash found, fetching fresh data")
            # If no cache, fetch fresh data
            results, block_hash = await fetch_tao_dividends()
            
            # Cache the fetched data
            try:
                for netuid, hotkey, value in results:
                    cache_key = get_dividend_cache_key(netuid, hotkey)
                    redis_client.set(cache_key, json.dumps(value), ex=CACHE_TTL)
                    logger.info(f"Cached: netuid={netuid}, hotkey={hotkey}")
                
                # Cache the block hash
                redis_client.set(get_block_hash_cache_key(), block_hash, ex=CACHE_TTL)
                logger.info(f"Cached block hash: {block_hash}")
            except Exception as e:
                logger.error(f"Error caching data: {e}")
            
            return {
                "data": [(hotkey, value) for _, hotkey, value in results],
                "block_hash": block_hash,
                "cached": False
            }
        
        # Get cached data
        results = []
        for netuid in range(1, 51):
            try:
                pattern = f"tao_dividend:{netuid}:*"
                keys = redis_client.keys(pattern)
                for key in keys:
                    try:
                        key_str = key.decode('utf-8')
                        hotkey = key_str.split(':')[-1]
                        value = redis_client.get(key)
                        if value:
                            results.append((hotkey, json.loads(value)))
                    except Exception as e:
                        logger.error(f"Error processing cache key {key}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error processing netuid {netuid}: {e}")
                continue
        
        logger.info(f"Returning {len(results)} cached dividend records")
        return {
            "data": results,
            "block_hash": block_hash.decode('utf-8'),
            "cached": True
        }
    except Exception as e:
        logger.error(f"Error in tao_dividends endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/tao-dividends/{netuid}/{hotkey}")
async def get_dividend(netuid: int, hotkey: str):
    """
    Get dividend for specific netuid and hotkey.
    """
    try:
        cache_key = get_dividend_cache_key(netuid, hotkey)
        cached_value = redis_client.get(cache_key)
        
        if cached_value:
            logger.info(f"Cache hit for {netuid}/{hotkey}")
            return {
                "netuid": netuid,
                "hotkey": hotkey,
                "dividend": json.loads(cached_value),
                "cached": True
            }
        
        logger.info(f"Cache miss for {netuid}/{hotkey}, fetching from chain")
        # If not in cache, fetch from chain
        try:
            async with AsyncSubstrateInterface("wss://entrypoint-finney.opentensor.ai:443",
                                         ss58_format=SS58_FORMAT) as substrate:
                block_hash = await substrate.get_chain_head()
                result = await substrate.query(
                    "SubtensorModule",
                    "TaoDividendsPerSubnet",
                    [netuid, hotkey],
                    block_hash=block_hash
                )
                
                if result and result.value:
                    # Cache the result
                    redis_client.set(cache_key, json.dumps(result.value), ex=CACHE_TTL)
                    logger.info(f"Cached new value for {netuid}/{hotkey}")
                    return {
                        "netuid": netuid,
                        "hotkey": hotkey,
                        "dividend": result.value,
                        "cached": False
                    }
                
                logger.warning(f"No dividend found for {netuid}/{hotkey}")
                raise HTTPException(status_code=404, detail="Dividend not found")
        except Exception as e:
            logger.error(f"Error querying substrate for {netuid}/{hotkey}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to query substrate: {str(e)}")
    except Exception as e:
        logger.error(f"Error in get_dividend endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# @app.get("/tao-dividends/status")
# async def get_update_status():
#     """Get the current status of the dividends cache update"""
#     try:
#         status = redis_client.get(get_update_status_key())
#         start_time = redis_client.get(get_update_start_time_key())
#         progress = redis_client.get(get_update_progress_key())
        
#         if not status:
#             return {
#                 "status": "not_started",
#                 "start_time": None,
#                 "progress": None
#             }
        
#         status = status.decode()
#         start_time = start_time.decode() if start_time else None
#         progress = progress.decode() if progress else None
        
#         return {
#             "status": status,
#             "start_time": start_time,
#             "progress": progress
#         }
#     except Exception as e:
#         logger.error(f"Error getting update status: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/tao-dividends/redis-info")
# async def get_redis_info():
#     """Get information about Redis keys and their types"""
#     try:
#         # Get all keys matching our patterns
#         dividend_keys = redis_client.keys("tao_dividend:*")
#         status_keys = redis_client.keys("tao_dividend:update_*")
        
#         # Get key types and TTLs
#         info = {
#             "total_keys": len(dividend_keys) + len(status_keys),
#             "keys_by_type": {},
#             "status_keys": {},
#             "dividend_keys_by_netuid": {}
#         }
        
#         # Process status keys
#         for key in status_keys:
#             key_str = key.decode('utf-8')
#             key_type = redis_client.type(key).decode()
#             ttl = redis_client.ttl(key)
#             info["status_keys"][key_str] = {
#                 "type": key_type,
#                 "ttl": ttl if ttl > 0 else None
#             }
        
#         # Process dividend keys
#         for key in dividend_keys:
#             key_str = key.decode('utf-8')
#             if key_str.startswith("tao_dividend:update_"):
#                 continue  # Skip status keys we already processed
                
#             key_type = redis_client.type(key).decode()
#             ttl = redis_client.ttl(key)
            
#             # Extract netuid from key
#             parts = key_str.split(':')
#             if len(parts) >= 3 and parts[1].isdigit():
#                 netuid = int(parts[1])
#                 if netuid not in info["dividend_keys_by_netuid"]:
#                     info["dividend_keys_by_netuid"][netuid] = {
#                         "count": 0,
#                         "ttl": ttl if ttl > 0 else None
#                     }
#                 info["dividend_keys_by_netuid"][netuid]["count"] += 1
        
#         # Count keys by type
#         all_keys = dividend_keys + status_keys
#         for key in all_keys:
#             key_type = redis_client.type(key).decode()
#             if key_type not in info["keys_by_type"]:
#                 info["keys_by_type"][key_type] = 0
#             info["keys_by_type"][key_type] += 1
        
#         return info
#     except Exception as e:
#         logger.error(f"Error getting Redis info: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

