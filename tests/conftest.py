import os
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
import json

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_redis():
    with patch('app.main.redis_client') as mock_redis:
        # Create an in-memory dictionary to simulate Redis storage
        storage = {}
        
        def mock_get(key):
            return storage.get(key)
            
        def mock_set(key, value, ex=None):
            storage[key] = value
            
        # Create instance with the mocked methods
        instance = mock_redis.return_value
        instance.get.side_effect = mock_get
        instance.set.side_effect = mock_set
        
        yield instance
        storage.clear()

@pytest.fixture
def mock_substrate():
    with patch('app.main.AsyncSubstrateInterface') as mock_substrate:
        # Create an async mock instance
        mock_instance = AsyncMock()
        
        # Set up the async context manager
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        
        # Set up async methods
        mock_instance.get_chain_head.return_value = "0x1234567890"
        
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
def mock_celery_task():
    with patch('app.main.update_dividends_cache.delay') as mock_task:
        mock_task.return_value = None
        yield mock_task 