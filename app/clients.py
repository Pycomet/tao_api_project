from pathlib import Path
from typing import List, Dict, Any
import bittensor as bt
from app.config import *
# from bittensor_wallet import Wallet # type: ignore
from bittensor import wallet as Wallet
# from bittensor import AsyncSubtensor
import os
import logging
import aiohttp
import json
import subprocess
from bittensor.utils.balance import Balance
from bittensor.utils.balance import tao
from bittensor.core.async_subtensor import add_stake_extrinsic, unstake_extrinsic
# from bittensor.core.subtensor import get_balance
# from bittensor.utils

SENTIMENT_PROMPT = """Analyze the sentiment expressed in the following tweets and provide a single sentiment score ranging from -100 (very negative) to +100 (very positive), representing the overall sentiment of the provided tweets. Consider the nuances in language, opinions, and emotions expressed in the text.

**Tweets:**
{tweets}

Just retiunr the overall sentiment score without any explanatory text
"""

logger = logging.getLogger(__name__)

class DaturaClient:
    def __init__(self):
        self.client = Datura(api_key=DATURA_API_KEY)

    async def search_tweets(self, netuid: str) -> dict[str, any]:
        """Search for tweets using Datura API."""
        try:
            response = self.client.basic_twitter_search(
                query=f"Bittensor netuid {netuid}",
                sort="Top",
                lang="en",
                count=5
            )
            return response
        except Exception as e:
            logger.error(f"Error searching tweets: {str(e)}")
            raise

    async def close(self):
        await self.client.aclose()


class LLMClient:
    def __init__(self, model: Optional[str] = None):
        self.api_key = CHUTES_API_KEY
        self.model_name = model or "unsloth/Llama-3.2-3B-Instruct"
        self.temperature = 0.7

    async def query_chute_llm(self, tweets: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = SENTIMENT_PROMPT.format(
            tweets=tweets
        )

        body = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "max_tokens": 1024,
            "temperature": self.temperature
        }


        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://llm.chutes.ai/v1/chat/completions",
                headers=headers,
                json=body
            ) as response:
                if response.status != 200:
                    error_msg = await response.text()
                    raise Exception(f"Failed to call Chutes API ({response.status}): {error_msg}")
                
                data = await response.json()
                return data["choices"][0]["message"]["content"]


