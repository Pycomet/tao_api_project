from fastapi.testclient import TestClient
from app.main import app
import time
import pytest
from unittest.mock import patch, MagicMock
import json

client = TestClient(app)

# Test credentials
TEST_USERNAME = "codefred"
TEST_PASSWORD = "secret123"
TEST_ACCESS_TOKEN = "test_access_token"

@pytest.fixture
def mock_redis():
    with patch('app.main.redis_client') as mock:
        mock.get.return_value = None
        mock.set.return_value = None
        yield mock

@pytest.fixture
def mock_substrate():
    with patch('app.main.AsyncSubstrateInterface') as mock:
        instance = MagicMock()
        instance.__aenter__.return_value = instance
        instance.__aexit__.return_value = None
        instance.get_chain_head.return_value = "0x1234567890"
        instance.query_map.return_value = [(b"test_key", {"value": 100})]
        instance.query.return_value = {"value": 100}
        mock.return_value = instance
        yield mock

def test_login():
    # Test successful login with form data
    form_data = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD
    }
    response = client.post("/api/v1/login", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    return data["access_token"]

def test_get_all_dividends(mock_redis, mock_substrate):
    # Get access token
    access_token = test_login()
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = client.get("/api/v1/tao-dividends", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data.keys()) > 0

def test_get_specific_dividend(mock_redis, mock_substrate):
    # Get access token
    access_token = test_login()
    headers = {"Authorization": f"Bearer {access_token}"}
    
    mock_redis.get.return_value = json.dumps(100).encode()
    response = client.get("/api/v1/tao-dividends?netuid=18&hotkey=5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["dividend"], int)
    assert data["cached"]

def test_unauthorized_access():
    response = client.get("/api/v1/tao-dividends")
    assert response.status_code == 401

def test_invalid_credentials():
    invalid_headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/api/v1/tao-dividends", headers=invalid_headers)
    assert response.status_code == 401

def test_invalid_login():
    # Test login with invalid credentials using form data
    invalid_form_data = {
        "username": "invalid_user",
        "password": "invalid_password"
    }
    response = client.post("/api/v1/login", data=invalid_form_data)
    assert response.status_code == 401 