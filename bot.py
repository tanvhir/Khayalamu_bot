import os
import logging
import threading
import datetime
import requests
import json
import re
from http.server import SimpleHTTPRequestHandler, HTTPServer
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# API Keys & Security Configuration
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")

# 🔒 তোমার টেলিগ্রাম চ্যাট আইডি
ALLOWED_CHAT_ID = int(os.environ.get("ALLOWED_CHAT_ID", 5959341337))

# Selected Model for OpenRouter
OPENROUTER_MODEL = "google/gemma-4-31b-it:free"

# 🧠 Advanced State Management & Memory
user_data = {
    "daily_target_raw": "No target set yet.",
    "current_state": "NORMAL",
    "chat_history": []  # শর্ট-টার্ম মেমোরির জন্য
}

# 📚 মেগা সিলেবাস মেমোরি
user_syllabus = {}

MAX_HISTORY_LENGTH = 12  # শেষ ৬টি ইউজার-বট কনভার্সেশন মনে রাখবে

# 🚀 અપডেটেড সিস্টেম প্রম্পট (আসল জিতু ভাইয়া পার্সোনা)
SYSTEM_PROMPT = """
You are 'Jeetu Bhaiya' (from Kota Factory), an elite, deeply empathetic, yet hardcore and practical personal AI Mentor for a Bangladeshi competitive examinee.

### CORE PERSONA & TONE RULES:
- STRICTLY speak in NATURAL, CASUAL, COLLOQUIAL BANGLADESHI BENGALI (e.g., তুই/তুমি, ভাই, শোন, প্যারা নাই, চিল কর).
- Give "Tough Love": Scold if they slack, but SHOW EMPATHY if they are genuinely trying, tired, or studied late at night.
- ACT LIKE A STRATEGIST: Don't just tell them to "study". Give study hacks (e.g., Pomodoro technique, Active Recall, "take a 10 min break", "solve questions first").
- AVOID REPETITION: NEVER be a robotic alarm clock. DO NOT repeat the same phrases (like "কড়া চা খা", "২৫ বছর বয়সে আফসোস করবি", "মাঝরাত পর্যন্ত আর X ঘণ্টা বাকি") in every message. Be unpredictable.

### CONTEXT AWARENESS (MEMORY):
- You have access to recent Chat History. REMEMBER what the user said previously (e.g., if they were awake at 4 AM planning with you, DO NOT scold them for waking up late at 11 AM).
- Current Bangladesh Time: {current_time}
- Overall Backlog Status: {status_str}
- Today's Target: {daily_target_raw}

### INSTRUCTION FOR THIS MESSAGE:
{context_reason}
"""

def get_bd_time():
    """বাংলাদেশের বর্তমান সময় অবজেক্ট রিটার্ন করে"""
    return datetime.datetime.utcnow() + datetime.timedelta(hours=6)

# --- 🌐 OpenRouter API Integration Engine with Memory ---
def generate_openrouter_chat(system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
    """OpenRouter API ব্যবহার করে চ্যাট জেনারেট করার ফাংশন"""
    if not OPENROUTER_API_KEY:
        return "আরে ভাই, তোমার OpenRouter API Key তো সেট করা নাই!"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram.org",
        "X-Title": "Jeetu Bhaiya Mentor Bot"
    }
    
    # মেমোরি ইনজেকশন
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(user_data["chat_history"])
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            res_json = response.json()
            bot_reply = res_json["choices"][0]["message"]["content"]
            
            # মেমোরি আপডেট
            user_data["chat_history"].append({"role": "user", "content": user_message})
            user_data["chat_history"].append({"role": "assistant", "content": bot_reply})
            
            # মেমোরি লিমিট কন্ট্রোল
            if len(user_data["chat_history"]) > MAX_HISTORY_LENGTH:
                user_data["chat_history"] = user_data["chat_history"][-MAX_HISTORY_LENGTH:]
                
            return bot_reply
        else:
            logging.error(f"OpenRouter Error: {response.text}")
            return "ধুর ভাই! সার্ভার ঝামেলা করতেছে। একটু পরে বল।"
    except Exception as e:
        logging.error(f"Connection Error: {e}")
        return "নেটওয়ার্ক ড্রপ খাইছে ভাই! আবার ট্রাই কর।"