class BittensorWallet:
    def __init__(self, wallet_path: Optional[str] = None):
        self.wallet_path = wallet_path or "~/.bittensor/wallets/"
        self.wallet_name = BITTENSOR_WALLET_NAME
        self.hotkey = BITTENSOR_WALLET_HOTKEY
        self.mnemonic = BITTENSOR_MNEMONIC
        
        # Faucet info
        self.faucet_mnemonic = "diamond like interest affair safe clarify lawsuit innocent beef van grief color"
        self.faucet_wallet_name = "faucet"
        self.faucet_hotkey = "default"
        self.max_faucet_transfer = 40.0

        
        # Create wallet directory if it doesn't exist
        Path(self.wallet_path).mkdir(parents=True, exist_ok=True)
        
        # Initialize wallet and subtensor
        self.wallet = self._initialize_wallet()
        self.subtensor = self._initialize_subtensor()
        
    def _initialize_wallet(self) -> Wallet:
        """Initialize or create wallet."""
        try:
            w = Wallet(
                name=self.wallet_name,
                hotkey=self.hotkey,
                path=self.wallet_path
            )
            
            w.regenerate_coldkey(
                mnemonic=self.mnemonic,
                use_password=False,
                overwrite=True,
                suppress=True,
            )

            w.regenerate_hotkey(
                mnemonic=self.mnemonic,
                use_password=False,
                overwrite=True,
                suppress=True,
            )

            # Try accessing keys to validate wallet
            try:
                _ = w.coldkeypub.ss58_address
                _ = w.hotkey.ss58_address
                logger.info(f"Using existing wallet: {self.wallet_name}")
            except Exception:
                # Keys are missing — create new wallet
                logger.info(f"Creating new wallet with name: {self.wallet_name}")
                w.create()
                self.hotkey = w.hotkey.ss58_address
                logger.info(f"Wallet created: coldkey={w.coldkeypub.ss58_address}, hotkey={w.hotkey.ss58_address}")

            return w

        except Exception as e:
            logger.error(f"Error initializing wallet: {str(e)}")
            raise
            
    def _initialize_subtensor(self) -> bt.subtensor:
        """Initialize subtensor connection."""
        try:
            # Initialize subtensor with testnet
            subtensor = bt.subtensor(network="test")
            logger.info("Connected to Bittensor testnet")
            return subtensor
        except Exception as e:
            logger.error(f"Error connecting to subtensor: {str(e)}")
            raise

    async def _fund_if_needed(self):
        """Fund the wallet from the faucet if balance is low."""
        
        try:
            current_balance = await self.get_tao_balance()
            if current_balance is not None and current_balance < 1.0:
                logger.info(f"Wallet balance is low ({current_balance} TAO). Attempting to fund from faucet...")

                faucet_wallet = Wallet(
                    name=self.faucet_wallet_name,
                    hotkey=self.faucet_hotkey,
                    path=self.wallet_path
                )

                faucet_wallet.regenerate_coldkey(self.faucet_mnemonic, use_password=False, overwrite=True, suppress=True)
                faucet_wallet.regenerate_hotkey(self.faucet_mnemonic, use_password=False, overwrite=True, suppress=True)

                faucet_balance = self.subtensor.get_balance(faucet_wallet.coldkeypub.ss58_address)
                if faucet_balance.tao < self.max_faucet_transfer:
                    logger.warning("Faucet wallet has insufficient funds.")
                    return

                result = self.subtensor.transfer(
                    wallet=faucet_wallet,
                    dest=self.wallet.coldkeypub.ss58_address,
                    amount=self.max_faucet_transfer,
                    wait_for_inclusion=True
                )

                logger.info(f"Funded wallet with {self.max_faucet_transfer} TAO: {result}")
            else:
                logger.info(f"Wallet already has sufficient balance: {current_balance} TAO")

        except Exception as e:
            logger.error(f"Error funding wallet: {str(e)}")


    def get_wallet_info(self) -> dict:
        """Get current balance of wallet."""
        try:
            balance = asyncio.run(self.get_tao_balance())
            return {
                "wallet_name": self.wallet_name,
                "hotkey": self.hotkey,
                "tao_balance": balance or 0.0
            }
        except Exception as e:
            logger.error(f"Error getting wallet info: {str(e)}")
            return {
                "wallet_name": self.wallet_name,
                "hotkey": self.hotkey,
                "tao_balance": 0.0
            }
        
    async def add_stake(self, netuid: int, hotkey: str, amount: float) -> Dict[str, Any]:
        """Add stake to a hotkey."""
        amount_balance = Balance.from_tao(amount).set_unit(netuid)
        
        await self._fund_if_needed()

        logger.info(f"Amount converted to Balance: {amount_balance.tao}")
        try:
            result = await self.subtensor.add_stake(
                wallet=self.wallet,
                netuid=netuid,
                hotkey_ss58=hotkey,
                amount=amount_balance.tao,
                allow_partial_stake=True,
                safe_staking=True
            )
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error adding stake: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def unstake(self, netuid: int, hotkey: str, amount: float) -> Dict[str, Any]:
        """Remove stake from a hotkey."""
        amount_balance = Balance.from_tao(amount).set_unit(netuid)

        logger.info(f"Amount converted to Balance: {amount_balance}")
        try:
            result = await self.subtensor.unstake(
                wallet=self.wallet,
                netuid=netuid,
                hotkey_ss58=hotkey,
                amount=amount_balance.tao,
                allow_partial_stake=True,
                safe_staking=True
            )
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error unstaking: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def get_tao_balance(self) -> Optional[float]:
        """Get TAO balance from subtensor."""
        try:
            balance = self.subtensor.get_balance(self.wallet.coldkeypub.ss58_address)
            if balance is not None:
                return balance.tao
            else:
                logger.warning("No balance found.")
                return 0.0
        except Exception as e:
            logger.error(f"Error getting balance: {str(e)}")
            return None
