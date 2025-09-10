import os
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.api.scheduler import router as scheduler_router
from app.services.config import get_settings
from app.middleware.auth import AuthMiddleware, verify_password, create_session_cookie

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Crypto Scheduler Dashboard",
    description="Web dashboard for managing crypto analysis scheduler jobs",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
app.add_middleware(AuthMiddleware, protected_paths=["/", "/api"])

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except:
    # Static directory might not exist, that's okay
    pass

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API routes
app.include_router(scheduler_router, prefix="/api", tags=["scheduler"])

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Login page"""
    settings = get_settings()
    return templates.TemplateResponse("login.html", {
        "request": request,
        "app_name": settings.app_name,
        "error": error,
        "default_password": settings.admin_password
    })

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle login form submission"""
    if verify_password(username, password):
        # Create session cookie
        session_cookie = create_session_cookie()
        
        # Redirect to dashboard with session cookie
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="auth_session", 
            value=session_cookie, 
            max_age=86400,  # 24 hours
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        return response
    else:
        # Return to login page with error
        return RedirectResponse(url="/login?error=Invalid username or password", status_code=302)

@app.get("/logout")
async def logout():
    """Logout and clear session"""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("auth_session")
    return response

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page (protected)"""
    settings = get_settings()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "project_id": settings.google_cloud_project,
        "region": settings.google_cloud_region,
        "function_url": settings.crypto_function_url,
        "app_name": settings.app_name
    })

@app.get("/health")
async def health_check():
    """Health check endpoint (unprotected)"""
    return {
        "status": "healthy",
        "service": "crypto-scheduler-dashboard",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)