from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import quote, unquote
import re
import aiohttp
import os
from dotenv import load_dotenv
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ========== APP SETUP ==========
app = FastAPI(title="Shopee Affiliate Link Generator", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
AFFILIATE_ID = "17323090153"
SUB_ID = "addlivetag-ductoan"
SHARE_CHANNEL = "4"

# ========== HELPER FUNCTIONS ==========

def is_shopee_url(url: str) -> bool:
    """Check if URL is from Shopee"""
    return bool(re.search(r'shopee\.(vn|ph|sg|my|tw|id|th)', url) or 's.shopee' in url)


def is_short_link(url: str) -> bool:
    """Check if URL is short link"""
    return 's.shopee' in url and 'an_redir' not in url


async def decode_short_link(short_url: str) -> str:
    """
    Decode short link to get origin link
    VD: https://s.shopee.vn/3B2qsVvyNN -> https://shopee.vn/product/123/456
    """
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
                logger.info(f"✅ Decoded to: {final_url}")
                return final_url
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"❌ Decode error: {e}")
        return None


def create_affiliate_link(origin_url: str) -> str:
    """Create affiliate link from origin URL"""
    encoded = quote(origin_url, safe='')
    return (
        f"https://s.shopee.vn/an_redir?"
        f"origin_link={encoded}"
        f"&affiliate_id={AFFILIATE_ID}"
        f"&sub_id={SUB_ID}"
        f"&share_channel_code={SHARE_CHANNEL}"
    )


# ========== API ENDPOINTS ==========

@app.post("/create-link")
async def create_link(origin_link: str = Query(...)):
    """
    Main endpoint - tạo affiliate link
    
    Flow:
    1. Kiểm tra URL có phải Shopee không
    2. Nếu là short link -> giải mã
    3. Tạo affiliate link mới
    """
    
    try:
        # Validate input
        if not origin_link or not origin_link.strip():
            raise HTTPException(status_code=400, detail="Link không được để trống")
        
        origin_link = origin_link.strip()
        logger.info(f"📥 Input: {origin_link}")
        
        # Check if Shopee URL
        if not is_shopee_url(origin_link):
            raise HTTPException(status_code=400, detail="Link phải từ Shopee")
        
        # Variables
        decoded_from_short = False
        final_origin_link = origin_link
        
        # ========== If short link, decode it ==========
        if is_short_link(origin_link):
            logger.info("🔄 Detected short link, decoding...")
            decoded_from_short = True
            
            decoded = await decode_short_link(origin_link)
            
            if not decoded:
                raise HTTPException(status_code=400, detail="Không thể giải mã short link")
            
            final_origin_link = decoded
        
        # ========== Create affiliate link ==========
        logger.info(f"🔗 Creating affiliate link...")
        affiliate_link = create_affiliate_link(final_origin_link)
        
        logger.info(f"✅ Success!")
        
        return {
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Shopee Affiliate API v1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
