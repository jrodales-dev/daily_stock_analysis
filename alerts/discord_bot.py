import httpx
import logging
from core.config import settings
import os

logger = logging.getLogger(__name__)

class DiscordBot:
    def __init__(self):
        self.webhook_url = settings.DISCORD_WEBHOOK_URL

    async def send_message(self, text: str) -> bool:
        if not self.webhook_url:
            logger.warning("Discord Webhook URL not configured. Skipping message.")
            return False
            
        payload = {"content": text}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.webhook_url, json=payload)
            if response.status_code not in (200, 204):
                logger.error(f"Discord API Error: {response.text}")
                return False
            return True

    async def send_document(self, file_path: str, message: str = "") -> bool:
        if not self.webhook_url:
            logger.warning("Discord Webhook URL not configured. Skipping document.")
            return False
            
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
            
        data = {"content": message}
        
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                response = await client.post(self.webhook_url, data=data, files=files)
                if response.status_code not in (200, 204):
                    logger.error(f"Discord API Error: {response.text}")
                    return False
                return True
