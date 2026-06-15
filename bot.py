import os
import logging
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Initialize Groq Client
groq_client = Groq(api_key=GROQ_API_KEY)

# State Management (Memory)
user_data = {
    "backlog_left": 30,
    "physics": 0,
    "chemistry": 0,
    "biology": 0,
    "math": 0,
    "daily_target": "No target set yet for today."
}

SYSTEM_PROMPT = """
You are 'Khayalamu', an elite, elder-sibling-like personal AI Mentor for a Bangladeshi student preparing for exams. The student has a backlog of 30 online classes across Physics, Chemistry, Biology, and Math.

Current Stats:
{status_str}
Today's Target: {daily_target}

### LANGUAGE & TONE RULES (CRITICAL):
- ALWAYS speak in natural, casual Banglish (Bengali written in English letters) or clean conversational Bengali. 
- NEVER use broken Google-translated words or mix Hindi/Urdu phrases (e.g., Never say "phir theko", "baksho", "ghumke jete hobe", "jari suggestion").
- Speak EXACTLY like a real supportive Bangladeshi friend, big brother, or mentor (e.g., use "bhai", "chill করো", "পড়তে বসো", "একটু ব্রেক নাও", "চা খেয়ে আসো").
- Keep responses concise, bold, and highly energetic. Use emojis properly.

### BREAK & MOTIVATION RULES:
- If the student says "bhalo lagtese na", "tired lage", or wants a break, give them a logical 15-minute offline task in natural language.
- Provide a clear, actionable micro-tip (e.g., "Phone-টা দূরে রেখে ৫ মিনিট হেঁটে আসো", "চোখে মুখে পানি দাও").
- Remind them of their daily target if they are slacking off.
"""

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f"Dummy server running on port {port}...")
    httpd.serve_forever()

# Custom Beautiful Layout for Status
async def get_status_str():
    total_done = 30 - user_data["backlog_left"]
    return (
        f"📊 *═══【 KHAYALAMU DASHBOARD 】═══*\n\n"
        f"🎯 *Total Backlog Left:* `{user_data['backlog_left']}/30`\n"
        f"✅ *Classes Completed:* `{total_done}`\n\n"
        f"📚 *Subject-wise Progress:*\n"
        f" ├ ⚛️ Physics: `{user_data['physics']}`\n"
        f" ├ 🧪 Chemistry: `{user_data['chemistry']}`\n"
        f" ├ 🧬 Biology: `{user_data['biology']}`\n"
        f" └ 📐 Math: `{user_data['math']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    )

# Persistent Custom Keyboard Buttons
def get_main_keyboard():
    keyboard = [
        ['📊 Check Status', '🎯 Set Daily Target'],
        ['✅ Done: Physics', '✅ Done: Chemistry'],
        ['✅ Done: Biology', '✅ Done: Math']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "👋 **Assalamu Alaikum! Ami tomar AI Mentor 'Khayalamu'.**\n\n"
        "Tomar 30 ta class er backlog sesh korar mission e ami tomar sathe achi. "
        "Ekhon theke kono kichu টাইপ করা লাগবে না, নিচের বাটনগুলো চাপ দিলেই হবে!\n\n"
        "👇 নিচের বাটন চাপো আর প্রোগ্রেস আপডেট করো:"
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    subject = None

    # Handle Button Actions
    if user_text == '📊 Check Status':
        status = await get_status_str()
        target_text = f"\n📌 *Today's Target:* {user_data['daily_target']}"
        await update.message.reply_text(status + target_text, parse_mode="Markdown")
        return

    elif user_text == '🎯 Set Daily Target':
        user_data["daily_target"] = "Waiting for your target..."
        await update.message.reply_text("📝 **Ajk tomar target ki bhai?**\nExactly likhe pathao, jemon: `Physics Ch 1, Chem Lecture 1` - ami mone rakhbo!")
        return

    # Check if user is trying to set a target
    if user_data["daily_target"] == "Waiting for your target...":
        user_data["daily_target"] = user_text
        await update.message.reply_text(f"🚀 **Target Set Successfully!**\n\n📌 *Today's Target:* `{user_text}`\n\nAmi mone rakhlam. Ebar baki class gila dhungmoto pore shesh koro!")
        return

    # Process Completed Classes via Buttons
    if user_text == '✅ Done: Physics':
        user_data["physics"] += 1
        user_data["backlog_left"] -= 1
        subject = "Physics"
    elif user_text == '✅ Done: Chemistry':
        user_data["chemistry"] += 1
        user_data["backlog_left"] -= 1
        subject = "Chemistry"
    elif user_text == '✅ Done: Biology':
        user_data["biology"] += 1
        user_data["backlog_left"] -= 1
        subject = "Biology"
    elif user_text == '✅ Done: Math':
        user_data["math"] += 1
        user_data["backlog_left"] -= 1
        subject = "Math"

    status_str = await get_status_str()
    
    # Context prompt configuration
    if subject:
        ai_input = f"I just finished 1 {subject} class, including notes, practice, and exam!"
    else:
        ai_input = user_text

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(status_str=status_str, daily_target=user_data["daily_target"])},
                {"role": "user", "content": ai_input}
            ],
            model="llama-3.1-8b-instant",
        )
        reply = chat_completion.choices[0].message.content
        
        # If subject was updated, show the new stats under AI reply
        if subject:
            reply += f"\n\n{status_str}\n📌 *Today's Target:* {user_data['daily_target']}"
            
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Groq Error: {e}")
        if subject:
            await update.message.reply_text(f"✅ {subject} er progress save hoise! But Groq API ektu jhamela kortese.\n\n{status_str}")
        else:
            await update.message.reply_text("🤖 'Khayalamu' bhabtese... kintu Groq API line paiteche na.")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
