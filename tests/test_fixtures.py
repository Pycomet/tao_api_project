import pytest
from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

# Codefred test credentials
TEST_API_KEY = "test_api_key"
TEST_API_SECRET = "test_api_secret"
AUTH_HEADERS = {
    "X-API-Key": TEST_API_KEY,
    "X-API-Secret": TEST_API_SECRET
}

def test_redis_fixture(mock_redis):
    # Test Redis get/set operations
    mock_redis.set("key", "value")
    assert mock_redis.get("key") == "value"
    
    # Test with JSON
    test_data = {"key": "value"}
    mock_redis.set("json_key", json.dumps(test_data))
    assert json.loads(mock_redis.get("json_key")) == test_data


def test_client_fixture():
    # Test root endpoint
    response = client.get("/api/v1")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the TAO API Service"}
    
    # Test health endpoint
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"} 