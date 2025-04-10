from app.config import *
from app.utils import fetch_tao_dividends

@router.get("/tao-dividends/all")
async def tao_dividends(current_user: dict = Depends(get_current_user)):
    """
    Endpoint to fetch Tao Dividends per Subnet with caching.
    """
    try:
        # Get cached block hash
        block_hash = redis_client.get(get_block_hash_cache_key())
        if not block_hash:
            logger.info("No cached block hash found, fetching fresh data")
            # If no cache, fetch fresh data
            results, block_hash = await fetch_tao_dividends()
            
            # Cache the fetched data
            try:
                for netuid, hotkey, value in results:
                    cache_key = get_dividend_cache_key(netuid, hotkey)
                    redis_client.set(cache_key, json.dumps(value), ex=CACHE_TTL)
                    logger.info(f"Cached: netuid={netuid}, hotkey={hotkey}")
                
                # Cache the block hash
                redis_client.set(get_block_hash_cache_key(), block_hash, ex=CACHE_TTL)
                logger.info(f"Cached block hash: {block_hash}")
            except Exception as e:
                logger.error(f"Error caching data: {e}")
            
            return {
                "data": results,
                "block_hash": block_hash,
                "cached": False
            }
        
        # Get cached data
        results = []
        for netuid in range(1, 51):
            try:
                pattern = f"tao_dividend:{netuid}:*"
                keys = redis_client.keys(pattern)
                for key in keys:
                    try:
                        key_str = key.decode('utf-8')
                        hotkey = key_str.split(':')[-1]
                        netuid = key_str.split(':')[-2]
                        value = redis_client.get(key)
                        if value:
                            results.append((netuid, hotkey))
                    except Exception as e:
                        logger.error(f"Error processing cache key {key}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error processing netuid {netuid}: {e}")
                continue
        
        logger.info(f"Returning {len(results)} cached dividend records")
        return {
            "data": results,
            "block_hash": block_hash.decode('utf-8'),
            "cached": True
        }
    except Exception as e:
        logger.error(f"Error in tao_dividends endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/tao-dividends")
async def get_dividend(
    netuid: int = Query(None, description="The netuid of the subnet"),
    hotkey: str = Query(None, description="The hotkey of the account"),
    trade: bool = Query(False, description="Flag to indicate if trade is enabled"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get dividend for specific netuid and hotkey.
    """
    results = {}

    
    try:
        # Condtion 1: Both Netuid & Hotkey are provided
        if netuid is not None and hotkey is not None:
            cache_key = get_dividend_cache_key(netuid, hotkey)
            cached_value = redis_client.get(cache_key)
            
            if cached_value:
                logger.info(f"Cache hit for {netuid}/{hotkey}")
                results =  {
                    "netuid": netuid,
                    "hotkey": hotkey,
                    "dividend": json.loads(cached_value),
                    "cached": True
                    "stake_tx_triggered": False
                }
            
            logger.info(f"Cache miss for {netuid}/{hotkey}, fetching from chain")

            
        # Condition 2: Netuid is provided but Hotkey is not
        elif netuid is not None and hotkey is None:
            
            # Check Valid SubnetID
            if netuid not in range(1, 51):
                raise HTTPException(status_code=400, detail=f"Invalid netuid provided: {netuid}")
            
            cache_key = f"tao_dividend:{netuid}:*"
            cached_values = redis_client.keys(cache_key)
            
            if cached_values and len(cached_values) > 0:
                logger.info(f"Cache hit for netuid - {len(cached_values)} items")
                data = []
                
                for key in cached_values:
                    key_str = key.decode('utf-8')
                    hotkey = key_str.split(':')[-1]
                    netuid = key_str.split(':')[-2]
                    value = redis_client.get(key)
                    if value:
                        data.append({
                            "netuid": netuid,
                            "hotkey": hotkey,
                            "dividend": json.loads(value)
                        })
                        
                results = {
                    "data": data,
                    "cached": True,
                    "stake_tx_triggered": False
                }
            else:
                logger.info(f"Cache miss for netuid - {netuid}")
                netuid = 18
                                        
                
        # Condition 3: Hotkey is provided but Netuid is not
        elif netuid is None and hotkey is not None:
            
            cache_key = f"tao_dividend:*:{str(hotkey)}"
            cached_values = redis_client.keys(cache_key)
            
            if cached_values and len(cached_values) > 0:
                logger.info(f"Cache hit for hotkey - {len(cached_values)} items")
                data = []
                
                for key in cached_values:
                    key_str = key.decode('utf-8')
                    hotkey = key_str.split(':')[-1]
                    netuid = key_str.split(':')[-2]
                    value = redis_client.get(key)
                    if value:
                        data.append({
                            "netuid": netuid,
                            "hotkey": str(hotkey),
                            "dividend": json.loads(value)
                        })
                        
                results = {
                    "data": data,
                    "cached": True,
                    "stake_tx_triggered": False
                }
            else:
                logger.info(f"Cache miss for hotkey - {hotkey}")
                hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"
                

        else:
            # Set default values
            netuid = 18
            hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"

        if len(results.keys()) == 0:
            # If not in cache, fetch from chain
            cache_key = get_dividend_cache_key(netuid, hotkey)
            
            try:
                async with AsyncSubstrateInterface("wss://entrypoint-finney.opentensor.ai:443",
                                            ss58_format=SS58_FORMAT) as substrate:
                    block_hash = await substrate.get_chain_head()
                    result = await substrate.query(
                        "SubtensorModule",
                        "TaoDividendsPerSubnet",
                        [netuid, hotkey],
                        block_hash=block_hash
                    )
                    
                    if result and result.value:
                        # Cache the result
                        redis_client.set(cache_key, json.dumps(result.value), ex=CACHE_TTL)
                        logger.info(f"Cached new value for {netuid}/{hotkey}")
                        return {
                            "netuid": netuid,
                            "hotkey": hotkey,
                            "dividend": result.value,
                            "cached": False,
                            "stake_tx_triggered": False
                        }
                    
                    logger.warning(f"No dividend found for {netuid}/{hotkey}")
                    raise HTTPException(status_code=404, detail="Dividend not found")
            except Exception as e:
                logger.error(f"Error querying substrate for {netuid}/{hotkey}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to query substrate: {str(e)}")
                
        return results
                
        
    except Exception as e:
        logger.error(f"Error in get_dividend endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))