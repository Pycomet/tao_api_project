from celery import Celery
from app.clients import DaturaClient, LLMClient
from app.config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, CACHE_TTL,
    get_dividend_cache_key, get_block_hash_cache_key, get_sentiment_cache_key,
    get_update_status_key, get_update_start_time_key, get_update_progress_key
)
import redis
import random
import asyncio
import logging
from async_substrate_interface.async_substrate import AsyncSubstrateInterface
from bittensor.core.chain_data import decode_account_id
from bittensor.core.settings import SS58_FORMAT
import json
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger
from datetime import datetime

# Configure logging
logger = get_task_logger(__name__)

# Initialize Celery
celery_app = Celery('tasks.worker', broker=f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    beat_schedule={
        'update-dividends-cache': {
            'task': 'tasks.worker.update_dividends_cache',
            'schedule': 60.0,  # Run every 120 seconds (2 minutes)
            'options': {
                'expires': 15.0,  # Task expires after 30 seconds if not picked up
            }
        },
    }
)

# Initialize Redis client
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    redis_client.ping()  # Test connection
    logger.info("Successfully connected to Redis")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    raise

async def exhaust(qmr):
    r = []
    async for k, v in await qmr:
        r.append((k, v))
    return r

async def _update():
    try:
        redis_client.set(get_update_status_key(), "in_progress", ex=CACHE_TTL)
        start_time = datetime.now()
        redis_client.set(get_update_start_time_key(), start_time.isoformat(), ex=CACHE_TTL)
        logger.info("Starting cache update")

        processed_count = 0
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
            
            for netuid, task in tasks:
                result = await exhaust(task)
                results_dicts_list.extend([(netuid, decode_account_id(k), v.value) for k, v in result])
                
            redis_client.set(get_block_hash_cache_key(), block_hash, ex=CACHE_TTL)
            logger.info(f"Cached block hash: {block_hash}")
            
            # Process and cache results
            for netuid, hotkey, value in results_dicts_list:
                try:
                    cache_key = get_dividend_cache_key(netuid, hotkey)
                    redis_client.set(cache_key, json.dumps(value), ex=CACHE_TTL)
                    logger.info(f"Cached: netuid={netuid}, hotkey={hotkey}")
                    processed_count += 1
                    
                    if processed_count % 1000 == 0:
                        print(f"Cache Key -- {cache_key}")
                        logger.info(f"Processed {processed_count} records")
                except Exception as e:
                    logger.error(f"Error processing hotkey {hotkey}: {e}")
                    continue

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Cache update completed in {duration:.2f} seconds")
        logger.info(f"Total records processed: {processed_count}")
        
        redis_client.set(get_update_status_key(), "completed", ex=CACHE_TTL)
        return processed_count

    except Exception as e:
        logger.error(f"Error in _update function: {e}")
        redis_client.set(get_update_status_key(), "failed", ex=CACHE_TTL)
        raise

@celery_app.task(bind=True, max_retries=3)
def update_dividends_cache(self):
    try:
        current_status = redis_client.get(get_update_status_key())
        if current_status and current_status.decode() == "in_progress":
            logger.info("Update already in progress, skipping periodic update")
            return "Update already in progress"

        logger.info("Starting periodic cache update")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            processed_count = loop.run_until_complete(_update())
            logger.info(f"Completed periodic cache update with {processed_count} records")
            return processed_count
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Error in periodic update_dividends_cache task: {e}")
        try:
            self.retry(exc=e, countdown=60)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded for periodic update_dividends_cache task")
            raise

# Initialize clients
datura_client = DaturaClient()
llm_client = LLMClient()

@celery_app.task(bind=True, max_retries=3)
async def analyze_sentiment(self, netuid: int) -> dict[str, any]:
    """
    Analyze sentiment for a given netuid by searching for tweets and calculating a sentiment score.
    Results are cached in Redis for CACHE_TTL seconds.
    
    Args:
        netuid (int): The netuid to analyze sentiment for
        
    Returns:
        dict[str, any]: A dictionary containing:
            - success (bool): Whether the analysis was successful
            - sentiment_score (str): The calculated sentiment score (-100 to 100)
            - tweets_analyzed (int): Number of tweets analyzed
            - error (str): Error message if any
            - cached (bool): Whether the result was retrieved from cache
    """
    try:
        # Search for tweets
        tweets_result = await datura_client.search_tweets(str(netuid))
        if not tweets_result:
            return {
                "success": False,
                "error": "No tweets found",
                "sentiment_score": "",
                "tweets_analyzed": 0
            }
        
        # Extract tweet texts
        tweets = [result.get("text") for result in tweets_result if "text" in result.keys()]
        if not tweets:
            return {
                "success": False,
                "error": "No valid tweets found",
                "sentiment_score": "",
                "tweets_analyzed": 0
            }
        
        # Combine tweets for analysis
        combined_tweets = "\n".join(tweets) 
        
        # Create sentiment prompt
        SENTIMENT_PROMPT = f"""Analyze the sentiment expressed in the following tweets and provide a single sentiment score ranging from -100 (very negative) to +100 (very positive), representing the overall sentiment of the provided tweets. Consider the nuances in language, opinions, and emotions expressed in the text.
        
        **Tweets:**
        {combined_tweets}
        
        Just return the overall sentiment score without any explanatory text
        """
        
        # Get sentiment analysis
        sentiment_result = await llm_client.query_chute_llm(SENTIMENT_PROMPT)

        cache_key = get_sentiment_cache_key(netuid)
        
        try:
            result = {
                "success": True,
                "sentiment_score": sentiment_result,
                "tweets_analyzed": len(tweets),
                "error": None,
                "cached": False
            }
            # Cache the successful result
            redis_client.set(cache_key, json.dumps(result), ex=CACHE_TTL)
            return result
        except (ValueError, TypeError):
            result = {
                "success": False,
                "error": "Invalid sentiment score format",
                "sentiment_score": "",
                "tweets_analyzed": len(tweets)
            }
            # Cache the error result
            redis_client.set(cache_key, json.dumps(result), ex=CACHE_TTL)
            return result
        
    except Exception as e:
        logger.error(f"Error in analyze_sentiment: {str(e)}")
        try:
            self.retry(exc=e, countdown=60)  # Retry after 1 minute
        except MaxRetriesExceededError:
            result = {
                "success": False,
                "error": str(e),
                "sentiment_score": "",
                "tweets_analyzed": 0
            }
            # Cache the error result
            redis_client.set(cache_key, json.dumps(result), ex=CACHE_TTL)
            return result

if __name__ == '__main__':
    celery_app.start()