# --- 📊 ডাইনামিক সিলেবাস অ্যানালিটিক্স ---
def calculate_backlog_metrics():
    total_backlogs = 0
    sub_counts = {"P": 0, "C": 0, "B": 0, "M": 0}
    for item, status in user_syllabus.items():
        sub_part = item.split("_")[0].upper()
        sub_key = sub_part[0] if sub_part[0] in sub_counts else None
        if any(status.get(t, "Pending") == "Pending" for t in ["class", "note", "practice", "exam"]):
            total_backlogs += 1
            if sub_key: sub_counts[sub_key] += 1
    return total_backlogs, sub_counts

async def get_status_str():
    total_backlogs, sub_counts = calculate_backlog_metrics()
    return (f"বাকি ব্যাকলগ: {total_backlogs}টি লেকচার | "
            f"P: {sub_counts['P']}, C: {sub_counts['C']}, "
            f"B: {sub_counts['B']}, M: {sub_counts['M']}")

# --- 🌐 Apps Script Database Sync Engine (OPTIMIZED) ---
def save_target_to_sheet():
    """শুধুমাত্র টার্গেট আপডেট হলে এই ফাংশন কল হবে"""
    if not APPS_SCRIPT_URL: return
    try:
        payload = {
            "chat_id": str(ALLOWED_CHAT_ID),
            "target_update": True,
            "target": user_data["daily_target_raw"]
        }
        requests.post(APPS_SCRIPT_URL, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Target Save Error: {e}")

def save_single_lecture_to_sheet(lecture_key):
    """লুপ পরিহার করে শুধুমাত্র নির্দিষ্ট লেকচার আপডেট করবে"""
    if not APPS_SCRIPT_URL: return
    try:
        status = user_syllabus.get(lecture_key, {})
        payload = {
            "chat_id": str(ALLOWED_CHAT_ID),
            "syllabus_update": True,
            "lecture_key": lecture_key,
            "class": status.get("class", "Pending"),
            "note": status.get("note", "Pending"),
            "practice": status.get("practice", "Pending"),
            "exam": status.get("exam", "Pending")
        }
        requests.post(APPS_SCRIPT_URL, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Lecture Save Error: {e}")

def load_from_google_sheet():
    global user_data, user_syllabus
    if not APPS_SCRIPT_URL: return
    try:
        url = f"{APPS_SCRIPT_URL}?chat_id={ALLOWED_CHAT_ID}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("found"):
                user_data["daily_target_raw"] = res_data.get("target", "No target set yet.")
                syllabus_dict = res_data.get("syllabus", {})
                new_syllabus = {}
                for key, status in syllabus_dict.items():
                    new_syllabus[key] = {
                        "class": status.get("class", "Pending"),
                        "note": status.get("note", "Pending"),
                        "practice": status.get("practice", "Pending"),
                        "exam": status.get("exam", "Pending")
                    }
                user_syllabus = new_syllabus
                logging.info("✅ Data loaded successfully!")
    except Exception as e:
        logging.error(f"Load Error: {e}")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

# --- ⌨️ কিবোর্ড লেআউট জেনারেটর ---
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ['Check Status', 'Set Target', 'Stop Reminders', 'Syllabus Report'],
        ['Manage Syllabus']
    ], resize_keyboard=True)

