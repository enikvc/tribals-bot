"""
Download external scripts (farmgod.js and massScavenge.js)
"""
import os
import aiohttp
import aiofiles
from pathlib import Path

from ..utils.logger import setup_logger

logger = setup_logger(__name__)

SCRIPTS = {
    'farmgod.js': 'https://cdn.jsdelivr.net/gh/enikvc/tribals_it_scripts@refs/tags/1.2/farmgod.js',
    'massScavenge.js': 'https://shinko-to-kuma.com/scripts/massScavenge.js'
}


async def download_external_scripts():
    """Download required external scripts"""
    vendor_dir = Path('vendor')
    vendor_dir.mkdir(exist_ok=True)
    
    for filename, url in SCRIPTS.items():
        file_path = vendor_dir / filename
        
        if file_path.exists():
            logger.info(f"✅ {filename} already exists")
            continue
            
        logger.info(f"📥 Downloading {filename}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                            await f.write(content)
                            
                        logger.info(f"✅ Downloaded {filename} ({len(content)} bytes)")
                    else:
                        logger.error(f"❌ Failed to download {filename}: HTTP {response.status}")
                        
        except Exception as e:
            logger.error(f"❌ Error downloading {filename}: {e}", exc_info=True)