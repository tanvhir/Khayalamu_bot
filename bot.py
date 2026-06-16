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
    "chat_history": []
}

MAX_HISTORY_LENGTH = 12  # শেষ ৬টি ইউজার-বট কনভার্সেশন মনে রাখবে

# 📚 মেগা সিলেবাস মেমোরি
user_syllabus = {}

# 📖 চ্যাপ্টার ডিকশনারি (শর্টকোড টু রিয়েল নেম)
# তুমি চাইলে ভবিষ্যতে এখানে আরও চ্যাপ্টার অ্যাড করতে পারবে
CHAPTER_NAMES = {
    # Physics 1st Paper
    "P1_C1": "ভৌত জগৎ ও পরিমাপ",
    "P1_C2": "ভেক্টর",
    "P1_C3": "গতিবিদ্যা",
    "P1_C4": "নিউটনীয় বলবিদ্যা",
    "P1_C5": "কাজ, শক্তি ও ক্ষমতা",
    "P1_C6": "মহাকর্ষ ও অভিকর্ষ",
    "P1_C7": "পদার্থের গাঠনিক ধর্ম",
    "P1_C8": "পর্যাবৃত্ত গতি",
    "P1_C9": "তরঙ্গ",
    "P1_C10": "আদর্শ গ্যাস ও গ্যাসের গতিতত্ত্ব",

    # Physics 2nd Paper
    "P2_C1": "তাপগতিবিদ্যা",
    "P2_C2": "স্থির তড়িৎ",
    "P2_C3": "চল তড়িৎ",
    "P2_C4": "তড়িৎ প্রবাহের চৌম্বক ক্রিয়া ও চৌম্বকত্ব",
    "P2_C5": "তড়িৎচুম্বকীয় আবেশ ও পরিবর্তী প্রবাহ",
    "P2_C6": "জ্যামিতিক আলোকবিজ্ঞান",
    "P2_C7": "ভৌত আলোকবিজ্ঞান",
    "P2_C8": "আধুনিক পদার্থবিজ্ঞানের সূচনা",

    # Chemistry 1st Paper
    "C1_C1": "ল্যাবরেটরির নিরাপদ ব্যবহার",
    "C1_C2": "গুণগত রসায়ন",
    "C1_C3": "মৌলের পর্যায়বৃত্ত ধর্ম ও রাসায়নিক বন্ধন",
    "C1_C4": "রাসায়নিক পরিবর্তন",
    "C1_C5": "কর্মমুখী রসায়ন",

    # Chemistry 2nd Paper
    "C2_C1": "পরিবেশ রসায়ন",
    "C2_C2": "জৈব রসায়ন",
    "C2_C3": "পরিমাণগত রসায়ন",
    "C2_C4": "তড়িৎ রসায়ন",
    "C2_C5": "অর্থনৈতিক রসায়ন",

    # Mathematics 1st Paper
    "M1_C1": "ম্যাট্রিক্স ও নির্ণায়ক",
    "M1_C2": "সরলরেখা",
    "M1_C3": "বৃত্ত",
    "M1_C4": "বিন্যাস ও সমাবেশ",
    "M1_C5": "ত্রিকোণমিতিক অনুপাত",
    "M1_C6": "সংযুক্ত কোণের ত্রিকোণমিতিক অনুপাত",
    "M1_C7": "ফাংশন ও ফাংশনের লেখচিত্র",
    "M1_C8": "অন্তর্বর্তী ও বিপরীত ত্রিকোণমিতিক ফাংশন",
    "M1_C9": "অন্তরীকরণ",
    "M1_C10": "যোগজীকরণ",

    # Mathematics 2nd Paper
    "M2_C1": "বাস্তব সংখ্যা ও অসমতা",
    "M2_C2": "বহুপদী ও বহুপদী সমীকরণ",
    "M2_C3": "জটিল সংখ্যা",
    "M2_C4": "দ্বিপদী বিস্তৃতি",
    "M2_C5": "কণিক",
    "M2_C6": "স্থিতিবিদ্যা",
    "M2_C7": "সমতলে বস্তুকণার গতি",
    "M2_C8": "সম্ভাবনা",
    "M2_C9": "পরিসংখ্যান",

    # Biology 1st Paper
    "B1_C1": "কোষ ও এর গঠন",
    "B1_C2": "কোষ বিভাজন",
    "B1_C3": "কোষ রসায়ন",
    "B1_C4": "অণুজীব",
    "B1_C5": "শৈবাল ও ছত্রাক",
    "B1_C6": "ব্রায়োফাইটা ও টেরিডোফাইটা",
    "B1_C7": "নগ্নবীজী ও আবৃতবীজী উদ্ভিদ",
    "B1_C8": "টিস্যু ও টিস্যুতন্ত্র",
    "B1_C9": "উদ্ভিদ শারীরতত্ত্ব",
    "B1_C10": "উদ্ভিদ প্রজনন",
    "B1_C11": "জীবপ্রযুক্তি",

    # Biology 2nd Paper
    "B2_C1": "প্রাণীর বিভিন্নতা ও শ্রেণিবিন্যাস",
    "B2_C2": "প্রাণীর পরিচিতি",
    "B2_C3": "পরিপাক ও শোষণ",
    "B2_C4": "রক্ত ও সঞ্চালন",
    "B2_C5": "শ্বাসক্রিয়া ও শ্বসন",
    "B2_C6": "বর্জ্য ও নিষ্কাশন",
    "B2_C7": "চলন ও অঙ্গচালনা",
    "B2_C8": "সমন্বয় ও নিয়ন্ত্রণ",
    "B2_C9": "মানব জীবনের ধারাবাহিকতা",
    "B2_C10": "মানবদেহের প্রতিরক্ষা",
    "B2_C11": "জিনতত্ত্ব ও বিবর্তন",
    "B2_C12": "প্রাণীর আচরণ",
    "B2_C13": "জীবের পরিবেশ, বিস্তার ও সংরক্ষণ"
}

