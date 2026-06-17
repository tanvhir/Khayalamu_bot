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
from dotenv import load_dotenv

# এনভায়রনমেন্ট ভেরিয়েবল লোড করা
load_dotenv()

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# API Keys & Security 
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")
ALLOWED_CHAT_ID = int(os.environ.get("ALLOWED_CHAT_ID", 5959341337))
OPENROUTER_MODEL = "google/gemma-4-31b-it:free"

# State & Memory (V6 টু-টেবিল আর্কিটেকচার এলাইন্ড)
user_data = {
    "daily_target_raw": "No target set yet.",
    "current_state": "NORMAL",  # STATES: NORMAL, WAITING_FOR_TARGET, WAITING_FOR_TARGET_UPDATE, WAITING_FOR_KAIZEN, WAITING_FOR_KAIZEN_UPDATE
    "chat_history": [],
    "kaizen_goals": "কোনো কাইজেন প্ল্যান সেট করা হয়নি।",
    "kaizen_logs": []
}
MAX_HISTORY_LENGTH = 12  # [FIXED BUG]: আগের ড্রাফটে এটা গ্লোবাল স্কোপে মিসিং ছিল

# তোর ব্রিলিয়ান্ট প্ল্যান অনুযায়ী ২ টেবিল গ্লোবাল ডিকশনারি মেমোরি
user_chapters = {} # {'P1_C2': {'progress': '1/10', 'note': 'Pending', 'practice': 'Done', 'exam': 'Pending'}}
user_lectures = {} # {'P1_C2_L1': 'Done', 'P1_C2_L2': 'Pending'}

SUBJECT_NAMES = {"P": "PHYSICS", "C": "CHEMISTRY", "M": "MATH", "B": "BIOLOGY"}
SUBJECT_ICONS = {"P": "🧲", "C": "🧪", "M": "📐", "B": "🧬"}

