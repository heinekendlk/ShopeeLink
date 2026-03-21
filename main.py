from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from urllib.parse import quote, urlparse
import re
import aiohttp
import logging

# ========== LOGGING SETUP ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== APP SETUP ==========
app = FastAPI(
    title="Shopee Affiliate Link Generator",
    version="1.0.0",
    description="Convert Shopee links to affiliate links with automatic short link decoding"
)

# ========== CORS MIDDLEWARE ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# ========== CONSTANTS ==========
AFFILIATE_ID = "17323090153"
SUB_ID = "addlivetag-ductoan"
SHARE_CHANNEL = "4"

logger.info("=" * 80)
logger.info("🚀 Shopee Affiliate Link Generator API Started")
logger.info(f"📋 Affiliate ID: {AFFILIATE_ID}")
logger.info(f"📋 Sub ID: {SUB_ID}")
logger.info(f"📋 Share Channel: {SHARE_CHANNEL}")
logger.info("=" * 80)

# ========== HELPER FUNCTIONS ==========

def is_shopee_url(url: str) -> bool:
    """
    Check if URL is from Shopee
    
    Args:
        url: URL to check
    
    Returns:
        bool: True if URL is from Shopee, False otherwise
    """
    if not url:
        return False
    
    shopee_domains = [
        'shopee.vn', 'shopee.ph', 'shopee.sg', 'shopee.my',
        'shopee.tw', 'shopee.id', 'shopee.th', 's.shopee'
    ]
    
    return any(domain in url for domain in shopee_domains)


def is_short_link(url: str) -> bool:
    """
    Check if URL is a Shopee short link
    
    Args:
        url: URL to check
    
    Returns:
        bool: True if URL is short link, False otherwise
    """
    # Short link starts with s.shopee and doesn't contain an_redir parameter
    return 's.shopee' in url and 'an_redir' not in url


def clean_url(url: str) -> str:
    """
    Remove query parameters from URL to keep only the base path
    
    Examples:
        https://shopee.vn/product/123/456?sp_atk=xxx&xptid=yyy
        -> https://shopee.vn/product/123/456
    
    Args:
        url: URL to clean
    
    Returns:
        str: Cleaned URL without query parameters
    """
    try:
        parsed = urlparse(url)
        # Reconstruct URL with only scheme, netloc, and path
        # Remove query parameters and fragments
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        if url != clean:
            logger.info(f"🧹 Cleaned URL")
            logger.info(f"   Before: {url}")
            logger.info(f"   After:  {clean}")
        
        return clean
    
    except Exception as e:
        logger.warning(f"⚠️ Could not clean URL: {e}")
        logger.warning(f"   Returning original URL")
        return url


async def decode_short_link(short_url: str) -> str:
    """
    Decode Shopee short link by following redirects
    
    Flow:
        1. Send GET request to short link
        2. Follow redirects (allow_redirects=True)
        3. Get final URL after all redirects
        4. Clean the URL to remove query parameters
    
    Args:
        short_url: Shopee short link (e.g., https://s.shopee.vn/3B2qsVvyNN)
    
    Returns:
        str: Origin link if successful, None if error
    """
    try:
        logger.info(f"🔍 Decoding short link")
        logger.info(f"   Input: {short_url}")
        
        connector = aiohttp.TCPConnector(ssl=False)
        session = aiohttp.ClientSession(connector=connector)
        
        try:
            async with session.get(
                short_url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as response:
                final_url = str(response.url)
                logger.info(f"   Decoded (raw): {final_url}")
                
                # Clean the URL - remove query parameters
                cleaned_url = clean_url(final_url)
                
                logger.info(f"   ✅ Decoded (cleaned): {cleaned_url}")
                return cleaned_url
        
        finally:
            await session.close()
    
    except asyncio.TimeoutError:
        logger.error(f"❌ Timeout while decoding short link (>15s)")
        return None
    except Exception as e:
        logger.error(f"❌ Error decoding short link: {str(e)}")
        return None


def create_affiliate_link(origin_url: str) -> str:
    """
    Create Shopee affiliate link from origin URL
    
    Formula:
        https://s.shopee.vn/an_redir?
            origin_link=<encoded_origin_url>
            &affiliate_id=<your_id>
            &sub_id=<your_sub_id>
            &share_channel_code=<channel>
    
    Args:
        origin_url: Origin product URL
    
    Returns:
        str: Affiliate link ready to share
    """
    encoded = quote(origin_url, safe='')
    
    affiliate_link = (
        f"https://s.shopee.vn/an_redir?"
        f"origin_link={encoded}"
        f"&affiliate_id={AFFILIATE_ID}"
        f"&sub_id={SUB_ID}"
        f"&share_channel_code={SHARE_CHANNEL}"
    )
    
    logger.info(f"🔗 Created affiliate link")
    logger.info(f"   Origin: {origin_url}")
    logger.info(f"   Affiliate: {affiliate_link[:100]}...")
    
    return affiliate_link


# ========== API ENDPOINTS ==========

@app.get("/")
async def root():
    """
    Root endpoint - API information
    
    Returns:
        dict: API information and available endpoints
    """
    logger.info("📍 GET / - Root endpoint")
    
    return JSONResponse(
        status_code=200,
        content={
            "message": "Shopee Affiliate Link Generator API",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "GET /": "API information",
                "GET /health": "Health check",
                "POST /create-link": "Create affiliate link"
            },
            "docs": "/docs"
        }
    )


