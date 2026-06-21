import os
import uuid
import asyncio
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters
from pyrogram.types import Message
from database import db

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

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# FastAPI Startup
@app.on_event("startup")
async def startup_event():
    # Start bot in background
    asyncio.create_task(start_bot_background())

async def start_bot_background():
    await bot.start()
    
    # বট চালু হওয়ার সাথে সাথে চ্যানেলে একটি মেসেজ পাঠিয়ে চ্যানেলটিকে "Resolve" করে নিবে
    try:
        await bot.send_message(DB_CHANNEL_ID, "🤖 Bot has started successfully!")
        print("DB Channel resolved successfully!")
    except Exception as e:
        print(f"Failed to resolve DB Channel: {e}")
        
    while True:
        await asyncio.sleep(3600)

@app.on_event("shutdown")
async def shutdown_event():
    await bot.stop()

@app.on_event("shutdown")
async def shutdown_event():
    await bot.stop()

# ---------------- Bot Handlers ----------------
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if user_id == ADMIN_ID:
        await message.reply_text("🎬 **MovieBoxBD Bot**\n\nSend me a Movie File (MP4/MKV) to upload.")
    else:
        await message.reply_text("This bot is for admin use only.")

@bot.on_message((filters.video | filters.document) & filters.private)
async def receive_movie(client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if user_id != ADMIN_ID:
        return
    
    status = await message.reply_text("Processing your movie...")
    
    try:
        # ফাইল পাওয়ার ঠিক পরেই বটকে চ্যানেল চিনিয়ে দেওয়া হচ্ছে
        await client.get_chat(DB_CHANNEL_ID)
        
        forwarded = await message.copy(DB_CHANNEL_ID)
        
        file_name = ""
        if message.video:
            file_name = message.video.file_name or "Movie"
            file_size = message.video.file_size
            file_id = message.video.file_id
        else:
            file_name = message.document.file_name or "Movie"
            file_size = message.document.file_size
            file_id = message.document.file_id

        title = message.caption if message.caption else file_name.split('.')[0]
        movie_id = str(uuid.uuid4())[:8]
        
        movie_data = {
            "_id": movie_id,
            "title": title,
            "file_size": file_size,
            "file_id": file_id,
            "message_id": forwarded.id
        }
        
        await db.add_movie(movie_data)
        link = f"{BASE_URL}/movie/{movie_id}"
        
        await status.edit_text(
            f"✅ **Movie Uploaded!**\n\n**Title:** {title}\n**Link:** [Click Here]({link})"
        )
    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")

# ---------------- Web Routes ----------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    movies = await db.get_all_movies()
    return templates.TemplateResponse("movie.html", {"request": request, "movies": movies, "page": "home", "movie": None})

@app.get("/movie/{movie_id}", response_class=HTMLResponse)
async def movie_page(request: Request, movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return templates.TemplateResponse("movie.html", {"request": request, "movie": movie, "page": "details"})

@app.get("/stream/{movie_id}")
async def stream_movie(movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    media = await bot.download_media(movie["file_id"], in_memory=True)
    
    headers = {
        "Content-Disposition": f"inline; filename=\"{movie['title']}.mp4\"",
        "Content-Type": "video/mp4"
    }
    return Response(content=media.getvalue(), headers=headers)

@app.get("/download/{movie_id}")
async def download_movie(movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    media = await bot.download_media(movie["file_id"], in_memory=True)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{movie['title']}.mp4\"",
        "Content-Type": "video/mp4"
    }
    return Response(content=media.getvalue(), headers=headers)

@app.get("/watch/{movie_id}", response_class=HTMLResponse)
async def watch_page(request: Request, movie_id: str):
    movie = await db.get_movie(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return templates.TemplateResponse("watch.html", {"request": request, "movie": movie, "stream_link": f"{BASE_URL}/stream/{movie_id}"})