def get_friendly_name(lecture_key):
    """P1_C2_L1 কে 'ভেক্টর - লেকচার ১' এ কনভার্ট করবে"""
    parts = lecture_key.split("_")
    if len(parts) >= 3:
        sub_ch = f"{parts[0]}_{parts[1]}"
        lec = parts[2].replace("L", "লেকচার ")
        chap_name = CHAPTER_NAMES.get(sub_ch, f"{parts[0]} {parts[1]}")
        return f"{chap_name} - {lec}"
    return lecture_key

# 🚀 અપডেটেড সিস্টেম প্রম্পট (আসল জিতু ভাইয়া পার্সোনা + কোড ডিকশনারি)
SYSTEM_PROMPT = """
You are 'Jeetu Bhaiya' (from Kota Factory), an elite, deeply empathetic, yet hardcore and practical personal AI Mentor for a Bangladeshi competitive examinee.

### CORE PERSONA & TONE RULES:
- STRICTLY speak in NATURAL, CASUAL, COLLOQUIAL BANGLADESHI BENGALI (e.g., তুই/তুমি, ভাই, শোন, প্যারা নাই, চিল কর).
- Give "Tough Love": Scold if they slack, but SHOW EMPATHY if they are genuinely trying.
- ACT LIKE A STRATEGIST: Give study hacks (Pomodoro, Active Recall).
- AVOID REPETITION: NEVER be a robotic alarm clock. Don't repeat the same dialogues.

### CODE DICTIONARY (CRITICAL):
The user uses short codes for subjects and chapters. If they say "c2 c1 l1" or "C2 C1 L1", UNDERSTAND they mean a SPECIFIC lecture (e.g., Chemistry 2nd Paper, Chapter 1, Lecture 1).
- P = Physics, C = Chemistry, M = Math, B = Biology.

### CONTEXT AWARENESS & MEMORY:
- You have access to recent Chat History. REMEMBER what the user said previously.
- Current Bangladesh Time: {current_time}
- Backlog & Pending Lectures Status (Real Chapter Names): {status_str}
- Today's Target: {daily_target_raw}

### INSTRUCTION FOR THIS MESSAGE:
{context_reason}
"""

def get_bd_time():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=6)

# --- 🌐 OpenRouter API Integration Engine with Memory ---
def generate_openrouter_chat(system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
    if not OPENROUTER_API_KEY:
        return "আরে ভাই, তোমার OpenRouter API Key তো সেট করা নাই!"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram.org",
        "X-Title": "Jeetu Bhaiya Mentor Bot"
    }
    
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
            
            # Update memory
            user_data["chat_history"].append({"role": "user", "content": user_message})
            user_data["chat_history"].append({"role": "assistant", "content": bot_reply})
            if len(user_data["chat_history"]) > MAX_HISTORY_LENGTH:
                user_data["chat_history"] = user_data["chat_history"][-MAX_HISTORY_LENGTH:]
                
            return bot_reply
        else:
            logging.error(f"OpenRouter Error: {response.text}")
            return "ধুর ভাই! সার্ভার ঝামেলা করতেছে। একটু পরে বল।"
    except Exception as e:
        logging.error(f"Connection Error: {e}")
        return "নেটওয়ার্ক ড্রপ খাইছে ভাই! আবার ট্রাই কর।"

