import os
import pytest
import asyncio
from pathlib import Path
from app.clients import BittensorWallet

# Test configuration
TEST_MNEMONIC = "diamond like interest affair safe clarify lawsuit innocent beef van grief color"
TEST_COLDKEY_ADDRESS = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
TEST_HOTKEY_ADDRESS = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"
TEST_BALANCE = 100.0
TEST_DIVIDENDS = 10.0
TEST_TRANSFER_AMOUNT = 0.1

@pytest.fixture(scope="function")
def bittensor_wallet(mock_bittensor_wallet, mock_async_subtensor):
    """Create a test Bittensor wallet."""
    return BittensorWallet(TEST_MNEMONIC)

@pytest.mark.asyncio
async def test_bittensor_wallet_operations(bittensor_wallet):
    """Test Bittensor wallet operations."""
    # Test getting wallet info
    info = bittensor_wallet.get_wallet_info()
    assert info is not None
    assert isinstance(info["tao_balance"], float), f"Expected float, got {type(info['tao_balance'])}"
    
    # Test getting balance
    balance = await bittensor_wallet.get_tao_balance()
    assert isinstance(balance, float), f"Expected float, got {type(balance)}"
    
    # Test funding the wallet
    await bittensor_wallet._fund_if_needed()
    
    # Test getting balance
    balance = await bittensor_wallet.get_tao_balance()
    assert isinstance(balance, float), f"Expected float, got {type(balance)}"
    assert balance >= 40.0