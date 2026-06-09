from pydantic import BaseModel
from typing import Optional

class ReportRequest(BaseModel):
    ticker: str
    send_telegram: Optional[bool] = False
    send_discord: Optional[bool] = False
    
class ReportResponse(BaseModel):
    ticker: str
    status: str
    message: str
    file_path: Optional[str] = None
