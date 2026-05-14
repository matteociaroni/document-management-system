from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.routes import auth, folders, documents, permissions, health, history, admin
from app.routes import email_accounts, agent, branding, search
from app.schemas import ErrorResponse
from app.database import engine, close_db
from app.middleware import LastActiveMiddleware

app = FastAPI(title="Document Management System")

# Add CORS middleware (must be added before LastActiveMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track last_active_at for polling frequency strategy
app.add_middleware(LastActiveMiddleware)

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(folders.router)
app.include_router(documents.router)
app.include_router(permissions.router)
app.include_router(history.router)
app.include_router(admin.router)
app.include_router(email_accounts.router)
app.include_router(agent.router)
app.include_router(branding.router)
app.include_router(search.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Bad Request", "code": "VALIDATION_ERROR", "details": exc.errors()},
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown - close database connections"""
    close_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

