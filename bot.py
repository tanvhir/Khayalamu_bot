import os
import logging
import threading
import datetime
from http.server import SimpleHTTPRequestHandler, HTTPServer
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# API Keys & Security Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# 🔒 এখানে তোমার আসল টেলিগ্রাম চ্যাট আইডি বসাও (যাতে লক না দেখায়)
ALLOWED_CHAT_ID = int(os.environ.get("ALLOWED_CHAT_ID", 5959341337)) 

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

# State Management (Memory)
user_data = {
    "backlog_left": 30,
    "physics": 0,
    "chemistry": 0,
    "biology": 0,
    "math": 0,
    "daily_target": "No target set yet for today."
}

# খাঁটি বাংলা সিস্টেম ইনস্ট্রাকশন
SYSTEM_PROMPT = """
You are 'Khayalamu', an elite, strict yet loving personal AI Mentor for a Bangladeshi student preparing for exams. 

### LANGUAGE & TONE RULES (CRITICAL):
- ALWAYS speak in 100% NATURAL, CASUAL, and COLLOQUIAL BANGLADESHI BENGALI (খাঁটি বাংলাদেশি বন্ধুদের বা বড় ভাইদের মতো ইনফরমাল বাংলা ভাষা)।
- NEVER use bookish or literal Google-translated words (e.g., NEVER say "নিঃশ্বাস সংক্রমণ", "মানসিকভাবে থাকবে", "শিক্ষা সর্বোচ্চ আছে")।
- Speak EXACTLY like a supportive Bangladeshi big brother, senior, or personal coach. Use words like "আরে ভাই", "শোনো", "পড়তে বসো", "একটু ব্রেক নাও", "চা খেয়ে আসো", "ফাঁকিবাজি বন্ধ করো", "চিল করো"।
- Keep your answers short, clear, full of emojis, and highly motivating.

### CURRENT STUDENT STATUS:
{status_str}
"""

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f"Dummy server running on port {port}...")
    httpd.serve_forever()

async def get_status_str():
    total_done = 30 - user_data["backlog_left"]
    return (
        f" ═══【STATUS】═══\n\n"
        f"🎧 Total Backlog Left: {user_data['backlog_left']}/30\n"
        f"🎗 Classes Completed: {total_done}\n\n"
        f"📚 Subject-wise Progress:\n"
        f" ├  Physics: {user_data['physics']}\n"
        f" ├ Chemistry: {user_data['chemistry']}\n"
        f" ├ Biology: {user_data['biology']}\n"
        f" └ Math: {user_data['math']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Today's Target: {user_data['daily_target']}"
    )

def get_main_keyboard():
    keyboard = [
        ['📊 স্ট্যাটাস চেক', '🎯 আজকের টার্গেট সেট'],
        ['✅ শেষ: Physics', '✅ শেষ: Chemistry'],
        ['✅ শেষ: Biology', '✅ শেষ: Math']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ দুঃখিত ভাই! এই বোটটি সম্পূর্ণ ব্যক্তিগত।")
        return

    welcome_msg = (
        "👋 **আসসালামু আলাইকুম ভাই! আমি তোমার এআই মেন্টর 'Khayalamu'।**\n\n"
        "গুগল জেমিনির পাওয়ার নিয়ে এখন আমি লাইনে আছি। পড়ালেখার কী অবস্থা বলো?\n"
        "👇 নিচের বাটনগুলো ব্যবহার করতে পারো:"
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

# --- ⏰ REMINDER SYSTEM ---
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    status_str = await get_status_str()
    reminder_msg = (
        f"🚨 **ভাই! আজকের টার্গেটের কী অবস্থা?**\n\n"
        f"🏆 *আজকের লক্ষ্য ছিল:* `{user_data['daily_target']}`\n\n"
        f"ফাঁকিবাজি না করে দ্রুত পড়া শেষ করো! কোনো ক্লাস শেষ হলে নিচের বাটন চেপে আপডেট জানিয়ে দাও।\n\n"
        f"{status_str}"
    )
    try:
        await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=reminder_msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Reminder failed: {e}")

async def test_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    await update.message.reply_text("⏳ জেমিনি রিমাইন্ডার ইঞ্জিন টেস্ট হচ্ছে... ঠিক ১০ সেকেন্ড পর বোট নিজে থেকে মেসেজ দেবে!")
    context.job_queue.run_once(send_reminder, 10)
# ---------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ এই বোটটি লক করা আছে।")
        return

    user_text = update.message.text
    subject = None

    if user_text == '📊 স্ট্যাটাস চেক':
        status = await get_status_str()
        await update.message.reply_text(status, parse_mode="Markdown")
        return

    elif user_text == '🎯 আজকের টার্গেট সেট':
        user_data["daily_target"] = "Waiting for your target..."
        await update.message.reply_text("📝 **আজকে তোমার টার্গেট কী ভাই?**\nলিখে পাঠাও, আমি মনে রাখছি!")
        return

    if user_data["daily_target"] == "Waiting for your target...":
        user_data["daily_target"] = user_text
        await update.message.reply_text(f"🚀 **টার্গেট সেট হয়ে গেছে ভাই!**\n\n🏆 *আজকের টার্গেট:* `{user_text}`\n\nএবার পড়তে বসে যাও!")
        return

    # সাবজেক্ট আপডেট হ্যান্ডলিং
    if user_text == '✅ শেষ: Physics':
        user_data["physics"] += 1; user_data["backlog_left"] -= 1; subject = "Physics"
    elif user_text == '✅ শেষ: Chemistry':
        user_data["chemistry"] += 1; user_data["backlog_left"] -= 1; subject = "Chemistry"
    elif user_text == '✅ শেষ: Biology':
        user_data["biology"] += 1; user_data["backlog_left"] -= 1; subject = "Biology"
    elif user_text == '✅ শেষ: Math':
        user_data["math"] += 1; user_data["backlog_left"] -= 1; subject = "Math"

    status_str = await get_status_str()
    ai_input = f"I just finished 1 {subject} class!" if subject else user_text

    try:
        # জেমিনি এপিআই কল করার নতুন স্ট্যান্ডার্ড ফরম্যাট
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=ai_input,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT.format(status_str=status_str),
                temperature=0.7,
            ),
        )
        reply = response.text
        if subject:
            reply += f"\n\n{status_str}"
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        if subject:
            await update.message.reply_text(f"✅ {subject} আপডেট হয়েছে ভাই!\n\n{status_str}")
        else:
            await update.message.reply_text("🤖 জেমিনি একটু জ্যামে আছে ভাই, আবার ট্রাই করো!")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # অটো রিমাইন্ডার শিডিউল (দুপুর ৩টা ও রাত ৯টা)
    app.job_queue.run_daily(send_reminder, time=datetime.time(hour=9, minute=0))
    app.job_queue.run_daily(send_reminder, time=datetime.time(hour=15, minute=0))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test_remind", test_reminder_command)) 
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running with Pure Gemini Engine...")
    app.run_polling()

if __name__ == '__main__':
    main()