# ৫৪ চ্যাপ্টারের পলিশ করা ডাটা ম্যাপ
CHAPTER_NAMES = {
    "P1_C1": "ভৌত জগৎ ও পরিমাপ", "P1_C2": "ভেক্টর", "P1_C3": "গতিবিদ্যা", "P1_C4": "নিউটনীয় বলবিদ্যা",
    "P1_C5": "কাজ, শক্তি ও ক্ষমতা", "P1_C6": "মহাকর্ষ ও অভিকর্ষ", "P1_C7": "পদার্থের গাঠনিক ধর্ম",
    "P1_C8": "পর্যাবৃত্ত গতি", "P1_C9": "তরঙ্গ", "P1_C10": "আదర్శ গ্যাস ও গ্যাসের গতিতত্ত্ব",
    "P2_C1": "তাপগতিবিদ্যা", "P2_C2": "স্থির তড়িৎ", "P2_C3": "চল তড়িৎ", "P2_C4": "তড়িৎ প্রবাহের চৌম্বক ক্রিয়া ও চৌম্বকত্ব",
    "P2_C5": "তড়িৎচুম্বকীয় আবেশ ও পরিবর্তী প্রবাহ", "P2_C6": "জ্যামিতিক আলোকবিজ্ঞান", "P2_C7": "ভৌত আলোকবিজ্ঞান", "P2_C8": "আধুনিক পদার্থবিজ্ঞানের সূচনা",
    "C1_C1": "ল্যাবরেটরির নিরাপদ ব্যবহার", "C1_C2": "গুণগত রসায়ন", "C1_C3": "مৌলের পর্যায়বৃত্ত ধর্ম ও রাসায়নিক বন্ধন", "C1_C4": "রাসায়নিক পরিবর্তন", "C1_C5": "কর্মমুখী রসায়ন",
    "C2_C1": "পরিবেশ রসায়ন", "C2_C2": "জৈব রসায়ন", "C2_C3": "পরিমাণগত রসায়ন", "C2_C4": "তড়িৎ রসায়ন", "C2_C5": "অর্থনৈতিক রসায়ন",
    "M1_C1": "ম্যাট্রিক্স ও নির্ণায়ক", "M1_C2": "সরলরেখা", "M1_C3": "বৃত্ত", "M1_C4": "বিন্যাস ও সমাবেশ", "M1_C5": "ত্রিকোণমিতিক অনুপাত",
    "M1_C6": "সংযুক্ত কোণের ত্রিকোণমিতিক অনুপাত", "M1_C7": "ফাংশন ও ফাংশনের লেখচিত্র", "M1_C8": "انتর্বর্তী ও বিপরীত ত্রিকোণমিতিক ফাংশন", "M1_C9": "অন্টারীকরণ", "M1_C10": "যোগজীকরণ",
    "M2_C1": "বাস্তব সংখ্যা ও অসমতা", "M2_C2": "বহুপদী ও বহুপদী সমীকরণ", "M2_C3": "জটিল সংখ্যা", "M2_C4": "দ্বিপদী বিস্তৃতি",
    "M2_C5": "কণিক", "M2_C6": "স্থিতিবিদ্যা", "M2_C7": "সমতলে বস্তুকণার গতি", "M2_C8": "সম্ভাবনা", "M2_C9": "পরিসংখ্যান",
    "B1_C1": "কোষ ও এর গঠন", "B1_C2": "কোষ বিভাজন", "B1_C3": "কোষ রসায়ন", "B1_C4": "অণুজীব", "B1_C5": "শৈবাল ও ছত্রাক",
    "B1_C6": "ব্রায়োফাইটা ও টেরিডোফাইটা", "B1_C7": "নগ্নবীজী ও আবৃতবীজী উদ্ভিদ", "B1_C8": "টিস্যু ও টিস্যুতন্ত্র", "B1_C9": "উদ্ভিদ শারীরতত্ত্ব", "B1_C10": "উদ্ভিদ প্রজনন", "B1_C11": "জীবপ্রযুক্তি",
    "B2_C1": "প্রাণীর বিভিন্নতা ও শ্রেণিবিন্যাস", "B2_C2": "প্রাণীর পরিচিতি", "B2_C3": "পরিপাক ও শোষণ", "B2_C4": "রক্ত ও সঞ্চালন",
    "B2_C5": "কম্পন ও শ্বসন", "B2_C6": "বর্জ্য ও নিষ্কাশন", "B2_C7": "চলন ও অঙ্গচালনা", "B2_C8": "সমন্বয় ও নিয়ন্ত্রণ",
    "B2_C9": "মানব জীবনের ধারাবাহিকতা", "B2_C10": "মানবدهহের প্রতিরক্ষা", "B2_C11": "জিনতত্ত্ব ও বিবর্তন", "B2_C12": "প্রাণীর আচরণ", "B2_C13": "জীবের পরিবেশ, বিস্তার ও সংরক্ষণ"
}

# জিতু ভাইয়ার ১০০% জেনুইন বাংলাদেশি পারসোনা + V6 ডাইনামিক লাইভ সামারি কনটেক্সট
SYSTEM_PROMPT = """
You are 'Jeetu Bhaiya', an elite, deeply empathetic, hardcore, and practical personal AI Mentor for a Bangladeshi second-timer varsity admission candidate.

CORE PROFILE INFO & CONTEXT:
- Target Exam: Varsity Admission 2026.
- User Status: Second Timer (High mental pressure, needs systematic guidance, zero room for fake motivation).
- LIVE PROGRESS SCENARIO: {dynamic_summary_context}
- User's Custom Kaizen Habits: {kaizen_goals}
- Recent Kaizen History Logs: {kaizen_logs_raw}

CORE PERSONA & RULES:
- STRICTLY speak in NATURAL, CASUAL BANGLADESHI BENGALI (তুমি/তুই mix, ভাই, শোন, প্যারা নাই, কিরে).
- NEVER use markdown formatting like asterisks (**) or hashes (#). Keep it clean.
- Keep responses short, human-like, crisp and direct (Max 3-5 lines). No long essays.

STRICT V4 ACTIONS INTERACTION RULES:
1. If context_reason says "PARSING_TARGET_UPDATE", evaluate if user succeeded, half-done or failed. End your reply with this tag: <TARGET_PARSE>Done or Half Done or Failed</TARGET_PARSE>
2. If context_reason says "PARSING_KAIZEN_LOG", evaluate their habit success. End your reply with this tag: <KAIZEN_LOG>goal_name|SUCCESS or FAILURE|Brief note in Bengali</KAIZEN_LOG>
3. If context_reason says "PARSING_KAIZEN_SET", finalize their new goal. End your reply with this tag: <KAIZEN_UPDATE>Summarized new active goals in Bengali</KAIZEN_UPDATE>

CONTEXT WINDOW:
- Current Bangladesh Time: {current_time}
- Today's Target: {daily_target_raw}
- Instruction Context: {context_reason}
"""

