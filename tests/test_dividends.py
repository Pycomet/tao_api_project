from fastapi.testclient import TestClient
from app.main import app
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
from app.redis_config import get_dividend_cache_key, get_block_hash_cache_key
from bittensor.core.chain_data import decode_account_id

client = TestClient(app)

@pytest.fixture
def mock_redis():
    with patch('app.main.redis_client') as mock_redis:
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
    with patch('app.main.AsyncSubstrateInterface') as mock_substrate:
        mock_instance = MagicMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.get_chain_head.async_return_value = "0x1234567890"
        
        async def mock_query_map(*args, **kwargs):
            return [(b"5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY", {"value": 100})]
        
        async def mock_query(*args, **kwargs):
            if args[2][1] == "nonexistent_hotkey":
                return None
            return {"value": 100}
        
        mock_instance.query_map = mock_query_map
        mock_instance.query = mock_query
        mock_substrate.return_value = mock_instance
        yield mock_substrate

@pytest.fixture
def mock_decode_account_id():
    with patch('app.main.decode_account_id') as mock_decode:
        def mock_decode_fn(key):
            if key == b"5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY":
                return "test_hotkey"
            return "nonexistent_hotkey"
        mock_decode.side_effect = mock_decode_fn
        yield mock_decode

@pytest.fixture
def mock_celery():
    with patch('app.main.celery') as mock_celery:
        yield mock_celery

@pytest.mark.asyncio
async def test_tao_dividends_no_cache(client, mock_redis, mock_substrate, mock_decode_account_id, mock_celery):
    response = client.get("/tao-dividends")
    assert response.status_code == 200
    data = response.json()
    
    assert "data" in data
    assert "block_hash" in data
    assert data["block_hash"] == "0x1234567890"
    
    # Verify Redis was called to set cache
    mock_redis.set.assert_called()
    # Verify Celery task was triggered
    mock_celery.delay.assert_called_once()

@pytest.mark.asyncio
async def test_tao_dividends_with_cache(client, mock_redis, mock_substrate, mock_decode_account_id, mock_celery):
    # Pre-populate cache
    block_hash = "0x1234567890"
    mock_redis.get.return_value = block_hash.encode()
    
    response = client.get("/tao-dividends")
    assert response.status_code == 200
    data = response.json()
    
    assert data["block_hash"] == block_hash
    
    # Verify substrate interface was not called for query_map
    assert not hasattr(mock_substrate.return_value.query_map, 'called')
    # Verify Celery task was not triggered
    mock_celery.delay.assert_not_called()

@pytest.mark.asyncio
async def test_specific_dividend_no_cache(client, mock_redis, mock_substrate):
    netuid = 1
    hotkey = "test_hotkey"
    
    response = client.get(f"/tao-dividends/{netuid}/{hotkey}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["netuid"] == netuid
    assert data["hotkey"] == hotkey
    assert data["dividend"] == 100
    assert data["cached"] == False
    
    # Verify cache was set
    cache_key = get_dividend_cache_key(netuid, hotkey)
    mock_redis.set.assert_called_with(cache_key, json.dumps(100), ex=None)

@pytest.mark.asyncio
async def test_specific_dividend_with_cache(client, mock_redis, mock_substrate):
    netuid = 1
    hotkey = "test_hotkey"
    cached_value = 100
    
    # Pre-populate cache
    cache_key = get_dividend_cache_key(netuid, hotkey)
    mock_redis.get.return_value = json.dumps(cached_value).encode()
    
    response = client.get(f"/tao-dividends/{netuid}/{hotkey}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["netuid"] == netuid
    assert data["hotkey"] == hotkey
    assert data["dividend"] == cached_value
    assert data["cached"] == True
    
    # Verify substrate interface was not called
    assert not hasattr(mock_substrate.return_value.query, 'called')

@pytest.mark.asyncio
async def test_specific_dividend_not_found(client, mock_redis, mock_substrate):
    # Mock substrate to return None for non-existent hotkey
    async def mock_query_none(*args, **kwargs):
        return None
    mock_substrate.return_value.query = mock_query_none
    
    response = client.get("/tao-dividends/1/nonexistent_hotkey")
    assert response.status_code == 404
    assert "detail" in response.json()

@pytest.mark.asyncio
async def test_get_dividends_cached(mock_redis, mock_substrate, mock_decode_account_id, mock_celery_task):
    # Set up mock Redis data
    mock_redis.get.return_value = json.dumps({
        "dividends": [
            {
                "hotkey": "test_hotkey",
                "amount": 100,
                "timestamp": "2024-01-01T00:00:00"
            }
        ],
        "last_updated": "2024-01-01T00:00:00"
    })
    
    response = client.get("/api/dividends")
    assert response.status_code == 200
    data = response.json()
    assert "dividends" in data
    assert len(data["dividends"]) == 1
    assert data["dividends"][0]["hotkey"] == "test_hotkey"
    assert data["dividends"][0]["amount"] == 100
    
    # Verify Celery task was not called (data was cached)
    mock_celery_task.assert_not_called()

@pytest.mark.asyncio
async def test_get_dividends_no_cache(mock_redis, mock_substrate, mock_decode_account_id, mock_celery_task):
    # Set up mock Redis to return None (no cache)
    mock_redis.get.return_value = None
    
    response = client.get("/api/dividends")
    assert response.status_code == 200
    data = response.json()
    assert "dividends" in data
    assert len(data["dividends"]) == 1
    assert data["dividends"][0]["hotkey"] == "test_hotkey"
    assert data["dividends"][0]["amount"] == 100
    
    # Verify Celery task was called
    mock_celery_task.assert_called_once()

@pytest.mark.asyncio
async def test_get_dividends_by_hotkey_cached(mock_redis, mock_substrate, mock_decode_account_id, mock_celery_task):
    # Set up mock Redis data
    mock_redis.get.return_value = json.dumps({
        "dividends": [
            {
                "hotkey": "test_hotkey",
                "amount": 100,
                "timestamp": "2024-01-01T00:00:00"
            }
        ],
        "last_updated": "2024-01-01T00:00:00"
    })
    
    response = client.get("/api/dividends/test_hotkey")
    assert response.status_code == 200
    data = response.json()
    assert "dividends" in data
    assert len(data["dividends"]) == 1
    assert data["dividends"][0]["hotkey"] == "test_hotkey"
    assert data["dividends"][0]["amount"] == 100
    
    # Verify Celery task was not called (data was cached)
    mock_celery_task.assert_not_called()

@pytest.mark.asyncio
async def test_get_dividends_by_hotkey_no_cache(mock_redis, mock_substrate, mock_decode_account_id, mock_celery_task):
    # Set up mock Redis to return None (no cache)
    mock_redis.get.return_value = None
    
    response = client.get("/api/dividends/test_hotkey")
    assert response.status_code == 200
    data = response.json()
    assert "dividends" in data
    assert len(data["dividends"]) == 1
    assert data["dividends"][0]["hotkey"] == "test_hotkey"
    assert data["dividends"][0]["amount"] == 100
    
    # Verify Celery task was called
    mock_celery_task.assert_called_once()

@pytest.mark.asyncio
async def test_get_dividends_by_nonexistent_hotkey(mock_redis, mock_substrate, mock_decode_account_id, mock_celery_task):
    # Set up mock Redis to return None (no cache)
    mock_redis.get.return_value = None
    
    response = client.get("/api/dividends/nonexistent_hotkey")
    assert response.status_code == 200
    data = response.json()
    assert "dividends" in data
    assert len(data["dividends"]) == 0
    
    # Verify Celery task was called
    mock_celery_task.assert_called_once() 