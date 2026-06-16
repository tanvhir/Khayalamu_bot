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

# API Keys & Security
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")
ALLOWED_CHAT_ID = int(os.environ.get("ALLOWED_CHAT_ID", 5959341337))
OPENROUTER_MODEL = "google/gemma-4-31b-it:free"

# State & Memory
user_data = {
    "daily_target_raw": "No target set yet.",
    "current_state": "NORMAL",
    "chat_history": [],
    "kaizen_goals": "কোনো কাইজেন প্ল্যান সেট করা হয়নি।",
    "kaizen_logs": []
}
MAX_HISTORY_LENGTH = 12 
user_syllabus = {}

SUBJECT_NAMES = {"P": "PHYSICS", "C": "CHEMISTRY", "M": "MATH", "B": "BIOLOGY"}
SUBJECT_ICONS = {"P": "🧲", "C": "🧪", "M": "📐", "B": "🧬"}

# চ্যাপ্টার ডিকশনারি
CHAPTER_NAMES = {
    # Physics 1st Paper
    "P1_C1": "ভৌত জগৎ ও পরিমাপ", "P1_C2": "ভেক্টর", "P1_C3": "গতিবিদ্যা", "P1_C4": "নিউটনীয় বলবিদ্যা",
    "P1_C5": "কাজ, শক্তি ও ক্ষমতা", "P1_C6": "মহাকর্ষ ও অভিকর্ষ", "P1_C7": "পদার্থের গাঠনিক ধর্ম",
    "P1_C8": "পর্যাবৃত্ত গতি", "P1_C9": "তরঙ্গ", "P1_C10": "আদর্শ গ্যাস ও গ্যাসের গতিতত্ত্ব",
    # Physics 2nd Paper
    "P2_C1": "তাপগতিবিদ্যা", "P2_C2": "স্থির তড়িৎ", "P2_C3": "চল তড়িৎ", "P2_C4": "তড়িৎ প্রবাহের চৌম্বক ক্রিয়া ও চৌম্বকত্ব",
    "P2_C5": "তড়িৎচুম্বকীয় আবেশ ও পরিবর্তী প্রবাহ", "P2_C6": "জ্যামিতিক আলোকবিজ্ঞান", "P2_C7": "ভৌত আলোকবিজ্ঞান", "P2_C8": "আধুনিক পদার্থবিজ্ঞানের সূচনা",
    # Chemistry 1st Paper
    "C1_C1": "ল্যাবরেটরির নিরাপদ ব্যবহার", "C1_C2": "गुणগত রসায়ন", "C1_C3": "মৌলের পর্যায়বৃত্ত ধর্ম ও রাসায়নিক বন্ধন", "C1_C4": "রাসায়নিক পরিবর্তন", "C1_C5": "কর্মমুখী রসায়ন",
    # Chemistry 2nd Paper
    "C2_C1": "পরিবেশ রসায়ন", "C2_C2": "জৈব রসায়ন", "C2_C3": "পরিমাণগত রসায়ন", "C2_C4": "তড়িৎ রসায়ন", "C2_C5": "অর্থনৈতিক রসায়ন",
    # Mathematics 1st Paper
    "M1_C1": "ম্যাট্রিক্স ও নির্ণায়ক", "M1_C2": "সরলরেখা", "M1_C3": "বৃত্ত", "M1_C4": "বিন্যাস ও সমাবেশ", "M1_C5": "ত্রিকোণমিতিক অনুপাত",
    "M1_C6": "সংযুক্ত কোণের ত্রিকোণমিতিক অনুপাত", "M1_C7": "ফাংশন ও ফাংশনের লেখচিত্র", "M1_C8": "অন্তর্বর্তী ও বিপরীত ত্রিকোণমিতিক ফাংশন", "M1_C9": "অন্টারীকরণ", "M1_C10": "যোগজীকরণ",
    # Mathematics 2nd Paper
    "M2_C1": "বাস্তব সংখ্যা ও অসমতা", "M2_C2": "বহুপদী ও বহুপদী সমীকরণ", "M2_C3": "জটিল সংখ্যা", "M2_C4": "দ্বিপদী বিস্তৃতি",
    "M2_C5": "কণিক", "M2_C6": "স্থিতিবিদ্যা", "M2_C7": "সমতলে বস্তুকণার গতি", "M2_C8": "সম্ভাবনা", "M2_C9": "পরিসংখ্যান",
    # Biology 1st Paper
    "B1_C1": "কোষ ও এর গঠন", "B1_C2": "কোষ বিভাজন", "B1_C3": "কোষ রসায়ন", "B1_C4": "অণুজীব", "B1_C5": "শৈবাল ও ছত্রাক",
    "B1_C6": "ব্রায়োফাইটা ও টেরিডোফাইটা", "B1_C7": "নগ্নবীজী ও আবৃতবীজী উদ্ভিদ", "B1_C8": "টিস্যু ও টিস্যুতন্ত্র", "B1_C9": "উদ্ভিদ শারীরতত্ত্ব", "B1_C10": "উদ্ভিদ প্রজনন", "B1_C11": "জীবপ্রযুক্তি",
    # Biology 2nd Paper
    "B2_C1": "প্রাণীর বিভিন্নতা ও শ্রেণিবিন্যাস", "B2_C2": "প্রাণীর পরিচিতি", "B2_C3": "পরিপাক ও শোষণ", "B2_C4": "রক্ত ও সঞ্চালন",
    "B2_C5": "কম্পন ও শ্বসন", "B2_C6": "বর্জ্য ও নিষ্কাশন", "B2_C7": "চলন ও অঙ্গচালনা", "B2_C8": "সমন্বয় ও নিয়ন্ত্রণ",
    "B2_C9": "মানব জীবনের ধারাবাহিকতা", "B2_C10": "মানবদেহের প্রতিরক্ষা", "B2_C11": "জিনতত্ত্ব ও বিবর্তন", "B2_C12": "প্রাণীর আচরণ", "B2_C13": "জীবের পরিবেশ, বিস্তার ও সংরক্ষণ"
}