def get_bd_time():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=6)

# --- Database Syncers (V6 ২-টেবিল সামঞ্জস্যতা ব্যাকহ্যান্ড থ্রেডিং) ---
def save_memory_to_sheet():
    if not APPS_SCRIPT_URL: return
    try: requests.post(APPS_SCRIPT_URL, json={"chat_id": str(ALLOWED_CHAT_ID), "memory_update": True, "chat_history": user_data["chat_history"], "kaizen_goals": user_data["kaizen_goals"]}, timeout=10)
    except Exception: pass

def save_target_to_sheet(status="Pending"):
    if not APPS_SCRIPT_URL: return
    try: requests.post(APPS_SCRIPT_URL, json={"chat_id": str(ALLOWED_CHAT_ID), "target_update": True, "target": user_data["daily_target_raw"], "target_status": status}, timeout=10)
    except Exception: pass

def post_lecture_to_sheet(ch_key, lec_num, status="Pending"):
    if not APPS_SCRIPT_URL: return
    try:
        ch_name = CHAPTER_NAMES.get(ch_key, "")
        requests.post(APPS_SCRIPT_URL, json={"chat_id": str(ALLOWED_CHAT_ID), "syllabus_update": True, "action_type": "LECTURE_UPDATE", "chapter_key": ch_key, "chapter_name": ch_name, "lecture_num": lec_num, "class_status": status}, timeout=10)
    except Exception: pass

def post_chapter_task_to_sheet(ch_key, task_type, status="Done"):
    if not APPS_SCRIPT_URL: return
    try:
        ch_name = CHAPTER_NAMES.get(ch_key, "")
        payload = {"chat_id": str(ALLOWED_CHAT_ID), "syllabus_update": True, "action_type": "CHAPTER_UPDATE", "chapter_key": ch_key, "chapter_name": ch_name}
        payload[task_type] = status
        requests.post(APPS_SCRIPT_URL, json=payload, timeout=10)
    except Exception: pass

def log_kaizen_to_sheet(goal_name, status, log_text):
    if not APPS_SCRIPT_URL: return
    try: requests.post(APPS_SCRIPT_URL, json={"chat_id": str(ALLOWED_CHAT_ID), "kaizen_log_update": True, "goal_name": goal_name, "status": status, "log_text": log_text}, timeout=10)
    except Exception: pass

def load_from_google_sheet():
    global user_data, user_chapters, user_lectures
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
                user_chapters = data.get("chapters", {})
                user_lectures = data.get("lectures", {})
                logging.info("✅ Core Sync Completed with 2-Table Schema Layout!")
    except Exception as e: logging.error(f"Load Error: {e}")

def parse_smart_shortcode(text):
    clean_text = text.strip().upper().replace("_", " ")
    # বাল্ক রেঞ্জ ডিটেকশন লজিক (যেমন: P1 C2 L1-10)
    match_range = re.search(r"([PCMB])\s*([12])\s*C\s*(\d+)\s*L\s*(\d+)\s*-\s*(\d+)", clean_text)
    if match_range:
        sub_type, paper, ch_num, start_l, end_l = match_range.groups()
        return "RANGE", f"{sub_type}{paper}_C{ch_num}", (int(start_l), int(end_l))
        
    match = re.search(r"([PCMB])\s*([12])\s*C\s*(\d+)(?:\s*L\s*(\d+))?", clean_text)
    if not match: return None, None, None
    sub_type, paper, ch_num, lec_num = match.groups()
    ch_key = f"{sub_type}{paper}_C{ch_num}"
    if lec_num: return "LECTURE", ch_key, f"L{lec_num}"
    return "CHAPTER", ch_key, None