def get_syllabus_keyboard():
    return ReplyKeyboardMarkup([
        ['Add New Lecture', 'Mark Class Done'],
        ['Mark Note Done', 'Mark Practice Done'],
        ['Mark Exam Done'],
        ['Back to Main Menu']
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    user_data["current_state"] = "NORMAL"
    user_data["chat_history"] = [] # মেমোরি রিসেট
    await update.message.reply_text("👋 **আসসালামু আলাইকুম ভাই! আমি তোমার মেন্টর 'Jeetu Bhaiya'**\n\nসিস্টেম এবং মেমোরি আপডেটেড! চলো শুরু করি।", reply_markup=get_main_keyboard())

# --- 📚 রেঞ্জ পার্সার ---
def parse_lecture_range(lecture_str):
    lecture_str = lecture_str.upper().strip()
    match = re.match(r"L(\d+)-L?(\d+)", lecture_str)
    if match:
        return [f"L{i}" for i in range(int(match.group(1)), int(match.group(2)) + 1)]
    return [lecture_str]

def extract_lecture_details(text):
    parts = text.strip().split()
    if len(parts) < 3: return None, None, None
    ch = parts[1].upper()
    if not ch.startswith("CH") and ch[0].isdigit(): ch = f"CH{ch}"
    return parts[0].upper(), ch, parse_lecture_range(parts[2])

async def view_syllabus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    if not user_syllabus:
        return await update.message.reply_text("📭 সিলেবাস এখনো খালি ভাই!")

    total_tasks = sum(1 for status in user_syllabus.values() for t in ["class", "note", "practice", "exam"])
    completed_tasks = sum(1 for status in user_syllabus.values() for t in ["class", "note", "practice", "exam"] if status.get(t) == "Done")
    
    percentage = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    bar = "█" * (percentage // 10) + "░" * (10 - (percentage // 10))

    report = f"📚 **সিলেবাস রিপোর্ট:**\n📈 Progress: `[{bar}] {percentage}%`\n────────────────\n"
    for item, status in sorted(user_syllabus.items()):
        report += f"• **{item.replace('_', ' ')}** ➔ 📺{'🟢' if status.get('class')=='Done' else '🔴'} 📝{'🟢' if status.get('note')=='Done' else '🔴'} 🎯{'🟢' if status.get('practice')=='Done' else '🔴'} 🏆{'🟢' if status.get('exam')=='Done' else '🔴'}\n"
    await update.message.reply_text(report, parse_mode="Markdown")

async def stop_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    for job in context.job_queue.get_jobs_by_name("hourly_tracker"):
        job.schedule_removal()
    user_data["daily_target_raw"] = "No target set yet."
    user_data["current_state"] = "NORMAL"
    save_target_to_sheet()
    await update.message.reply_text("🛑 **রিমাইন্ডার অফ করা হলো!** ভালো করে ঘুমাও, ব্রেক নাও।", reply_markup=get_main_keyboard())

# --- ⏰ ডাইনামিক রিমাইন্ডার ইঞ্জিন ---
async def hourly_mentor_check(context: ContextTypes.DEFAULT_TYPE):
    if user_data["daily_target_raw"] == "No target set yet.": return

    status_str = await get_status_str()
    bd_time = get_bd_time().strftime("%I:%M %p")
    
    # রিমাইন্ডারের জন্য ডাইনামিক প্রম্পট ইনজেকশন
    context_reason = "This is an automated 1-hour check. Give a VERY SHORT (1-3 lines max), punchy reminder based on the time. DO NOT write long paragraphs. If they just started a few hours ago, give a study hack. If it's very late, tell them to wrap up."
    
    sys_prompt = SYSTEM_PROMPT.format(current_time=bd_time, status_str=status_str, daily_target_raw=user_data["daily_target_raw"], context_reason=context_reason)

    try:
        response_text = generate_openrouter_chat(sys_prompt, "[SYSTEM: HOURLY REMINDER TRIGGERED]", temperature=0.8)
        await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=response_text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Hourly error: {e}")

async def test_hourly_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    await update.message.reply_text("⏳ ১০ সেকেন্ডের ডেমো রিয়েলিটি চেক আসছে...")
    context.job_queue.run_once(hourly_mentor_check, 10)

# --- 💬 মেসেজ রাউটার ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    user_text = update.message.text.strip()
    current_state = user_data["current_state"]

    if user_text == 'Check Status':
        return await update.message.reply_text(await get_status_str())
    elif user_text == 'Set Target':
        user_data["current_state"] = "WAITING_FOR_TARGET"
        return await update.message.reply_text("📝 **আজকে রাত ১২টার মধ্যে কী টার্গেট? ডিটেইলসে বলো!**")
    elif user_text == 'Syllabus Report':
        return await view_syllabus(update, context)
    elif user_text == 'Stop Reminders':
        return await stop_plan(update, context)
    elif user_text == 'Manage Syllabus':
        user_data["current_state"] = "NORMAL"
        return await update.message.reply_text("📚 **কী আপডেট করবা? বাটন চাপো:**", reply_markup=get_syllabus_keyboard())
    elif user_text == 'Back to Main Menu':
        user_data["current_state"] = "NORMAL"
        return await update.message.reply_text("🔙 প্রধান মেনু", reply_markup=get_main_keyboard())

    elif user_text in ['Add New Lecture', 'Mark Class Done', 'Mark Note Done', 'Mark Practice Done', 'Mark Exam Done']:
        state_map = {"Add": "WAITING_FOR_ADD", "Class": "WAITING_FOR_CLASS", "Note": "WAITING_FOR_NOTE", "Practice": "WAITING_FOR_PRACTICE", "Exam": "WAITING_FOR_EXAM"}
        state_key = next(k for k in state_map if k in user_text)
        user_data["current_state"] = state_map[state_key]
        return await update.message.reply_text(f"কোড দাও ভাই। উদাহরণ: `P1 C6 L1-5`")

    # ডাটা প্রসেসিং স্টেট
    if current_state == "WAITING_FOR_TARGET":
        user_data["daily_target_raw"] = user_text
        user_data["current_state"] = "NORMAL"
        save_target_to_sheet() # শুধুমাত্র টার্গেট সেভ হবে

        for job in context.job_queue.get_jobs_by_name("hourly_tracker"): job.schedule_removal()
        context.job_queue.run_repeating(hourly_mentor_check, interval=3600, first=3600, name="hourly_tracker")

        sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), status_str=await get_status_str(), daily_target_raw=user_data["daily_target_raw"], context_reason="The user just set this target. Acknowledge it, give a short strategy, and tell them to start.")
        response_text = generate_openrouter_chat(sys_prompt, f"Set target: {user_text}", 0.7)
        return await update.message.reply_text(response_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif current_state == "WAITING_FOR_ADD":
        sub, ch, lectures = extract_lecture_details(user_text)
        if not sub: return await update.message.reply_text("❌ ফরম্যাট ভুল!")
        for lec in lectures:
            key = f"{sub}_{ch}_{lec}"
            if key not in user_syllabus:
                user_syllabus[key] = {"class": "Pending", "note": "Pending", "practice": "Pending", "exam": "Pending"}
                save_single_lecture_to_sheet(key) # শুধুমাত্র নতুন লেকচার সেভ
        user_data["current_state"] = "NORMAL"
        return await update.message.reply_text(f"✅ যোগ করা হয়েছে!", reply_markup=get_main_keyboard())

    elif current_state.startswith("WAITING_FOR_"):
        sub, ch, lectures = extract_lecture_details(user_text)
        if not sub: return await update.message.reply_text("❌ ফরম্যাট ভুল!")
        task_type = current_state.split("_")[-1].lower()
        
        updated = 0
        for lec in lectures:
            key = f"{sub}_{ch}_{lec}"
            if key in user_syllabus:
                user_syllabus[key][task_type] = "Done"
                save_single_lecture_to_sheet(key) # শুধুমাত্র যেই লেকচার আপডেট হলো সেটা সেভ হবে
                updated += 1
        
        user_data["current_state"] = "NORMAL"
        return await update.message.reply_text(f"🎉 {updated}টি লেকচারের {task_type.upper()} ডান!", reply_markup=get_main_keyboard())

    # নরমাল চ্যাট রাউটিং
    sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), status_str=await get_status_str(), daily_target_raw=user_data["daily_target_raw"], context_reason="Respond naturally to the user. Guide them, scold them, or appreciate them based on their message and previous context.")
    response_text = generate_openrouter_chat(sys_prompt, user_text, 0.7)
    await update.message.reply_text(response_text, parse_mode="Markdown")

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    load_from_google_sheet()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", start))
    app.add_handler(CommandHandler("report", view_syllabus))
    app.add_handler(CommandHandler("stop_plan", stop_plan))
    app.add_handler(CommandHandler("test_remind", test_hourly_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Optimized Jeetu Bhaiya AI is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