# 🚀 SYSTEM PROMPT (KAIZEN & INTELLECTUAL MENTOR ENGINE)
SYSTEM_PROMPT = """
You are 'Jeetu Bhaiya', an elite, deeply empathetic, hardcore, and practical personal AI Mentor for a Bangladeshi second-timer varsity admission candidate.

CORE PROFILE INFO & CONTEXT:
- Target Exam: Varsity Admission 2026 (Starting around December 2026).
- User Status: Second Timer (High mental pressure, needs systematic guidance, zero room for fake motivation).
- Current Backlog Status: User has around 30+ lecture backlogs. Do NOT shout or panic about all 30 backlogs in one day. Guide them to clear it step-by-step (e.g., 1 backlog per day along with daily tasks).
- User's Custom Kaizen Habits: {kaizen_goals}
- Recent Kaizen History Logs: {kaizen_logs_raw}

CORE PERSONA & RULES:
- STRICTLY speak in NATURAL, CASUAL BANGLADESHI BENGALI (তুমি/তুই mix, ভাই, শোন, প্যারা নাই, কিরে).
- NEVER use markdown formatting like asterisks (**) or hashes (#) in your response text. Keep it clean.
- Provide "Tough Love": Show deep empathy regarding the struggles of being a second timer, but strictly hold them accountable.
- Keep responses short, human-like, crisp and direct (Max 3-5 lines). No long essays.
- Act like a real human monitor. If they succeed in a Kaizen goal for multiple days (visible in logs), congratulate them and ask if they are ready to graduate or update that goal.

SECRET KAIZEN LOGGING TRIGGERS:
1. If the user reports a daily progress or check-in for their habit/routine, append this secret tag at the VERY END:
<KAIZEN_LOG>goal_name|SUCCESS or FAILURE|Brief 2-3 words note in Bengali</KAIZEN_LOG>
2. If you agree on a NEW kaizen goal/phase or wish to MODIFY/RESET a goal with the user, append this secret tag at the VERY END:
<KAIZEN_UPDATE>Summarized current active goals here in Bengali</KAIZEN_UPDATE>

CONTEXT WINDOW:
- Current Bangladesh Time: {current_time}
- Today's Target: {daily_target_raw}

INSTRUCTION:
{context_reason}
"""

def get_bd_time():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=6)