def get_live_summary_string():
    tot_lec = len(user_lectures)
    done_lec = sum(1 for v in user_lectures.values() if v == "Done")
    tot_ch = len(user_chapters)
    done_notes = sum(1 for v in user_chapters.values() if v.get("note") == "Done")
    return f"Syllabus Lectures Added: {tot_lec}, Completed Classes: {done_lec}, Backlogs: {tot_lec - done_lec}. Total Chapters Created: {tot_ch}, Notes Done: {done_notes}."

# --- OpenRouter AI Core Interceptor ---
def generate_openrouter_chat(system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
    if not OPENROUTER_API_KEY: return "API Key Missing!"
    messages = [{"role": "system", "content": system_prompt}] + user_data["chat_history"] + [{"role": "user", "content": user_message}]
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}, json={"model": OPENROUTER_MODEL, "messages": messages, "temperature": temperature}, timeout=25)
        if res.status_code == 200:
            bot_reply = res.json()["choices"][0]["message"]["content"]
            
            match_up = re.search(r"<KAIZEN_UPDATE>(.*?)</KAIZEN_UPDATE>", bot_reply, re.IGNORECASE | re.DOTALL)
            if match_up:
                user_data["kaizen_goals"] = match_up.group(1).strip()
                bot_reply = re.sub(r"<KAIZEN_UPDATE>.*?</KAIZEN_UPDATE>", "", bot_reply, flags=re.IGNORECASE | re.DOTALL).strip()
            
            match_log = re.search(r"<KAIZEN_LOG>(.*?)</KAIZEN_LOG>", bot_reply, re.IGNORECASE | re.DOTALL)
            if match_log:
                try:
                    parts = match_log.group(1).strip().split("|")
                    if len(parts) >= 3: threading.Thread(target=log_kaizen_to_sheet, args=(parts[0], parts[1], parts[2]), daemon=True).start()
                except Exception: pass
                bot_reply = re.sub(r"<KAIZEN_LOG>.*?</KAIZEN_LOG>", "", bot_reply, flags=re.IGNORECASE | re.DOTALL).strip()

            match_tgt = re.search(r"<TARGET_PARSE>(.*?)</TARGET_PARSE>", bot_reply, re.IGNORECASE | re.DOTALL)
            if match_tgt:
                parsed_status = match_tgt.group(1).strip()
                if parsed_status in ["Done", "Completed"]: user_data["daily_target_raw"] = "No target set yet. (কালকের মিশন সফল! 🔥)"
                threading.Thread(target=save_target_to_sheet, args=(parsed_status,), daemon=True).start()
                bot_reply = re.sub(r"<TARGET_PARSE>.*?</TARGET_PARSE>", "", bot_reply, flags=re.IGNORECASE | re.DOTALL).strip()

            bot_reply = bot_reply.replace("**", "").replace("#", "").strip()
            user_data["chat_history"].extend([{"role": "user", "content": user_message}, {"role": "assistant", "content": bot_reply}])
            if len(user_data["chat_history"]) > MAX_HISTORY_LENGTH: user_data["chat_history"] = user_data["chat_history"][-MAX_HISTORY_LENGTH:]
            
            threading.Thread(target=save_memory_to_sheet, daemon=True).start()
            return bot_reply
    except Exception: pass
    return "নেটওয়ার্ক ড্রপ খাইছে ভাই! আবার একটু বল তো।"