# --- 📊 ডাইনামিক সিলেবাস অ্যানালিটিক্স (with Friendly Names) ---
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
    
    pending_list = []
    for item, status in user_syllabus.items():
        if any(status.get(t, "Pending") == "Pending" for t in ["class", "note", "practice", "exam"]):
            pending_list.append(get_friendly_name(item))
            
    pending_str = ", ".join(pending_list) if pending_list else "কোনো ব্যাকলগ নাই! সব ক্লিয়ার।"

    return (f"বাকি ব্যাকলগ: {total_backlogs}টি লেকচার | "
            f"P: {sub_counts['P']}, C: {sub_counts['C']}, "
            f"B: {sub_counts['B']}, M: {sub_counts['M']}\n"
            f"Pending Chapters: [{pending_str}]")

# --- 🌐 Apps Script Database Sync Engine (OPTIMIZED) ---
def save_target_to_sheet():
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
    user_data["chat_history"] = [] 
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
        real_name = get_friendly_name(item)
        c_emo = '🟢' if status.get('class')=='Done' else '🔴'
        n_emo = '🟢' if status.get('note')=='Done' else '🔴'
        p_emo = '🟢' if status.get('practice')=='Done' else '🔴'
        e_emo = '🟢' if status.get('exam')=='Done' else '🔴'
        report += f"• **{real_name}** ➔ 📺{c_emo} 📝{n_emo} 🎯{p_emo} 🏆{e_emo}\n"
        
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
    context_reason = "This is an automated 1-hour check. Give a VERY SHORT (1-3 lines max), punchy reminder based on the time. Use the exact Chapter Names from the status string. DO NOT write long paragraphs."
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
        return await update.message.reply_text(f"কোড দাও ভাই। উদাহরণ: `P1 C2 L1-5` (ভেক্টর লেকচার ১ থেকে ৫)")

    # ডাটা প্রসেসিং স্টেট
    if current_state == "WAITING_FOR_TARGET":
        user_data["daily_target_raw"] = user_text
        user_data["current_state"] = "NORMAL"
        save_target_to_sheet()

        for job in context.job_queue.get_jobs_by_name("hourly_tracker"): job.schedule_removal()
        context.job_queue.run_repeating(hourly_mentor_check, interval=3600, first=3600, name="hourly_tracker")

        sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), status_str=await get_status_str(), daily_target_raw=user_data["daily_target_raw"], context_reason="The user just set this target. Acknowledge it using the chapter names, give a short strategy, and tell them to start.")
        response_text = generate_openrouter_chat(sys_prompt, f"Set target: {user_text}", 0.7)
        return await update.message.reply_text(response_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif current_state == "WAITING_FOR_ADD":
        sub, ch, lectures = extract_lecture_details(user_text)
        if not sub: return await update.message.reply_text("❌ ফরম্যাট ভুল!")
        
        added_names = []
        for lec in lectures:
            key = f"{sub}_{ch}_{lec}"
            if key not in user_syllabus:
                user_syllabus[key] = {"class": "Pending", "note": "Pending", "practice": "Pending", "exam": "Pending"}
                save_single_lecture_to_sheet(key)
                added_names.append(get_friendly_name(key))
                
        user_data["current_state"] = "NORMAL"
        msg = f"✅ যোগ করা হয়েছে!\n" + "\n".join([f"📎 {n}" for n in added_names]) if added_names else "⚠ লেকচার অলরেডি আছে!"
        return await update.message.reply_text(msg, reply_markup=get_main_keyboard())

    elif current_state.startswith("WAITING_FOR_"):
        sub, ch, lectures = extract_lecture_details(user_text)
        if not sub: return await update.message.reply_text("❌ ফরম্যাট ভুল!")
        task_type = current_state.split("_")[-1].lower()
        
        updated = 0
        last_name = ""
        for lec in lectures:
            key = f"{sub}_{ch}_{lec}"
            if key in user_syllabus:
                user_syllabus[key][task_type] = "Done"
                save_single_lecture_to_sheet(key)
                updated += 1
                last_name = get_friendly_name(key)
        
        user_data["current_state"] = "NORMAL"
        if updated > 0:
            return await update.message.reply_text(f"🎉 ওড়াধুড়া! **{last_name}** সহ {updated}টি লেকচারের **{task_type.upper()}** ডান!", reply_markup=get_main_keyboard())
        else:
            return await update.message.reply_text("❌ লেকচার খুঁজে পাওয়া যায়নি! আগে Add New Lecture করো।", reply_markup=get_main_keyboard())

    # নরমাল চ্যাট রাউটিং
    sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), status_str=await get_status_str(), daily_target_raw=user_data["daily_target_raw"], context_reason="Respond naturally to the user. Use Real Chapter Names. Guide them, scold them, or appreciate them based on their message and context.")
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

    print("✅ Optimized Jeetu Bhaiya AI (with Friendly Names) is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
