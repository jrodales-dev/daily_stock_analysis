import httpx
import logging
from core.config import settings
import os

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, text: str) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not configured. Skipping message.")
            return False
            
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                logger.error(f"Telegram API Error: {response.text}")
                return False
            return True

    async def send_document(self, file_path: str, caption: str = "") -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not configured. Skipping document.")
            return False
            
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
            
        url = f"{self.base_url}/sendDocument"
        data = {
            "chat_id": self.chat_id,
            "caption": caption
        }
        
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {"document": f}
                response = await client.post(url, data=data, files=files)
                if response.status_code != 200:
                    logger.error(f"Telegram API Error: {response.text}")
                    return False
                return True