def create_progress_bar(percentage):
    filled = int(percentage // 10)
    return f"[{'█' * filled}{'░' * (10 - filled)}] {int(percentage)}%"

# --- UI Layout Dashboard Formatters (V6 টু-টেবিল ডাটা ড্যাশবোর্ড) ---
async def generate_premium_status():
    tot_lec = len(user_lectures)
    done_lec = sum(1 for v in user_lectures.values() if v == "Done")
    
    subs = {"P": {"tot_ch":0,"note":0,"practice":0,"exam":0,"tot_l":0,"done_l":0},
            "C": {"tot_ch":0,"note":0,"practice":0,"exam":0,"tot_l":0,"done_l":0},
            "M": {"tot_ch":0,"note":0,"practice":0,"exam":0,"tot_l":0,"done_l":0},
            "B": {"tot_ch":0,"note":0,"practice":0,"exam":0,"tot_l":0,"done_l":0}}
            
    # লেকচার থেকে সাবজেক্ট সামারি কাউন্ট
    for k, v in user_lectures.items():
        sk = k.split("_")[0][0]
        if sk in subs:
            subs[sk]["tot_l"] += 1
            if v == "Done": subs[sk]["done_l"] += 1
            
    # চ্যাপ্টার শিট থেকে চ্যাপ্টার লেভেল গোল সামারি কাউন্ট
    for ck, info in user_chapters.items():
        sk = ck.split("_")[0][0]
        if sk in subs:
            subs[sk]["tot_ch"] += 1
            if info.get("note") == "Done": subs[sk]["note"] += 1
            if info.get("practice") == "Done": subs[sk]["practice"] += 1
            if info.get("exam") == "Done": subs[sk]["exam"] += 1
                    
    overall_prog = (done_lec / tot_lec * 100) if tot_lec > 0 else 0
    
    msg = "Status Dashboard\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"Overall Progress: {create_progress_bar(overall_prog)}\n"
    msg += f"Total Lectures: {tot_lec}  |  Completed: {done_lec}  |  Backlog: {tot_lec - done_lec}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for sk in ["P", "C", "M", "B"]:
        d = subs[sk]
        prog = (d["done_l"] / d["tot_l"] * 100) if d["tot_l"] > 0 else 0
        msg += f"{SUBJECT_ICONS[sk]} {SUBJECT_NAMES[sk]}: {create_progress_bar(prog)}\n"
        msg += f"            ├── Classes ── {d['done_l']}/{d['tot_l']}\n"
        msg += f"            ├── Note: {d['note']}/{d['tot_ch']}\n"
        msg += f"            ├── Practice: {d['practice']}/{d['tot_ch']}\n"
        msg += f"            └── Exam: {d['exam']}/{d['tot_ch']}\n\n"
        
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🎯 আজকের টার্গেটঃ {user_data['daily_target_raw']}\n\n"
    msg += f"🧠 কাইজেন গোলঃ {user_data['kaizen_goals']}\n"
    msg += "📊 লাস্ট ট্র্যাকিং লগঃ\n"
    
    if user_data["kaizen_logs"]:
        for log in user_data["kaizen_logs"][:4]:
            icon = "✅" if log.get("status") == "SUCCESS" else "❌"
            msg += f"  • {log.get('date')}: {log.get('goal')} -> {icon} ({log.get('text')})\n"
    else:
        msg += "  • এখনো কোনো লগ ডেটা জমা হয়নি।\n"
    msg += "  (জিতু ভাইয়া তোর প্যাটার্ন নজরে রাখছে!)\n"
    return msg

async def view_syllabus_tree(update: Update, context: ContextTypes.DEFAULT_TYPE, filter_arg=None):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    if not user_chapters and not user_lectures: return await update.message.reply_text("সিলেবাসে কোনো ডেটা নাই ভাই!")
    
    tree = {"P": {}, "C": {}, "M": {}, "B": {}}
    for ck, info in sorted(user_chapters.items()):
        sk = ck.split("_")[0][0]
        if filter_arg and filter_arg in ["P", "C", "M", "B"] and sk != filter_arg: continue
        if filter_arg and filter_arg in CHAPTER_NAMES and ck != filter_arg: continue
        if sk in tree: tree[sk][ck] = {"info": info, "lecs": []}
        
    for lk, stat in sorted(user_lectures.items()):
        parts = lk.split("_")
        ck = parts[0] + "_" + parts[1]
        sk = parts[0][0]
        if sk in tree and ck in tree[sk]:
            tree[sk][ck]["lecs"].append((parts[2], stat))
            
    msg = "Detailed Syllabus Report\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    has_data = False
    
    for sk in ["P", "C", "M", "B"]:
        if tree[sk]:
            has_data = True
            msg += f"{SUBJECT_ICONS[sk]} {SUBJECT_NAMES[sk]}\n\n"
            for ck, obj in tree[sk].items():
                ch_name = CHAPTER_NAMES.get(ck, ck)
                info = obj["info"]
                msg += f"📁 {ch_name} ({ck.split('_')[1]}) -> [Progress: {info.get('progress','0/0')}]\n"
                msg += f"  ├── Note: {info.get('note','Pending')} | Practice: {info.get('practice','Pending')} | Exam: {info.get('exam','Pending')}\n"
                msg += "  └── Lectures:\n"
                for idx, (l_num, stat) in enumerate(obj["lecs"]):
                    connector = "└──" if idx == len(obj["lecs"]) - 1 else "├──"
                    msg += f"      {connector} {l_num} ── {'Class Done' if stat=='Done' else 'Pending'}\n"
                msg += "\n"
                
    if not has_data: return await update.message.reply_text("কোনো সিলেবাস ডেটা খুঁজে পাওয়া যায়নি।")
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    await update.message.reply_text(msg)

# --- Keyboard Menus ---
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ['Check Status', 'Set Target', 'Update Target'],
        ['Manage Kaizen', 'Update Kaizen', 'Syllabus Report'],
        ['Manage Syllabus']
    ], resize_keyboard=True)