# --- Database Syncer ---
def save_memory_to_sheet():
    if not APPS_SCRIPT_URL: return
    try:
        requests.post(APPS_SCRIPT_URL, json={"chat_id": str(ALLOWED_CHAT_ID), "memory_update": True, "chat_history": user_data["chat_history"], "kaizen_goals": user_data["kaizen_goals"]}, timeout=10)
    except Exception: pass

def save_target_to_sheet():
    if not APPS_SCRIPT_URL: return
    try: requests.post(APPS_SCRIPT_URL, json={"chat_id": str(ALLOWED_CHAT_ID), "target_update": True, "target": user_data["daily_target_raw"]}, timeout=10)
    except Exception: pass

def save_single_lecture_to_sheet(lecture_key, class_val=None, note_val=None, practice_val=None, exam_val=None):
    if not APPS_SCRIPT_URL: return
    try:
        payload = {"chat_id": str(ALLOWED_CHAT_ID), "syllabus_update": True, "lecture_key": lecture_key}
        if class_val: payload["class"] = class_val
        if note_val: payload["note"] = note_val
        if practice_val: payload["practice"] = practice_val
        if exam_val: payload["exam"] = exam_val
        requests.post(APPS_SCRIPT_URL, json=payload, timeout=10)
    except Exception: pass

def log_kaizen_to_sheet(goal_name, status, log_text):
    if not APPS_SCRIPT_URL: return
    try:
        requests.post(APPS_SCRIPT_URL, json={"chat_id": str(ALLOWED_CHAT_ID), "kaizen_log_update": True, "goal_name": goal_name, "status": status, "log_text": log_text}, timeout=10)
    except Exception: pass

def load_from_google_sheet():
    global user_data, user_syllabus
    if not APPS_SCRIPT_URL: return
    try:
        res = requests.get(f"{APPS_SCRIPT_URL}?chat_id={ALLOWED_CHAT_ID}", timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get("found"):
                user_data["daily_target_raw"] = data.get("target", "No target set yet.")
                user_data["chat_history"] = data.get("chat_history", [])
                user_data["kaizen_goals"] = data.get("kaizen_goals", "কোনো কাইজেন প্ল্যান সেট করা হয়নি।")
                user_data["kaizen_logs"] = data.get("kaizen_logs", [])
                user_syllabus = data.get("syllabus", {})
                logging.info("✅ Core Sync Completed!")
    except Exception as e: logging.error(f"Load Error: {e}")

# --- Shortcode Regex Engine ---
def parse_smart_shortcode(text):
    # Matches codes like: B2 C13 L1 or b2 c2 l12 or P1 C3 or m2 c1
    clean_text = text.strip().upper().replace("_", " ")
    match = re.search(r"([PCMB])\s*([12])\s*C\s*(\d+)(?:\s*L\s*(\d+))?", clean_text)
    if not match:
        return None, None, None
    sub_type = match.group(1)
    paper = match.group(2)
    ch_num = match.group(3)
    lec_num = match.group(4)
    
    ch_key = f"{sub_type}{paper}_C{ch_num}"
    if lec_num:
        return "LECTURE", ch_key, f"L{lec_num}"
    return "CHAPTER", ch_key, None

# --- OpenRouter Interceptor ---
def generate_openrouter_chat(system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
    if not OPENROUTER_API_KEY: return "API Key Missing!"
    messages = [{"role": "system", "content": system_prompt}] + user_data["chat_history"] + [{"role": "user", "content": user_message}]
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}, json={"model": OPENROUTER_MODEL, "messages": messages, "temperature": temperature}, timeout=25)
        if res.status_code == 200:
            bot_reply = res.json()["choices"][0]["message"]["content"]
            
            # Catch Kaizen Changes
            match_up = re.search(r"<KAIZEN_UPDATE>(.*?)</KAIZEN_UPDATE>", bot_reply, re.IGNORECASE | re.DOTALL)
            if match_up:
                user_data["kaizen_goals"] = match_up.group(1).strip()
                bot_reply = re.sub(r"<KAIZEN_UPDATE>.*?</KAIZEN_UPDATE>", "", bot_reply, flags=re.IGNORECASE | re.DOTALL).strip()
            
            # Catch Log Triggers
            match_log = re.search(r"<KAIZEN_LOG>(.*?)</KAIZEN_LOG>", bot_reply, re.IGNORECASE | re.DOTALL)
            if match_log:
                try:
                    parts = match_log.group(1).strip().split("|")
                    if len(parts) >= 3:
                        threading.Thread(target=log_kaizen_to_sheet, args=(parts[0], parts[1], parts[2]), daemon=True).start()
                except Exception: pass
                bot_reply = re.sub(r"<KAIZEN_LOG>.*?</KAIZEN_LOG>", "", bot_reply, flags=re.IGNORECASE | re.DOTALL).strip()

            bot_reply = bot_reply.replace("**", "").replace("#", "").strip()
            user_data["chat_history"].extend([{"role": "user", "content": user_message}, {"role": "assistant", "content": bot_reply}])
            if len(user_data["chat_history"]) > MAX_HISTORY_LENGTH: user_data["chat_history"] = user_data["chat_history"][-MAX_HISTORY_LENGTH:]
            
            threading.Thread(target=save_memory_to_sheet, daemon=True).start()
            return bot_reply
    except Exception: pass
    return "নেটওয়ার্ক ড্রপ খাইছে ভাই! আবার একটু বল তো।"

