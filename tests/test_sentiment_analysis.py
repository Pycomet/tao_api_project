import asyncio
import os
import logging
from pathlib import Path
from typing import Optional
import bittensor as bt
from unittest.mock import MagicMock
from unittest.mock import patch
from typing import Dict, Any
import aiohttp
import json
import subprocess
from bittensor.utils.balance import Balance
from bittensor.core.async_subtensor import add_stake_extrinsic, unstake_extrinsic
from bittensor_wallet import Wallet # type: ignore
from datura_py import Datura # type: ignore
from dotenv import load_dotenv

from tasks.worker import execute_sentiment_trade

logger = logging.getLogger(__name__)

DATURA_API_KEY = os.getenv("DATURA_API_KEY")
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY")
BITTENSOR_WALLET_NAME = os.getenv("BITTENSOR_WALLET_NAME", "default")
BITTENSOR_WALLET_HOTKEY = os.getenv("BITTENSOR_WALLET_HOTKEY", "default")
BITTENSOR_MNEMONIC = os.getenv("BITTENSOR_MNEMONIC", None)

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

    async def query_chute_llm(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

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
        
        # Fund wallet if balance is too low
        self._fund_if_needed()
        
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

    def _fund_if_needed(self):
        """Fund the wallet from the faucet if balance is low."""
        try:
            current_balance = self.get_tao_balance()
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
                    wait_for_inclusion=True,
                    prompt=False
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
            balance = await self.subtensor.get_balance(self.wallet.coldkeypub.ss58_address)
            if balance is not None:
                return balance.tao
            else:
                logger.warning("No balance found.")
                return 0.0
        except Exception as e:
            logger.error(f"Error getting balance: {str(e)}")
            return None

# Load environment variables
load_dotenv()

async def test_datura_client_live():
    """Test DaturaClient with real API calls"""
    print("\n=== Testing DaturaClient with Real API ===")
    
    client = DaturaClient()
    
    # Test different search queries
    queries = [
        "Bittensor",
        "#TAO",
        "Bittensor network"
    ]
    
    for query in queries:
        print(f"\nSearching for: {query}")
        try:
            results = await client.search_tweets(query)
            if results:
                tweets = [result.get("text") for result in results if "text" in result.keys()]
                print(f"Found {len(tweets)} tweets")
                for tweet in tweets[:3]:  # Show first 3 tweets
                    print(f"- {tweet}...")
            else:
                print("No results found")
        except Exception as e:
            print(f"Error: {str(e)}")
        
        # Wait between requests to avoid rate limiting
        await asyncio.sleep(2)

async def test_llm_client_live():
    """Test LLMClient with real API calls"""
    print("\n=== Testing LLMClient with Real API ===")
    
    client = LLMClient()
    
    # Test different sentiment analysis cases
    texts = [
        "Bittensor is revolutionizing AI with its decentralized network!",
        "I'm concerned about the recent changes in the Bittensor network.",
        "The TAO token price has been stable recently."
    ]
    
    SENTIMENT_PROMPT = f"""Analyze the sentiment expressed in the following tweets and provide a single sentiment score ranging from -100 (very negative) to +100 (very positive), representing the overall sentiment of the provided tweets. Consider the nuances in language, opinions, and emotions expressed in the text.
    
    **Tweets:**
    {"".join(texts)}
    
    Just retiunr the overall sentiment score without any explanatory text
    """

    
    try:
        response = await client.query_chute_llm(SENTIMENT_PROMPT)
    except Exception as e:
        logging.error("Failed, error: %s", str(e))
        raise
    
    print(f"Response {type(response)} {response}")
    return response



async def test_full_workflow():
    """Test the complete workflow from tweet search to sentiment analysis"""
    print("\n=== Testing Complete Workflow ===")
    
    datura_client = DaturaClient()
    llm_client = LLMClient()
    
    try:
        # Search for tweets
        print("\nSearching for Bittensor tweets...")
        tweets_result = await datura_client.search_tweets("18")  # Using netuid 18
        
        if tweets_result:
            tweets = [result.get("text") for result in tweets_result if "text" in result.keys()]
            print(f"Found {len(tweets)} tweets")
            
            # Combine tweets for sentiment analysis
            combined_tweets = "\n- ".join(tweets)  # Use first 3 tweets
            
            # Create sentiment prompt
            SENTIMENT_PROMPT = f"""Analyze the sentiment expressed in the following tweets and provide a single sentiment score ranging from -100 (very negative) to +100 (very positive), representing the overall sentiment of the provided tweets. Consider the nuances in language, opinions, and emotions expressed in the text.
            
            **Tweets:**
            {combined_tweets}
            
            Just return the overall sentiment score without any explanatory text
            """
            
            # Analyze sentiment
            print("\nAnalyzing sentiment of tweets...")
            sentiment_result = await llm_client.query_chute_llm(SENTIMENT_PROMPT)
            print(f"Sentiment Analysis Result: {sentiment_result}")
            
            return sentiment_result
            
        else:
            print("No tweets found")
            return 0
            
    except Exception as e:
        print(f"Error in workflow: {str(e)}")
        raise 
    

async def test_sentiment_based_staking():
    """Test staking/unstaking TAO based on sentiment scores"""
    print("\n=== Testing Sentiment-Based Staking ===")
    wallet_client = BittensorWallet()
    wallet_info = wallet_client.get_wallet_info()
    
    sentiment_score = 40.0
    
    # Test different sentiment scenarios
    test_cases = [
        {"sentiment": sentiment_score, "expected_action": "stake", "expected_amount": sentiment_score * 0.01},  # Positive sentiment
        {"sentiment": -50, "expected_action": "unstake", "expected_amount": 0.50},  # Negative sentiment
        {"sentiment": 0, "expected_action": "no_action", "expected_amount": 0.0},  # Neutral sentiment
        {"sentiment": 100, "expected_action": "stake", "expected_amount": 1.0},  # Very positive
        {"sentiment": -100, "expected_action": "unstake", "expected_amount": 1.0},  # Very negative
    ]
    
    # Patch the wallet in the task
    for case in test_cases:
        print(f"\nTesting sentiment score: {sentiment_score}")
        try:
            
            # Create the task instance
            result = await execute_sentiment_trade(hotkey=wallet_info['hotkey'], sentiment_score=sentiment_score)

            # Validate if the action in result matches the expected action
            if result['action'] == case['expected_action']:
                print(f"✓ Test passed for sentiment {case['sentiment']}. Action matched: {result['action']}")
            else:
                print(f"✗ Test failed for sentiment {case['sentiment']}. Expected action: {case['expected_action']}, but got: {result['action']}")

            # Check if expected_amount is also correct
            if result.get('amount', 0) == case['expected_amount']:
                print(f"✓ Amount matched: {result['amount']}")
            else:
                print(f"✗ Amount mismatch. Expected: {case['expected_amount']}, but got: {result.get('amount', 0)}")
            
        except Exception as e:
            print(f"✗ Test failed for sentiment {sentiment_score}: {str(e)}")
            raise
