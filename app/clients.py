from typing import List, Dict, Any
import bittensor as bt
from app.config import *
# from bittensor.wallet import Wallet # type: ignore


SENTIMENT_PROMPT = """Analyze the sentiment expressed in the following tweets and provide a single sentiment score ranging from -100 (very negative) to +100 (very positive), representing the overall sentiment of the provided tweets. Consider the nuances in language, opinions, and emotions expressed in the text.

**Tweets:**
{tweets}

Just retiunr the overall sentiment score without any explanatory text
"""


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


# class BittensorWallet:
#     def __init__(self, mnemonic: str, network: str = "test"):
#         self.wallet = Wallet(mnemonic=mnemonic)
#         self.network = network
#         self.subtensor = bt.subtensor(network=network)

#     async def add_stake(self, hotkey: str, amount: float) -> Dict[str, Any]:
#         """Add stake to a hotkey."""
#         try:
#             result = await self.subtensor.add_stake(
#                 wallet=self.wallet,
#                 hotkey=hotkey,
#                 amount=amount
#             )
#             return {"success": True, "result": result}
#         except Exception as e:
#             logger.error(f"Error adding stake: {str(e)}")
#             return {"success": False, "error": str(e)}

#     async def unstake(self, hotkey: str, amount: float) -> Dict[str, Any]:
#         """Remove stake from a hotkey."""
#         try:
#             result = await self.subtensor.unstake(
#                 wallet=self.wallet,
#                 hotkey=hotkey,
#                 amount=amount
#             )
#             return {"success": True, "result": result}
#         except Exception as e:
#             logger.error(f"Error unstaking: {str(e)}")
#             return {"success": False, "error": str(e)}

#     async def get_balance(self) -> float:
#         """Get wallet balance."""
#         try:
#             return await self.subtensor.get_balance(self.wallet.coldkeypub.ss58_address)
#         except Exception as e:
#             logger.error(f"Error getting balance: {str(e)}")
#             raise 