import os

# pyrefly: ignore [missing-import]
import certifi
import logging
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from backend.database.db import init_db
from backend.routes.upload import router as upload_router
from backend.routes.chat import router as chat_router
from backend.routes.history import router as history_router
from backend.routes.debug import router as debug_router

load_dotenv()
init_db()
# Enable debug logging for troubleshooting
logging.basicConfig(level=logging.DEBUG)
app = FastAPI()
app.include_router(history_router)
os.environ["SSL_CERT_FILE"] = certifi.where()


@app.middleware("http")
async def log_requests(request, call_next):
    # Lightweight request logger to help debug 405/route issues
    try:
        method = request.method
        path = request.url.path
        print(f"[HTTP] {method} {path}")
    except Exception:
        pass

    response = await call_next(request)

    try:
        print(f"[HTTP] -> {response.status_code} {method} {path}")
    except Exception:
        pass

    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routes
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(debug_router)


@app.get("/")
def home():
    return {"message": "RAG Chatbot Backend Running"}