def get_syllabus_keyboard():
    return ReplyKeyboardMarkup([
        ['Add New Lecture', 'Mark Class Done'],
        ['Mark Note Done', 'Mark Practice Done', 'Mark Exam Done'],
        ['Back to Main Menu']
    ], resize_keyboard=True)

# --- Handler Functions ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    user_data["current_state"] = "NORMAL"
    msg = "কিরে ভাই, আমি তোর মেন্টর জিতু ভাইয়া। নতুন ২-টেবিল সুপার আর্কিটেকচার ডেটাবেজ এখন লাইভ রানিং! কাজ শুরু কর।"
    await update.message.reply_text(msg, reply_markup=get_main_keyboard())

async def chapters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    msg = "📖 সিলেবাস কোড ডিকশনারী ম্যাপ\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    current_sub = ""
    for k, v in sorted(CHAPTER_NAMES.items()):
        sub_prefix = k.split("_")[0]
        if sub_prefix != current_sub:
            current_sub = sub_prefix
            msg += f"\n{SUBJECT_ICONS.get(current_sub[0], '📚')} {SUBJECT_NAMES.get(current_sub[0], current_sub)} ({current_sub})\n"
        msg += f"  • {k} -> {v}\n"
    await update.message.reply_text(msg)

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = context.args[0].upper() if context.args else None
    await view_syllabus_tree(update, context, filter_arg=arg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    text = update.message.text.strip()
    state = user_data["current_state"]

    if text == 'Check Status': return await update.message.reply_text(await generate_premium_status())
    elif text == 'Syllabus Report': return await view_syllabus_tree(update, context)
    elif text == 'Manage Syllabus': user_data["current_state"] = "NORMAL"; return await update.message.reply_text("সিলেবাসシステム কনফিগার কর:", reply_markup=get_syllabus_keyboard())
    elif text == 'Back to Main Menu': user_data["current_state"] = "NORMAL"; return await update.message.reply_text("🔙 মূল মেনু", reply_markup=get_main_keyboard())
    
    elif text == 'Set Target': user_data["current_state"] = "WAITING_FOR_TARGET"; return await update.message.reply_text("আজকের মিশন বা টার্গেটটা লিখে দে শুনি?")
    elif text == 'Update Target': user_data["current_state"] = "WAITING_FOR_TARGET_UPDATE"; return await update.message.reply_text("তোর আজকের টার্গেট কি শেষ করেছিস নাকি আংশিক হয়েছে? ক্যাজুয়ালি বল।")
    elif text == 'Manage Kaizen': user_data["current_state"] = "WAITING_FOR_KAIZEN"; return await update.message.reply_text("তোর নতুন কাইজেন গোল লাইফস্টাইল অভ্যাসটা কী সেট করতে চাস বল?")
    elif text == 'Update Kaizen': user_data["current_state"] = "WAITING_FOR_KAIZEN_UPDATE"; return await update.message.reply_text("কালকের কাইজেন গোলের অবস্থা বল, সফল নাকি ব্যর্থ? কী হয়েছিল খুলে বল।")

    elif text == 'Add New Lecture': user_data["current_state"] = "WAITING_FOR_ADD"; return await update.message.reply_text("কোন লেকচারটা অ্যাড করতে চাস বল? রেঞ্জও দিতে পারিস (যেমন: P1 C2 L1 বা P1 C2 L1-10)")
    elif text == 'Mark Class Done': user_data["current_state"] = "WAITING_FOR_CLASS"; return await update.message.reply_text("কোন লেকচারের ক্লাস শেষ করলি? কোড দে (যেমন: P1 C2 L1)")
    elif text == 'Mark Note Done': user_data["current_state"] = "WAITING_FOR_NOTE"; return await update.message.reply_text("কোন চ্যাপ্টারের নোট কমপ্লিট? কোড দে (যেমন: P1 C2)")
    elif text == 'Mark Practice Done': user_data["current_state"] = "WAITING_FOR_PRACTICE"; return await update.message.reply_text("কোন চ্যাপ্টারের প্র্যাকটিস ডান? কোড দে (যেমন: P1 C2)")
    elif text == 'Mark Exam Done': user_data["current_state"] = "WAITING_FOR_EXAM"; return await update.message.reply_text("কোন চ্যাপ্টারের এক্সাম ডান? কোড দে (যেমন: P1 C2)")

    # ------------------ EXECUTE ONE-TIME LOCKED STATES ------------------
    if state == "WAITING_FOR_TARGET":
        user_data["daily_target_raw"] = text; user_data["current_state"] = "NORMAL"
        save_target_to_sheet("Pending")
        logs_raw = json.dumps(user_data["kaizen_logs"][:5])
        sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=text, kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, dynamic_summary_context=get_live_summary_string(), context_reason="User has set a daily target.")
        return await update.message.reply_text(generate_openrouter_chat(sys_prompt, f"Set target: {text}", 0.7), reply_markup=get_main_keyboard())

    elif state == "WAITING_FOR_TARGET_UPDATE":
        user_data["current_state"] = "NORMAL"
        logs_raw = json.dumps(user_data["kaizen_logs"][:5])
        sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=user_data["daily_target_raw"], kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, dynamic_summary_context=get_live_summary_string(), context_reason="PARSING_TARGET_UPDATE")
        return await update.message.reply_text(generate_openrouter_chat(sys_prompt, text, 0.5), reply_markup=get_main_keyboard())

    elif state == "WAITING_FOR_KAIZEN":
        user_data["current_state"] = "NORMAL"
        logs_raw = json.dumps(user_data["kaizen_logs"][:5])
        sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=user_data["daily_target_raw"], kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, dynamic_summary_context=get_live_summary_string(), context_reason="PARSING_KAIZEN_SET")
        return await update.message.reply_text(generate_openrouter_chat(sys_prompt, f"New Goal Setup: {text}", 0.7), reply_markup=get_main_keyboard())

    elif state == "WAITING_FOR_KAIZEN_UPDATE":
        user_data["current_state"] = "NORMAL"
        logs_raw = json.dumps(user_data["kaizen_logs"][:5])
        sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=user_data["daily_target_raw"], kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, dynamic_summary_context=get_live_summary_string(), context_reason="PARSING_KAIZEN_LOG")
        return await update.message.reply_text(generate_openrouter_chat(sys_prompt, text, 0.5), reply_markup=get_main_keyboard())

    # নতুন ২-টেবিল ডেটা রাইট সাব-স্টেট ইঞ্জিন
    elif state == "WAITING_FOR_ADD":
        mode, ch_key, lec_info = parse_smart_shortcode(text)
        if not ch_key: return await update.message.reply_text("কোড ঠিক নাই ভাই! উদাহরণ: P1 C2 L1 বা P1 C2 L1-10")
        
        if ch_key not in user_chapters: user_chapters[ch_key] = {"progress": "0/0", "note": "Pending", "practice": "Pending", "exam": "Pending"}
        
        if mode == "RANGE":
            start_l, end_l = lec_info
            for i in range(start_l, end_l + 1):
                user_lectures[f"{ch_key}_L{i}"] = "Pending"
                post_lecture_to_sheet(ch_key, f"L{i}", "Pending")
            user_data["current_state"] = "NORMAL"; return await update.message.reply_text(f"চ্যাপ্টারে L{start_l} থেকে L{end_l} বাল্ক লেকচার অ্যাড করা হয়েছে!", reply_markup=get_main_keyboard())
        elif mode == "LECTURE":
            user_lectures[f"{ch_key}_{lec_info}"] = "Pending"
            post_lecture_to_sheet(ch_key, lec_info, "Pending")
            user_data["current_state"] = "NORMAL"; return await update.message.reply_text(f"সিলেবাসে {ch_key} এর {lec_info} অ্যাড করা হয়েছে!", reply_markup=get_main_keyboard())
        else: return await update.message.reply_text("লেকচার নাম্বার বা রেঞ্জ উল্লেখ কর ভাই!")

    elif state == "WAITING_FOR_CLASS":
        mode, ch_key, lec_key = parse_smart_shortcode(text)
        if not ch_key or mode != "LECTURE": return await update.message.reply_text("ভুল শর্টকোড! ট্রাই কর এভাবে: P1 C2 L1")
        full_lkey = f"{ch_key}_{lec_key}"
        user_lectures[full_lkey] = "Done"
        
        tot = sum(1 for k in user_lectures.keys() if k.startswith(ch_key+"_"))
        dn = sum(1 for k, v in user_lectures.items() if k.startswith(ch_key+"_") and v == "Done")
        if ch_key in user_chapters: user_chapters[ch_key]["progress"] = f"{dn}/{tot}"
        
        post_lecture_to_sheet(ch_key, lec_key, "Done")
        user_data["current_state"] = "NORMAL"; return await update.message.reply_text("লেকচার ক্লাস কমপ্লিট মার্ক করা হয়েছে!", reply_markup=get_main_keyboard())

    elif state in ["WAITING_FOR_NOTE", "WAITING_FOR_PRACTICE", "WAITING_FOR_EXAM"]:
        mode, ch_key, _ = parse_smart_shortcode(text)
        if not ch_key: return await update.message.reply_text("ভুল চ্যাপ্টার শর্টকোড! ট্রাই কর এভাবে: P1 C2")
        task = state.split("_")[-1].lower()
        
        if ch_key not in user_chapters: user_chapters[ch_key] = {"progress": "0/0", "note": "Pending", "practice": "Pending", "exam": "Pending"}
        user_chapters[ch_key][task] = "Done"
        
        post_chapter_task_to_sheet(ch_key, task, "Done")
        user_data["current_state"] = "NORMAL"; return await update.message.reply_text(f"চ্যাপ্টারের {task.capitalize()} সফলভাবে ডান মার্ক করা হয়েছে!", reply_markup=get_main_keyboard())

    # ------------------ NORMAL CHAT MODE ------------------
    logs_raw = json.dumps(user_data["kaizen_logs"][:5])
    sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=user_data["daily_target_raw"], kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, dynamic_summary_context=get_live_summary_string(), context_reason="Respond organically as a mentor.")
    await update.message.reply_text(generate_openrouter_chat(sys_prompt, text, 0.7))

