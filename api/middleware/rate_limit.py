from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict

# Simple in-memory rate limiting for MVP. 
# In production, this should use Redis to share state across workers.
# Free tier: 100 requests per minute
RATE_LIMIT = 100
RATE_LIMIT_WINDOW = 60 

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.requests = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = time.time()
        
        # Clean up old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] 
            if current_time - req_time < RATE_LIMIT_WINDOW
        ]
        
        if len(self.requests[client_ip]) >= RATE_LIMIT:
            return HTTPException(
                status_code=429, 
                detail="Rate limit exceeded. Try again later."
            )
            
        self.requests[client_ip].append(current_time)
        response = await call_next(request)
        return response
