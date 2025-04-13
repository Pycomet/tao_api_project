import os
import sys
from pathlib import Path
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

import pytest
from fastapi.testclient import TestClient
from app.main import app
import json

# Set test environment variables
os.environ.setdefault("BITTENSOR_NETWORK", "test")
os.environ.setdefault("BITTENSOR_WALLET_PATH", str(Path("tests/wallets").absolute()))
os.environ.setdefault("BITTENSOR_WALLET_NAME", "test_wallet")
os.environ.setdefault("BITTENSOR_WALLET_HOTKEY", "test_hotkey")
os.environ.setdefault("BITTENSOR_MNEMONIC", "diamond like interest affair safe clarify lawsuit innocent beef van grief color")

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_redis():
    with patch('app.main.redis_client') as mock_redis:
        storage = {}

        def mock_get(key):
            return storage.get(key)

        def mock_set(key, value, ex=None):
            storage[key] = value

        instance = mock_redis.return_value
        instance.get.side_effect = mock_get
        instance.set.side_effect = mock_set

        yield instance
        storage.clear()

@pytest.fixture
def mock_substrate():
    with patch('app.main.AsyncSubstrateInterface') as mock_substrate:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None

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
        def decode_fn(key):
            if key == b"5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY":
                return "test_hotkey"
            return "nonexistent_hotkey"
        mock_decode.side_effect = decode_fn
        yield mock_decode

@pytest.fixture
def mock_celery_task():
    with patch('app.main.update_dividends_cache.delay') as mock_task:
        mock_task.return_value = None
        yield mock_task

@pytest.fixture
def mock_bittensor_wallet():
    with patch('bittensor_wallet.Wallet') as mock_wallet:
        instance = MagicMock()
        instance.exists.return_value = True
        instance.coldkeypub.ss58_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        instance.hotkey.ss58_address = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"
        instance.create.return_value = None
        instance.__str__.return_value = (
            f"Wallet (Name: 'test_wallet', Hotkey: 'test_hotkey', Path: {os.environ['BITTENSOR_WALLET_PATH']})"
        )
        mock_wallet.return_value = instance
        yield mock_wallet

@pytest.fixture
def mock_async_subtensor():
    with patch('bittensor.AsyncSubtensor') as mock_subtensor:
        instance = AsyncMock()
        instance.get_balance.return_value = 100.0
        instance.get_dividends_for_hotkey.return_value = 10.0
        instance.add_stake.return_value = {"success": True}
        instance.unstake.return_value = {"success": True}
        instance.transfer.return_value = {"success": True}

        mock_subtensor.return_value = instance
        yield mock_subtensor

@pytest.fixture(autouse=True)
def setup_test_environment():
    Path("tests/wallets").mkdir(parents=True, exist_ok=True)
    yield
    for file in Path("tests/wallets").glob("*"):
        file.unlink()
    Path("tests/wallets").rmdir()
