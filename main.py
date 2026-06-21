import os
import uuid
import asyncio
import nest_asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters
from pyrogram.types import Message
from database import db

nest_asyncio.apply()

# Environment Variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL_ID", 0))
BASE_URL = os.environ.get("BASE_URL", "https://your-app.onrender.com")

bot = Client(
    "movie_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# --- নতুন ব্যাকগ্রাউন্ড টাস্ক কোড ---
async def start_bot_background():
    """Starts the Pyrogram bot in a background task to avoid Render Timeout"""
    await bot.start()
    # Keep the task running
    while True:
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create a background task for the bot
    task = asyncio.create_task(start_bot_background())
    yield
    # On shutdown, stop the bot and cancel the task
    await bot.stop()
    task.cancel()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# (এখান থেকে আপনার আগের কোডগুলো অর্থাৎ Bot Handlers এবং Web Routes অপরিবর্তিত থাকবে...)
