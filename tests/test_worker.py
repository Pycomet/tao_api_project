import pytest
from unittest.mock import patch, MagicMock
import json
from tasks.worker import update_dividends_cache
from app.redis_config import get_dividend_cache_key, get_block_hash_cache_key
import asyncio

@pytest.fixture
def mock_redis():
    with patch('tasks.worker.redis_client') as mock_redis:
        # Create an in-memory dictionary to simulate Redis storage
        storage = {}
        
        def mock_get(key):
            return storage.get(key)
            
        def mock_set(key, value, ex=None):
            storage[key] = value
            
        mock_redis.get.side_effect = mock_get
        mock_redis.set.side_effect = mock_set
        yield mock_redis
        storage.clear()

@pytest.fixture
def mock_substrate():
    with patch('tasks.worker.AsyncSubstrateInterface') as mock_substrate:
        mock_instance = MagicMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.get_chain_head.async_return_value = "0x1234567890"
        
        async def mock_query_map(*args, **kwargs):
            return [(b"test_hotkey", {"value": 100})]
        
        mock_instance.query_map = mock_query_map
        mock_substrate.return_value = mock_instance
        yield mock_substrate

@pytest.mark.asyncio
async def test_update_dividends_cache(mock_redis, mock_substrate):
    # Run the task
    await update_dividends_cache()
    
    # Verify block hash was cached
    mock_redis.set.assert_any_call(
        get_block_hash_cache_key(),
        "0x1234567890",
        ex=None
    )
    
    # Verify dividend was cached
    mock_redis.set.assert_any_call(
        get_dividend_cache_key(1, "test_hotkey"),
        json.dumps(100),
        ex=None
    )

@pytest.mark.asyncio
async def test_update_dividends_cache_error(mock_redis, mock_substrate):
    # Mock substrate to raise an error
    async def mock_query_map_error(*args, **kwargs):
        raise Exception("Connection error")
    
    mock_substrate.return_value.query_map = mock_query_map_error
    
    # Run the task and expect it to handle the error
    with pytest.raises(Exception):
        await update_dividends_cache() 