# from fastapi.testclient import TestClient
# from app.main import app
# import pytest
# from unittest.mock import patch, MagicMock, AsyncMock
# import json

# client = TestClient(app)

# # Test credentials
# TEST_USERNAME = "codefred"
# TEST_PASSWORD = "secret123"
# TEST_ACCESS_TOKEN = "test_access_token"

# # Test wallet credentials
# TEST_WALLET_MNEMONIC = "diamond like interest affair safe clarify lawsuit innocent beef van grief color"
# TEST_HOTKEY = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"
# TEST_NETUID = 18

# # API Keys
# DATURA_API_KEY = "dt_$q4qWC2K5mwT5BnNh0ZNF9MfeMDJenJ-pddsi_rE1FZ8"
# CHUTES_API_KEY = "cpk_9402c24cc755440b94f4b0931ebaa272.7a748b60e4a557f6957af9ce25778f49.8huXjHVlrSttzKuuY0yU2Fy4qEskr5J0"

# @pytest.fixture
# def mock_redis():
#     with patch('app.main.redis_client') as mock:
#         mock.get.return_value = None
#         mock.set.return_value = None
#         yield mock

# @pytest.fixture
# def mock_substrate():
#     with patch('app.main.AsyncSubstrateInterface') as mock:
#         instance = MagicMock()
#         instance.__aenter__.return_value = instance
#         instance.__aexit__.return_value = None
#         instance.get_chain_head.return_value = "0x1234567890"
#         instance.query_map.return_value = [(b"test_key", {"value": 100})]
#         instance.query.return_value = {"value": 100}
#         mock.return_value = instance
#         yield mock

# @pytest.fixture
# def mock_datura():
#     with patch('app.main.DaturaClient') as mock:
#         instance = MagicMock()
#         instance.search_tweets.return_value = {
#             "tweets": [
#                 {"text": "Bittensor netuid 18 is amazing!", "created_at": "2024-04-10T12:00:00Z"},
#                 {"text": "Great progress on Bittensor netuid 18", "created_at": "2024-04-10T11:00:00Z"}
#             ]
#         }
#         mock.return_value = instance
#         yield mock

# @pytest.fixture
# def mock_chutes():
#     with patch('app.main.ChutesClient') as mock:
#         instance = MagicMock()
#         instance.analyze_sentiment.return_value = {"sentiment_score": 75}
#         mock.return_value = instance
#         yield mock

# @pytest.fixture
# def mock_wallet():
#     with patch('app.main.BittensorWallet') as mock:
#         instance = MagicMock()
#         instance.add_stake.return_value = {"success": True}
#         instance.unstake.return_value = {"success": True}
#         mock.return_value = instance
#         yield mock

# def test_login():
#     form_data = {
#         "username": TEST_USERNAME,
#         "password": TEST_PASSWORD
#     }
#     response = client.post("/api/v1/login", data=form_data)
#     assert response.status_code == 200
#     data = response.json()
#     assert "access_token" in data
#     return data["access_token"]

# def test_trading_with_positive_sentiment(mock_redis, mock_substrate, mock_datura, mock_chutes, mock_wallet):
#     # Get access token
#     access_token = test_login()
#     headers = {"Authorization": f"Bearer {access_token}"}
    
#     # Test trading with positive sentiment
#     params = {
#         "netuid": TEST_NETUID,
#         "hotkey": TEST_HOTKEY,
#         "trade": True
#     }
    
#     response = client.get("/api/v1/tao-dividends", params=params, headers=headers)
#     assert response.status_code == 200
#     data = response.json()
    
#     # Verify sentiment analysis was performed
#     mock_datura.return_value.search_tweets.assert_called_once()
#     mock_chutes.return_value.analyze_sentiment.assert_called_once()
    
#     # Verify stake was added
#     mock_wallet.return_value.add_stake.assert_called_once()
    
#     # Verify response contains trading info
#     assert "sentiment_score" in data
#     assert "trading_action" in data
#     assert data["trading_action"] == "stake_added"

# def test_trading_with_negative_sentiment(mock_redis, mock_substrate, mock_datura, mock_chutes, mock_wallet):
#     # Get access token
#     access_token = test_login()
#     headers = {"Authorization": f"Bearer {access_token}"}
    
#     # Mock negative sentiment
#     mock_chutes.return_value.analyze_sentiment.return_value = {"sentiment_score": -50}
    
#     # Test trading with negative sentiment
#     params = {
#         "netuid": TEST_NETUID,
#         "hotkey": TEST_HOTKEY,
#         "trade": True
#     }
    
#     response = client.get("/api/v1/tao-dividends", params=params, headers=headers)
#     assert response.status_code == 200
#     data = response.json()
    
#     # Verify unstake was called
#     mock_wallet.return_value.unstake.assert_called_once()
    
#     # Verify response contains trading info
#     assert "sentiment_score" in data
#     assert "trading_action" in data
#     assert data["trading_action"] == "stake_removed"

# def test_trading_without_trade_param(mock_redis, mock_substrate):
#     # Get access token
#     access_token = test_login()
#     headers = {"Authorization": f"Bearer {access_token}"}
    
#     # Test without trade parameter
#     params = {
#         "netuid": TEST_NETUID,
#         "hotkey": TEST_HOTKEY,
#         "trade": True
#     }
    
#     response = client.get("/api/v1/tao-dividends", params=params, headers=headers)
#     assert response.status_code == 200
#     data = response.json()
    
#     # Verify no trading actions were taken
#     assert "sentiment_score" in data
#     assert "trading_action" in data

# def test_trading_with_invalid_credentials():
#     invalid_headers = {"Authorization": "Bearer invalid_token"}
#     params = {
#         "netuid": TEST_NETUID,
#         "hotkey": TEST_HOTKEY,
#         "trade": True
#     }
#     response = client.get("/api/v1/tao-dividends", params=params, headers=invalid_headers)
#     assert response.status_code == 401 