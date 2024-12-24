import os
import random
import requests
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Path to your video folder
VIDEO_FOLDER = r"C:\Users\vivek\Downloads\Videos"

# Daily limit for free videos
DAILY_LIMIT = 3

# Track user limits and premium status
user_limits = {}
premium_users = set()

# NowPayments API key
NOWPAYMENTS_API_KEY = "C3FMM03-1D14YBS-KMC8475-3DH26JV"
WEBHOOK_URL = "https://yourdomain.com/payment-webhook"  # Replace with your webhook URL

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with reply keyboard."""
    chat_id = update.effective_chat.id

    # Define the reply keyboard buttons
    reply_keyboard = [["View Plan 💵", "Get Video 🍒"]]

    # Create the reply keyboard markup
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

    await context.bot.send_message(chat_id=chat_id, text="Welcome! Choose an option below:", reply_markup=reply_markup)

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a payment link for purchasing premium."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Create a payment link
    payment_data = {
        "price_amount": 99,
        "price_currency": "INR",
        "pay_currency": "BTC",  # Replace with preferred cryptocurrency
        "ipn_callback_url": WEBHOOK_URL,
        "order_id": str(user_id)  # Use user ID as the order ID
    }

    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
    }

    response = requests.post("https://api.nowpayments.io/v1/invoice", json=payment_data, headers=headers)
    if response.status_code == 200:
        payment_link = response.json()["invoice_url"]
        await context.bot.send_message(chat_id=chat_id, text=f"Pay here to unlock premium: {payment_link}")
    else:
        await context.bot.send_message(chat_id=chat_id, text="Failed to generate payment link. Please try again.")

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user replies from the reply keyboard."""
    user_text = update.message.text
    user_id = update.effective_user.id

    if user_text == "Get Video 🍒":
        await send_video(update, context, user_id)
    elif user_text == "View Plan 💵":
        await update.message.reply_text("Buy premium for 99/- using /buy command.")
    else:
        await update.message.reply_text("Please use the provided buttons.")

async def send_video(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Send a random video, prioritizing unsent videos and respecting daily limits."""
    global user_limits

    # Check if the user is a premium user
    if user_id in premium_users:
        await send_premium_video(update, context)
        return

    # Initialize user data if not present
    if user_id not in user_limits:
        user_limits[user_id] = {
            "count": 0,
            "reset_time": datetime.now(),
            "sent_videos": set()
        }

    user_data = user_limits[user_id]
    now = datetime.now()

    # Reset daily limit if the time has passed
    if now >= user_data["reset_time"]:
        user_data["count"] = 0
        user_data["reset_time"] = now + timedelta(days=1)
        user_data["sent_videos"] = set()

    # Check if daily limit is reached
    if user_data["count"] >= DAILY_LIMIT:
        remaining_time = (user_data["reset_time"] - now).seconds // 3600
        await update.message.reply_text(f"Daily limit reached! Wait {remaining_time} hours for more videos or purchase premium using /buy command.")
        return

    await send_premium_video(update, context)

async def send_premium_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send any video for premium users."""
    # Get list of videos from the folder
    try:
        video_files = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith((".mp4", ".avi", ".mkv"))]
        if not video_files:
            await update.message.reply_text("No videos found in the folder. Please check the path!")
            return
    except Exception as e:
        await update.message.reply_text(f"Error accessing video folder: {e}")
        return

    # Select a random video and send it
    selected_video = random.choice(video_files)
    video_path = os.path.join(VIDEO_FOLDER, selected_video)

    try:
        await context.bot.send_video(chat_id=update.effective_chat.id, video=open(video_path, "rb"))
    except Exception as e:
        await update.message.reply_text(f"Failed to send video: {e}")

def main():
    """Start the bot."""
    TOKEN = "YOUR_BOT_TOKEN"

    print("Bot is running... Press Ctrl+C to stop.")

    # Create the application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
