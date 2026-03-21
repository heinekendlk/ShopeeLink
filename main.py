from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from urllib.parse import quote, unquote
import re
import aiohttp
import os
from dotenv import load_dotenv
import asyncio
import logging

# ========== Setup Logging ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ========== FastAPI App ==========
app = FastAPI(
    title="Shopee Affiliate Link Generator",
    version="1.0.5",
    description="Convert Shopee links to affiliate links"
)

# ========== CORS - Very Permissive ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# ========== Constants ==========
FIXED_AFFILIATE_ID = "17323090153"
FIXED_SUB_ID = "addlivetag-ductoan"
FIXED_SHARE_CHANNEL_CODE = "4"

logger.info(f"Starting app with affiliate_id: {FIXED_AFFILIATE_ID}")

# ========== Health Check Startup ==========
@app.on_event("startup")
async def startup_event():
    """Chạy khi app start"""
    logger.info("✅ App started successfully")
    logger.info(f"Available endpoints: /config, /create-link, /health")

# ========== CONFIG ENDPOINT ==========
@app.get("/config")
async def get_config():
    """
    GET /config - Trả về config cho frontend
    
    Response:
    {
        "apiUrl": "...",
        "version": "1.0.5",
        "features": ["decode_short_link", "create_affiliate_link"],
        "status": "ok"
    }
    """
    try:
        api_url = os.getenv("API_URL", "https://shopee-affiliate-api-ymtu.onrender.com")
        
        config = {
            "apiUrl": api_url,
            "version": "1.0.5",
            "features": ["decode_short_link", "create_affiliate_link"],
            "status": "ok"
        }
        
        logger.info(f"Config endpoint called - returning API_URL: {api_url}")
        
        return config
        
    except Exception as e:
        logger.error(f"Config endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Config error: {str(e)}"
        )


# ========== HELPER FUNCTIONS ==========

def validate_shopee_url(url: str) -> bool:
    """Validate Shopee URL"""
    shopee_patterns = [
        r'shopee\.vn', r'shopee\.ph', r'shopee\.sg', 
        r'shopee\.my', r'shopee\.com\.my', r'shopee\.co\.th',
        r'shopee\.tw', r'shopee\.id', r's\.shopee'
    ]
    pattern = '|'.join(shopee_patterns)
    return bool(re.search(pattern, url))


def is_short_link(url: str) -> bool:
    """Check if URL is short link"""
    return 's.shopee' in url and 'an_redir' not in url


async def extract_origin_link_from_short(url: str) -> str:
    """
    Decode short link to get origin link
    """
    try:
        logger.info(f"Decoding short link: {url}")
        
        # ========== Method 1: Extract from an_redir parameter ==========
        if 'an_redir' in url and 'origin_link=' in url:
            logger.info("Method 1: Found an_redir parameter")
            match = re.search(r'origin_link=([^&]+)', url)
            if match:
                origin_link = unquote(match.group(1))
                logger.info(f"Extracted: {origin_link}")
                return origin_link
        
        # ========== Method 2: Follow redirect ==========
        logger.info("Method 2: Following redirect...")
        
        connector = aiohttp.TCPConnector(ssl=False)
        session = aiohttp.ClientSession(connector=connector)
        
        try:
            async with session.get(
                url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                }
            ) as response:
                final_url = str(response.url)
                logger.info(f"Final URL after redirect: {final_url}")
                
                # Check if has origin_link parameter
                if 'origin_link=' in final_url:
                    logger.info("Found origin_link parameter")
                    match = re.search(r'origin_link=([^&]+)', final_url)
                    if match:
                        origin_link = unquote(match.group(1))
                        logger.info(f"Extracted: {origin_link}")
                        return origin_link
                
                # Check if final URL is valid Shopee URL
                if validate_shopee_url(final_url):
                    logger.info(f"Final URL is valid: {final_url}")
                    return final_url
                
                logger.warning("Could not decode short link")
                return None
                
        finally:
            await session.close()
        
    except asyncio.TimeoutError:
        logger.error("Timeout while decoding short link")
        return None
    except Exception as e:
        logger.error(f"Error decoding short link: {e}", exc_info=True)
        return None


