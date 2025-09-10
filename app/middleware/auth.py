from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import secrets
from app.services.config import get_settings

security = HTTPBasic()
settings = get_settings()

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, protected_paths: list = None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/", "/api"]
        
    async def dispatch(self, request: Request, call_next):
        # Check if path needs protection
        path = request.url.path
        needs_auth = any(path.startswith(protected_path) for protected_path in self.protected_paths)
        
        # Skip auth for login page and health check
        if path in ["/login", "/health"] or path.startswith("/static"):
            response = await call_next(request)
            return response
            
        if needs_auth:
            # Check for session cookie
            auth_cookie = request.cookies.get("auth_session")
            if not auth_cookie or not self.verify_session(auth_cookie):
                # Redirect to login page
                return RedirectResponse(url="/login", status_code=302)
        
        response = await call_next(request)
        return response
    
    def verify_session(self, session_cookie: str) -> bool:
        """Verify the session cookie"""
        # Simple session verification (in production, use JWT or proper session management)
        expected_session = f"authenticated_{settings.secret_key}"
        return secrets.compare_digest(session_cookie, expected_session)

def verify_password(username: str, password: str) -> bool:
    """Verify username and password"""
    # Simple password check (in production, use proper password hashing)
    correct_username = "admin"
    correct_password = settings.admin_password
    
    username_correct = secrets.compare_digest(username, correct_username)
    password_correct = secrets.compare_digest(password, correct_password)
    
    return username_correct and password_correct

def create_session_cookie() -> str:
    """Create a session cookie value"""
    return f"authenticated_{settings.secret_key}"