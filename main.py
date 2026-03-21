from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from urllib.parse import quote
import re
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== APP ==========
app = FastAPI(title="Shopee Affiliate API", version="1.0.0")

# ========== CORS ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ========== Constants ==========
AFFILIATE_ID = "17323090153"
SUB_ID = "addlivetag-ductoan"
SHARE_CHANNEL = "4"

logger.info("✅ Shopee Affiliate API Started")

# ========== HELPER FUNCTIONS ==========

def is_shopee_url(url: str) -> bool:
    """Check if URL is from Shopee"""
    patterns = ['shopee.vn', 'shopee.ph', 'shopee.sg', 'shopee.my', 
                'shopee.tw', 'shopee.id', 'shopee.th', 's.shopee']
    return any(pattern in url for pattern in patterns)


def is_short_link(url: str) -> bool:
    """Check if URL is short link"""
    return 's.shopee' in url and 'an_redir' not in url


async def decode_short_link(short_url: str) -> str:
    """Decode short link"""
    try:
        logger.info(f"🔍 Decoding: {short_url}")
        
        connector = aiohttp.TCPConnector(ssl=False)
        session = aiohttp.ClientSession(connector=connector)
        
        try:
            async with session.get(
                short_url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={'User-Agent': 'Mozilla/5.0'}
            ) as response:
                final_url = str(response.url)
                logger.info(f"✅ Decoded: {final_url}")
                return final_url
        finally:
            await session.close()
    except Exception as e:
        logger.error(f"❌ Decode error: {e}")
        return None


def create_affiliate_link(origin_url: str) -> str:
    """Create affiliate link"""
    encoded = quote(origin_url, safe='')
    return (
        f"https://s.shopee.vn/an_redir?"
        f"origin_link={encoded}"
        f"&affiliate_id={AFFILIATE_ID}"
        f"&sub_id={SUB_ID}"
        f"&share_channel_code={SHARE_CHANNEL}"
    )


# ========== ROUTES ==========

@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("GET /")
    return {
        "message": "Shopee Affiliate API v1.0.0",
        "status": "running",
        "endpoints": ["/health", "/create-link"]
    }


@app.get("/health")
async def health():
    """Health check"""
    logger.info("GET /health")
    return {"status": "ok", "version": "1.0.0"}


@app.post("/create-link")
async def create_link(origin_link: str = Query(...)):
    """Create affiliate link"""
    
    logger.info(f"POST /create-link - Input: {origin_link}")
    
    try:
        # Validate
        if not origin_link or not origin_link.strip():
            return JSONResponse(
                status_code=400,
                content={"detail": "Link không được để trống"}
            )
        
        origin_link = origin_link.strip()
        
        # Check Shopee
        if not is_shopee_url(origin_link):
            return JSONResponse(
                status_code=400,
                content={"detail": "Link phải từ Shopee"}
            )
        
        decoded_from_short = False
        final_origin_link = origin_link
        
        # Decode if short link
        if is_short_link(origin_link):
            decoded_from_short = True
            decoded = await decode_short_link(origin_link)
            
            if not decoded:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Không thể giải mã short link"}
                )
            
            final_origin_link = decoded
        
        # Create affiliate link
        affiliate_link = create_affiliate_link(final_origin_link)
        
        logger.info(f"✅ Success - Created affiliate link")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Tạo link thành công" + (" (giải mã từ short link)" if decoded_from_short else ""),
                "affiliateLink": affiliate_link,
                "originLink": final_origin_link,
                "inputLink": origin_link,
                "decodedFromShort": decoded_from_short,
                "affiliateId": AFFILIATE_ID,
                "subId": SUB_ID,
                "shareChannelCode": SHARE_CHANNEL
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Lỗi: {str(e)}"}
        )


# ========== CORS Preflight ==========
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle CORS preflight"""
    logger.info(f"OPTIONS /{full_path}")
    return JSONResponse(
        status_code=200,
        content={"message": "OK"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