# --- Hourly Smart Reminder Engine ---
async def hourly_mentor_check(context: ContextTypes.DEFAULT_TYPE):
    if user_data["daily_target_raw"] == "No target set yet." or "mission successful" in user_data["daily_target_raw"].lower(): return
    current_hour = get_bd_time().hour
    if current_hour >= 0 and current_hour < 6: return
    logs_raw = json.dumps(user_data["kaizen_logs"][:5])
    sys_prompt = SYSTEM_PROMPT.format(current_time=get_bd_time().strftime("%I:%M %p"), daily_target_raw=user_data["daily_target_raw"], kaizen_goals=user_data["kaizen_goals"], kaizen_logs_raw=logs_raw, dynamic_summary_context=get_live_summary_string(), context_reason="Hourly checking routine.")
    try: await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=generate_openrouter_chat(sys_prompt, "[SYSTEM: RUNNING HOURLY MONITOR CHECK]", 0.8))
    except Exception: pass

def run_dummy_server(): HTTPServer(('', int(os.environ.get("PORT", 8080))), SimpleHTTPRequestHandler).serve_forever()

def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    load_from_google_sheet()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", start))
    app.add_handler(CommandHandler("chapters", chapters_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    if app.job_queue: app.job_queue.run_repeating(hourly_mentor_check, interval=3600, first=3600, name="hourly_tracker")
    print("✅ Jeetu Bhaiya AI V6 (Two-Table Architecture Clean Edition) Running Successfully!")
    app.run_polling()

if __name__ == '__main__': main()
