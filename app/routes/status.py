from app.config import *


@router.get("/tao-dividends/status")
async def get_update_status():
    """Get the current status of the dividends cache update"""
    try:
        status = redis_client.get(get_update_status_key())
        start_time = redis_client.get(get_update_start_time_key())
        progress = redis_client.get(get_update_progress_key())
        
        if not status:
            return {
                "status": "not_started",
                "start_time": None,
                "progress": None
            }
        
        status = status.decode()
        start_time = start_time.decode() if start_time else None
        progress = progress.decode() if progress else None
        
        return {
            "status": status,
            "start_time": start_time,
            "progress": progress
        }
    except Exception as e:
        logger.error(f"Error getting update status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tao-dividends/redis-info")
async def get_redis_info():
    """Get information about Redis keys and their types"""
    try:
        # Get all keys matching our patterns
        dividend_keys = redis_client.keys("tao_dividend:*")
        status_keys = redis_client.keys("tao_dividend:update_*")
        
        # Get key types and TTLs
        info = {
            "total_keys": len(dividend_keys) + len(status_keys),
            "keys_by_type": {},
            "status_keys": {},
            "dividend_keys_by_netuid": {}
        }
        
        # Process status keys
        for key in status_keys:
            key_str = key.decode('utf-8')
            key_type = redis_client.type(key).decode()
            ttl = redis_client.ttl(key)
            info["status_keys"][key_str] = {
                "type": key_type,
                "ttl": ttl if ttl > 0 else None
            }
        
        # Process dividend keys
        for key in dividend_keys:
            key_str = key.decode('utf-8')
            if key_str.startswith("tao_dividend:update_"):
                continue  # Skip status keys we already processed
                
            key_type = redis_client.type(key).decode()
            ttl = redis_client.ttl(key)
            
            # Extract netuid from key
            parts = key_str.split(':')
            if len(parts) >= 3 and parts[1].isdigit():
                netuid = int(parts[1])
                if netuid not in info["dividend_keys_by_netuid"]:
                    info["dividend_keys_by_netuid"][netuid] = {
                        "count": 0,
                        "ttl": ttl if ttl > 0 else None
                    }
                info["dividend_keys_by_netuid"][netuid]["count"] += 1
        
        # Count keys by type
        all_keys = dividend_keys + status_keys
        for key in all_keys:
            key_type = redis_client.type(key).decode()
            if key_type not in info["keys_by_type"]:
                info["keys_by_type"][key_type] = 0
            info["keys_by_type"][key_type] += 1
        
        return info
    except Exception as e:
        logger.error(f"Error getting Redis info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