@app.get("/health")
async def health():
    """
    Health check endpoint
    
    Returns:
        dict: Service status information
    """
    logger.info("📍 GET /health - Health check")
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "version": "1.0.0",
            "service": "Shopee Affiliate Link Generator",
            "affiliateId": AFFILIATE_ID,
            "uptime": "running"
        }
    )


@app.post("/create-link")
async def create_link(origin_link: str = Query(..., description="Shopee URL or short link")):
    """
    Main endpoint - Create affiliate link from Shopee URL
    
    Process Flow:
        1. Validate input (not empty, is Shopee URL)
        2. Check if it's a short link
           - If YES: Decode it (follow redirects)
           - If NO: Use it directly
        3. Clean URL (remove query parameters)
        4. Create affiliate link
        5. Return response with all details
    
    Query Parameters:
        origin_link (str): Shopee URL or short link
    
    Returns:
        dict: Response with affiliate link and metadata
    
    Status Codes:
        200: Success - affiliate link created
        400: Client error - invalid input
        500: Server error - internal error
    """
    
    logger.info("=" * 80)
    logger.info("📍 POST /create-link - Create Affiliate Link")
    logger.info(f"📝 Input: {origin_link}")
    
    try:
        # ========== STEP 1: Validate Input ==========
        if not origin_link or not origin_link.strip():
            logger.warning("❌ Empty link received")
            return JSONResponse(
                status_code=400,
                content={"detail": "Link không được để trống"}
            )
        
        origin_link = origin_link.strip()
        logger.info(f"✅ Input validated - Length: {len(origin_link)} chars")
        
        # ========== STEP 2: Check Shopee URL ==========
        if not is_shopee_url(origin_link):
            logger.warning(f"❌ Not a Shopee URL")
            return JSONResponse(
                status_code=400,
                content={"detail": "Link phải từ Shopee (shopee.vn, shopee.ph, etc.)"}
            )
        
        logger.info(f"✅ Valid Shopee URL detected")
        
        # ========== STEP 3: Initialize Variables ==========
        decoded_from_short = False
        final_origin_link = origin_link
        input_link = origin_link
        
        # ========== STEP 4: Check and Decode Short Link ==========
        if is_short_link(origin_link):
            logger.info(f"🔄 Short link detected - Starting decode process...")
            decoded_from_short = True
            
            decoded = await decode_short_link(origin_link)
            
            if not decoded:
                logger.error(f"❌ Failed to decode short link")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Không thể giải mã short link - vui lòng thử lại"}
                )
            
            # Validate decoded URL
            if not is_shopee_url(decoded):
                logger.error(f"❌ Decoded URL is not a valid Shopee URL")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Link giải mã không hợp lệ"}
                )
            
            final_origin_link = decoded
            logger.info(f"✅ Short link decoded successfully")
        
        else:
            logger.info(f"📌 Regular link detected - Cleaning query parameters...")
            final_origin_link = clean_url(origin_link)
        
        # ========== STEP 5: Create Affiliate Link ==========
        logger.info(f"🔗 Creating affiliate link from: {final_origin_link}")
        affiliate_link = create_affiliate_link(final_origin_link)
        logger.info(f"✅ Affiliate link created successfully")
        
        # ========== STEP 6: Prepare Response ==========
        response_data = {
            "success": True,
            "message": "Tạo link thành công" + (
                " (giải mã từ short link)" if decoded_from_short else ""
            ),
            "affiliateLink": affiliate_link,
            "originLink": final_origin_link,
            "inputLink": input_link,
            "decodedFromShort": decoded_from_short,
            "affiliateId": AFFILIATE_ID,
            "subId": SUB_ID,
            "shareChannelCode": SHARE_CHANNEL
        }
        
        logger.info(f"=" * 80)
        logger.info(f"✅ SUCCESS - Affiliate link created")
        logger.info(f"=" * 80)
        
        return JSONResponse(
            status_code=200,
            content=response_data,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
    
    except Exception as e:
        logger.error(f"=" * 80)
        logger.error(f"❌ UNEXPECTED ERROR: {str(e)}")
        logger.error(f"=" * 80)
        
        return JSONResponse(
            status_code=500,
            content={"detail": f"Lỗi server: {str(e)}"}
        )


# ========== CORS Preflight Handler ==========
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """
    Handle CORS preflight requests
    
    CORS preflight is sent by browsers before actual requests
    to check if the server allows cross-origin requests.
    
    Args:
        full_path: The requested path
    
    Returns:
        dict: OK response with CORS headers
    """
    logger.info(f"📍 OPTIONS /{full_path} - CORS preflight")
    
    return JSONResponse(
        status_code=200,
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


# ========== Startup Event ==========
@app.on_event("startup")
async def startup_event():
    """Called when app starts"""
    logger.info("\n")
    logger.info("🎉 API is ready to receive requests!")
    logger.info("📝 Documentation: /docs")
    logger.info("\n")


# ========== Main ==========
if __name__ == "__main__":
    import asyncio
    import uvicorn
    
    # Import asyncio for Windows compatibility
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    logger.info("\n🚀 Starting Uvicorn server...\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