# --- UI Layout Dashboard Formatters ---
def create_progress_bar(percentage):
    filled = int(percentage // 10)
    return f"[{'█' * filled}{'░' * (10 - filled)}] {int(percentage)}%"

async def generate_premium_status():
    tot_lec = 0; done_lec = 0
    subs = {"P": {"tot":0,"done":0,"note":"Pending","practice":"Pending","exam":"Pending"},
            "C": {"tot":0,"done":0,"note":"Pending","practice":"Pending","exam":"Pending"},
            "M": {"tot":0,"done":0,"note":"Pending","practice":"Pending","exam":"Pending"},
            "B": {"tot":0,"done":0,"note":"Pending","practice":"Pending","exam":"Pending"}}
    
    for k, s in user_syllabus.items():
        if "_CH" in k:
            sk = k.split("_")[0].upper()[0]
            if sk in subs:
                if s.get("note") == "Done": subs[sk]["note"] = "Done"
                if s.get("practice") == "Done": subs[sk]["practice"] = "Done"
                if s.get("exam") == "Done": subs[sk]["exam"] = "Done"
        else:
            sk = k.split("_")[0].upper()[0]
            if sk in subs:
                subs[sk]["tot"] += 1
                tot_lec += 1
                if s.get("class") == "Done":
                    subs[sk]["done"] += 1
                    done_lec += 1
                    
    overall_prog = (done_lec / tot_lec * 100) if tot_lec > 0 else 0
    
    msg = "Status Dashboard\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"Overall Progress: {create_progress_bar(overall_prog)}\n"
    msg += f"Total Lectures: {tot_lec}  |  Completed: {done_lec}  |  Backlog: {tot_lec - done_lec}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for sk in ["P", "C", "M", "B"]:
        d = subs[sk]
        prog = (d["done"] / d["tot"] * 100) if d["tot"] > 0 else 0
        msg += f"{SUBJECT_ICONS[sk]} {SUBJECT_NAMES[sk]}: {create_progress_bar(prog)}\n"
        msg += f"            ├── Classes ── {d['done']}/{d['tot']}\n"
        msg += f"            ├── Note: {d['note']}\n"
        msg += f"            ├── Practice: {d['practice']}\n"
        msg += f"            └── Exam: {d['exam']}\n\n"
        
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🎯 আজকের টার্গেটঃ {user_data['daily_target_raw']}\n\n"
    msg += f"🧠 কাইজেন গোলঃ {user_data['kaizen_goals']}\n"
    msg += "📊 লাস্ট ট্র্যাকিং লগঃ\n"
    
    if user_data["kaizen_logs"]:
        for log in user_data["kaizen_logs"][:4]:
            icon = "✅" if log.get("status") == "SUCCESS" else "❌"
            msg += f"  • {log.get('date')}: {log.get('goal')} -> {icon} ({log.get('text')})\n"
    else:
        msg += "  • এখনো কোনো লগ ডেটা জমা হয়নি।\n"
        
    msg += "  (জিতু ভাইয়া তোর প্যাটার্ন নজরে রাখছে!)\n"
    return msg

async def view_syllabus_tree(update: Update, context: ContextTypes.DEFAULT_TYPE, filter_arg=None):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    if not user_syllabus: return await update.message.reply_text("সিলেবাসে এখনো কিছু অ্যাড করিস নাই ভাই!")
    
    tree = {"P": {}, "C": {}, "M": {}, "B": {}}
    chapter_tasks = {}
    
    for k, s in sorted(user_syllabus.items()):
        parts = k.split("_")
        sk = parts[0][0].upper()
        ch_key = parts[0] + "_" + parts[1]
        
        if filter_arg:
            if filter_arg in ["P", "C", "M", "B"] and sk != filter_arg: continue
            if filter_arg in CHAPTER_NAMES and ch_key != filter_arg: continue
            
        if "_CH" in k:
            chapter_tasks[ch_key] = s
        else:
            lec = parts[2]
            if sk in tree:
                if ch_key not in tree[sk]: tree[sk][ch_key] = []
                tree[sk][ch_key].append((lec, s))
                
    msg = "Detailed Syllabus Report\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    has_data = False
    for sk in ["P", "C", "M", "B"]:
        if tree[sk]:
            has_data = True
            msg += f"{SUBJECT_ICONS[sk]} {SUBJECT_NAMES[sk]}\n\n"
            for ch, lecs in tree[sk].items():
                ch_name = CHAPTER_NAMES.get(ch, ch)
                ct = chapter_tasks.get(ch, {"note":"Pending","practice":"Pending","exam":"Pending"})
                
                msg += f"📁 {ch_name} ({ch.split('_')[1]})\n"
                msg += f"  ├── Note: {ct.get('note')} | Practice: {ct.get('practice')} | Exam: {ct.get('exam')}\n"
                msg += "  └── Lectures:\n"
                
                for idx, (lec, s) in enumerate(lecs):
                    connector = "└──" if idx == len(lecs) - 1 else "├──"
                    c_status = "Class Done" if s.get("class") == "Done" else "Pending"
                    msg += f"      {connector} {lec} ── {c_status}\n"
                msg += "\n"
                
    if not has_data:
        return await update.message.reply_text("এই ফিল্টারের আন্ডারে কোনো সিলেবাস ডেটা খুঁজে পাওয়া যায়নি।")
        
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "(ফিল্টার করার অপশন: /report P বা /report P1_C6)"
    await update.message.reply_text(msg)

# --- Keyboard Menus ---
def get_main_keyboard():
    return ReplyKeyboardMarkup([['Check Status', 'Set Target', 'Syllabus Report'], ['Manage Kaizen', 'Manage Syllabus']], resize_keyboard=True)

def get_syllabus_keyboard():
    return ReplyKeyboardMarkup([['Add New Lecture', 'Mark Class Done'], ['Mark Note Done', 'Mark Practice Done', 'Mark Exam Done'], ['Back to Main Menu']], resize_keyboard=True)

# --- Handler Functions ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    user_data["current_state"] = "NORMAL"
    msg = (
        "কিরে ভাই, আমি তোর মেন্টর জিতু ভাইয়া।\n\n"
        "সেকেন্ড টাইমে কিন্তু ভুল করার বা ফালতু সময় নষ্ট করার বিন্দুমাত্র সুযোগ নাই। ২০২৬ সালের ডিসেম্বরের মিশন মাথায় রেখে জান লফিয়ে পড়তে হবে।\n\n"
        "মেইন ড্যাশবোর্ড মেনু রেডি আছে, কাজ শুরু কর। প্যারামুক্তভাবে গাইড করবো তোকে।"
    )
    await update.message.reply_text(msg, reply_markup=get_main_keyboard())

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = context.args[0].upper() if context.args else None
    await view_syllabus_tree(update, context, filter_arg=arg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    text = update.message.text.strip()
    state = user_data["current_state"]

    # Main Navigation
    if text == 'Check Status': return await update.message.reply_text(await generate_premium_status())
    elif text == 'Set Target': user_data["current_state"] = "WAITING_FOR_TARGET"; return await update.message.reply_text("আজকের মিশন বা টার্গেটটা লিখে দে শুনি?")
    elif text == 'Syllabus Report': return await view_syllabus_tree(update, context)
    elif text == 'Manage Syllabus': user_data["current_state"] = "NORMAL"; return await update.message.reply_text("সিলেবাস সিস্টেম কনফিগার কর:", reply_markup=get_syllabus_keyboard())
    elif text == 'Back to Main Menu': user_data["current_state"] = "NORMAL"; return await update.message.reply_text("🔙 মূল মেনু", reply_markup=get_main_keyboard())
    
    elif text == 'Manage Kaizen':
        user_data["current_state"] = "WAITING_FOR_KAIZEN"
        return await update.message.reply_text("তোর কাইজেন গোল লাইফস্টাইল অভ্যাসটা পরিবর্তন বা যোগ করতে চাস? আমাকে ডিটেইলস বল (যেমন: সকাল ৬টায় উঠতে চাই)।")

    # Mode Handling SUB-STATES
    elif text == 'Add New Lecture': user_data["current_state"] = "WAITING_FOR_ADD"; return await update.message.reply_text("কোন লেকচারটা অ্যাড করতে চাস বল? (যেমন: P1 C6 L1)")
    elif text == 'Mark Class Done': user_data["current_state"] = "WAITING_FOR_CLASS"; return await update.message.reply_text("কোন লেকচারের ক্লাস শেষ করলি? কোড দে (যেমন: P1 C6 L1)")
    elif text == 'Mark Note Done': user_data["current_state"] = "WAITING_FOR_NOTE"; return await update.message.reply_text("কোন চ্যাপ্টারের নোট কমপ্লিট? কোড দে (যেমন: P1 C6)")
    elif text == 'Mark Practice Done': user_data["current_state"] = "WAITING_FOR_PRACTICE"; return await update.message.reply_text("কোন চ্যাপ্টারের প্র্যাকটিস ডান? কোড দে (যেমন: P1 C6)")
    elif text == 'Mark Exam Done': user_data["current_state"] = "WAITING_FOR_EXAM"; return await update.message.reply_text("কোন চ্যাপ্টারের এক্সাম ডান? কোড দে (যেমন: P1 C6)")

    # WAITING FOR TARGET STATE
    if state == "WAITING_FOR_TARGET":
        user_data["daily_target_raw"] = text; user_data["current_state"] = "NORMAL"
        save_target_to_sheet()
        logs_raw = json.dumps(user_data["kaizen_logs"][:5])
        sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=text, kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, context_reason="User has set a daily target. Motivate them in a short human-like big brother style.")
        return await update.message.reply_text(generate_openrouter_chat(sys_prompt, f"Set target: {text}", 0.7), reply_markup=get_main_keyboard())

    # WAITING FOR KAIZEN GOAL CONFIGURE STATE
    elif state == "WAITING_FOR_KAIZEN":
        user_data["current_state"] = "NORMAL"
        logs_raw = json.dumps(user_data["kaizen_logs"][:5])
        sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=user_data["daily_target_raw"], kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, context_reason="User is explicitly discussing or updating their Kaizen lifestyle habits. Interview them or process it and remember to include <KAIZEN_UPDATE> tags if a plan is made.")
        return await update.message.reply_text(generate_openrouter_chat(sys_prompt, f"Kaizen Input: {text}", 0.7), reply_markup=get_main_keyboard())

    # WAITING FOR ADD LECTURE STATE
    elif state == "WAITING_FOR_ADD":
        mode, ch_key, lec_key = parse_smart_shortcode(text)
        if not ch_key or mode != "LECTURE": return await update.message.reply_text("কোড বা ফরম্যাট ঠিক নাই ভাই! একটু চেক কর। উদাহরণ: P1 C6 L1")
        
        full_lkey = f"{ch_key}_{lec_key}"
        full_ch_main = f"{ch_key}_CH"
        
        # Add basic lecture key
        if full_lkey not in user_syllabus:
            user_syllabus[full_lkey] = {"class": "Pending"}
            save_single_lecture_to_sheet(full_lkey, class_val="Pending")
        # Ensure chapter entry exists
        if full_ch_main not in user_syllabus:
            user_syllabus[full_ch_main] = {"note": "Pending", "practice": "Pending", "exam": "Pending"}
            save_single_lecture_to_sheet(full_ch_main, note_val="Pending", practice_val="Pending", exam_val="Pending")
            
        user_data["current_state"] = "NORMAL"
        return await update.message.reply_text("সফলভাবে সিলেবাস ট্র্যাকিংয়ে যুক্ত করা হয়েছে!", reply_markup=get_main_keyboard())

    # WAITING FOR CLASS COMPLETE STATE
    elif state == "WAITING_FOR_CLASS":
        mode, ch_key, lec_key = parse_smart_shortcode(text)
        if not ch_key or mode != "LECTURE": return await update.message.reply_text("ভুল শর্টকোড! ট্রাই কর এভাবে: P1 C6 L1")
        
        full_lkey = f"{ch_key}_{lec_key}"
        if full_lkey in user_syllabus:
            user_syllabus[full_lkey]["class"] = "Done"
            save_single_lecture_to_sheet(full_lkey, class_val="Done")
            user_data["current_state"] = "NORMAL"
            return await update.message.reply_text("ক্লাস কমপ্লিট হিসেবে মার্ক করা হয়েছে!", reply_markup=get_main_keyboard())
        else:
            user_data["current_state"] = "NORMAL"
            return await update.message.reply_text("এই লেকচারটি সিলেবাসে আগে যুক্ত করা হয়নি।", reply_markup=get_main_keyboard())

    # WAITING FOR CHAPTER LEVEL TASKS (NOTE, PRACTICE, EXAM)
    elif state in ["WAITING_FOR_NOTE", "WAITING_FOR_PRACTICE", "WAITING_FOR_EXAM"]:
        mode, ch_key, _ = parse_smart_shortcode(text)
        if not ch_key: return await update.message.reply_text("ভুল চ্যাপ্টার শর্টকোড! ট্রাই কর এভাবে: P1 C6")
        
        task = state.split("_")[-1].lower() # note, practice, exam
        full_ch_main = f"{ch_key}_CH"
        
        if full_ch_main not in user_syllabus:
            user_syllabus[full_ch_main] = {"note": "Pending", "practice": "Pending", "exam": "Pending"}
            
        user_syllabus[full_ch_main][task] = "Done"
        save_single_lecture_to_sheet(full_ch_main, **{f"{task}_val": "Done"})
        user_data["current_state"] = "NORMAL"
        return await update.message.reply_text(f"চ্যাপ্টারের {task.capitalize()} সফলভাবে ডান মার্ক করা হয়েছে!", reply_markup=get_main_keyboard())

    # --- NORMAL MODE CHAT CHANNELS ---
    logs_raw = json.dumps(user_data["kaizen_logs"][:5])
    sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=user_data["daily_target_raw"], kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, context_reason="Respond organically as a mentor. Notice their current state, second-timer condition and backlog history if they mention studies or habits.")
    await update.message.reply_text(generate_openrouter_chat(sys_prompt, text, 0.7))

async def hourly_mentor_check(context: ContextTypes.DEFAULT_TYPE):
    if user_data["daily_target_raw"] == "No target set yet.": return
    logs_raw = json.dumps(user_data["kaizen_logs"][:5])
    sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=user_data["daily_target_raw"], kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, context_reason="Hourly checking routine. Give a extremely sharp 1-2 lines push toward goals.")
    try: await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=generate_openrouter_chat(sys_prompt, "[SYSTEM: RUNNING HOURLY MONITOR CHECK]", 0.8))
    except Exception: pass

def run_dummy_server():
    HTTPServer(('', int(os.environ.get("PORT", 8080))), SimpleHTTPRequestHandler).serve_forever()

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    load_from_google_sheet()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", start))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run loop background checker hourly interval
    if app.job_queue:
        app.job_queue.run_repeating(hourly_mentor_check, interval=3600, first=3600, name="hourly_tracker")
        
    print("✅ Jeetu Bhaiya AI V3 (Engine & Persona Upgraded) Running Successfully!")
    app.run_polling()

if __name__ == '__main__': main()