def create_affiliate_link(origin_link: str) -> str:
    """Create affiliate link"""
    encoded_link = quote(origin_link, safe='')
    affiliate_link = (
        f"https://s.shopee.vn/an_redir?"
        f"origin_link={encoded_link}"
        f"&affiliate_id={FIXED_AFFILIATE_ID}"
        f"&sub_id={FIXED_SUB_ID}"
        f"&share_channel_code={FIXED_SHARE_CHANNEL_CODE}"
    )
    return affiliate_link


# ========== CREATE LINK ENDPOINT ==========
@app.post("/create-link")
async def create_link(origin_link: str = Query(...)):
    """
    POST /create-link - Tạo affiliate link
    
    Query Parameters:
    - origin_link: Shopee URL (short link hoặc link thường)
    
    Response:
    {
        "success": true,
        "affiliateLink": "...",
        "originLink": "...",
        "decodedFromShortLink": true/false,
        ...
    }
    """
    
    try:
        # Validation
        if not origin_link:
            logger.warning("origin_link is empty")
            raise HTTPException(
                status_code=400,
                detail="origin_link không được để trống"
            )
        
        origin_link = origin_link.strip()
        logger.info(f"Creating link for: {origin_link}")
        
        if not validate_shopee_url(origin_link):
            logger.warning(f"Invalid Shopee URL: {origin_link}")
            raise HTTPException(
                status_code=400,
                detail="URL không phải từ Shopee"
            )
        
        decoded_from_short_link = False
        original_input = origin_link
        
        # ========== If short link, decode it ==========
        if is_short_link(origin_link):
            logger.info("Detected short link, decoding...")
            decoded_from_short_link = True
            
            decoded_link = await extract_origin_link_from_short(origin_link)
            
            if not decoded_link:
                logger.error("Failed to decode short link")
                raise HTTPException(
                    status_code=400,
                    detail="Không thể giải mã short link"
                )
            
            origin_link = decoded_link
            logger.info(f"Decoded to: {origin_link}")
        
        # ========== Validate origin link ==========
        if not validate_shopee_url(origin_link):
            logger.warning(f"Invalid origin link: {origin_link}")
            raise HTTPException(
                status_code=400,
                detail="Link gốc không hợp lệ"
            )
        
        # ========== Create affiliate link ==========
        affiliate_link = create_affiliate_link(origin_link)
        logger.info(f"Created affiliate link successfully")
        
        response = {
            "success": True,
            "message": "✅ Đã tạo link thành công" + (
                " (giải mã từ short link)" if decoded_from_short_link else ""
            ),
            "affiliateLink": affiliate_link,
            "originLink": origin_link,
            "originalInput": original_input,
            "decodedFromShortLink": decoded_from_short_link,
            "affiliateId": FIXED_AFFILIATE_ID,
            "subId": FIXED_SUB_ID,
            "shareChannelCode": FIXED_SHARE_CHANNEL_CODE
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating link: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi: {str(e)}"
        )


# ========== HEALTH CHECK ENDPOINT ==========
@app.get("/health")
async def health_check():
    """GET /health - Health check"""
    return {
        "status": "ok",
        "service": "Shopee Affiliate Link Generator",
        "version": "1.0.5",
        "affiliateId": FIXED_AFFILIATE_ID,
        "subId": FIXED_SUB_ID,
        "shareChannelCode": FIXED_SHARE_CHANNEL_CODE
    }


# ========== ROOT ENDPOINT ==========
@app.get("/")
async def root():
    """GET / - Root endpoint"""
    return {
        "message": "Shopee Affiliate Link Generator API",
        "version": "1.0.5",
        "status": "running",
        "endpoints": {
            "GET /config": "Lấy config",
            "POST /create-link": "Tạo affiliate link",
            "GET /health": "Health check"
        }
    }


# ========== OPTIONS for CORS ==========
@app.options("/{path_name:path}")
async def options_handler(path_name: str):
    """Handle CORS preflight requests"""
    return {"message": "OK"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
