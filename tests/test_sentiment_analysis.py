import asyncio
import os
import logging
from typing import Optional

import aiohttp
from datura_py import Datura # type: ignore
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DATURA_API_KEY = os.getenv("DATURA_API_KEY")
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY")

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
            
        else:
            print("No tweets found")
            
    except Exception as e:
        print(f"Error in workflow: {str(e)}")
        raise 
    

async def main():
    """Run all live tests"""
    print("Starting live tests...")
    
    # Run individual client tests
    # await test_datura_client_live()
    # await test_llm_client_live()
    
    # Run complete workflow test
    await test_full_workflow()
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 