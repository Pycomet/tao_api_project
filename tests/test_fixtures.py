import pytest
import json

def test_redis_fixture(mock_redis):
    # Test Redis get/set operations
    mock_redis.set("test_key", "test_value")
    assert mock_redis.get("test_key") == "test_value"
    
    # Test with JSON
    test_data = {"key": "value"}
    mock_redis.set("json_key", json.dumps(test_data))
    assert json.loads(mock_redis.get("json_key")) == test_data

@pytest.mark.asyncio
async def test_substrate_fixture(mock_substrate):
    # Test async context manager
    async with mock_substrate.return_value as substrate:
        # Test get_chain_head
        block_hash = await substrate.get_chain_head()
        assert block_hash == "0x1234567890"
        
        # Test query_map
        result = await substrate.query_map("SubtensorModule", "TaoDividendsPerSubnet", [1])
        assert result == [(b"5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY", {"value": 100})]
        
        # Test query
        result = await substrate.query("SubtensorModule", "TaoDividendsPerSubnet", [1, "test_hotkey"])
        assert result == {"value": 100}
        
        # Test query with non-existent hotkey
        result = await substrate.query("SubtensorModule", "TaoDividendsPerSubnet", [1, "nonexistent_hotkey"])
        assert result is None

def test_decode_account_id_fixture(mock_decode_account_id):
    # Test decode_account_id with valid key
    result = mock_decode_account_id(b"5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
    assert result == "test_hotkey"
    
    # Test decode_account_id with invalid key
    result = mock_decode_account_id(b"invalid_key")
    assert result == "nonexistent_hotkey"

def test_client_fixture(client):
    # Test root endpoint
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the TAO API Service"}
    
    # Test health endpoint
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"} 