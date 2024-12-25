import os
import random
from datetime import datetime, timedelta
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update, ReplyKeyboardMarkup
import requests
from flask import Flask, request

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 3))  # Default limit is 3 if not set
TEMP_VIDEO_PATH = os.getenv("TEMP_VIDEO_PATH", "New folder")
NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Webhook URL for Render deployment
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID")  # Your private channel ID

# Initialize Telegram Bot API
from telegram import Bot
bot = Bot(token=BOT_TOKEN)

# Ensure the temporary folder exists
os.makedirs(TEMP_VIDEO_PATH, exist_ok=True)

# Track user limits and subscriptions
user_limits = {}
user_subscriptions = {}

# Flask app for webhook
app = Flask(__name__)

# Track video IDs from private channel
video_ids = []

# Function to get video IDs from the private channel
def fetch_video_ids():
    global video_ids
    # Get the latest 100 messages from the private channel (excluding the bot's own messages)
    updates = bot.get_chat_history(chat_id=PRIVATE_CHANNEL_ID, limit=100)
    for update in updates:
        if update.video and update.from_user.id != bot.id:  # Ignore bot's own messages
            video_ids.append(update.video.file_id)

# Create a payment link
def create_payment(user_id):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "price_amount": 99,  # Price in INR
        "price_currency": "inr",
        "order_id": f"user_{user_id}_{int(datetime.now().timestamp())}",
        "order_description": "Premium Plan for 1 month",
        "success_url": f"https://t.me/<your_bot_username>",  # Replace with your bot link
        "ipn_callback_url": WEBHOOK_URL,  # Render webhook URL for payment notifications
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("invoice_url")
    else:
        print(f"Error creating payment: {response.text}")
        return None

# Handle webhook notifications
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if data.get('payment_status') == 'finished':
        order_id = data.get('order_id')
        user_id = int(order_id.split("_")[1])  # Extract user ID from order ID
        # Activate premium plan
        user_subscriptions[user_id] = datetime.now() + timedelta(days=30)  # Premium valid for 1 month
        print(f"Payment successful for user {user_id}")
    return "OK", 200

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with reply keyboard."""
    chat_id = update.effective_chat.id

    # Define the reply keyboard buttons
    reply_keyboard = [["View Plan 💵", "Get Video 🍒"]]

    # Create the reply keyboard markup
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

    await context.bot.send_message(chat_id=chat_id, text="Welcome! Choose an option below:", reply_markup=reply_markup)

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send a payment link for purchasing premium."""
    chat_id = update.effective_chat.id
    payment_url = create_payment(chat_id)
    if payment_url:
        await context.bot.send_message(chat_id=chat_id, text=f"Buy premium for ₹99 using this link: {payment_url}")
    else:
        await context.bot.send_message(chat_id=chat_id, text="Failed to generate payment link. Please try again later.")

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user replies from the reply keyboard."""
    user_text = update.message.text
    user_id = update.effective_user.id

    if user_text == "Get Video 🍒":
        await send_video(update, context, user_id)
    elif user_text == "View Plan 💵":
        await update.message.reply_text("Buy premium for ₹99 using /buy command.")
    else:
        await update.message.reply_text("Please use the provided buttons.")

async def send_video(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Send a random video from the private Telegram channel, respecting daily limits."""
    global user_limits, user_subscriptions, video_ids

    # Check if user is premium
    now = datetime.now()
    if user_id in user_subscriptions and user_subscriptions[user_id] > now:
        limit = 100  # Premium users have 100 videos per day
    else:
        limit = DAILY_LIMIT

    # Initialize user data if not present
    if user_id not in user_limits:
        user_limits[user_id] = {
            "count": 0,
            "reset_time": now,
            "sent_videos": set()
        }

    user_data = user_limits[user_id]

    # Reset daily limit if the time has passed
    if now >= user_data["reset_time"]:
        user_data["count"] = 0
        user_data["reset_time"] = now + timedelta(days=1)
        user_data["sent_videos"] = set()

    # Check if daily limit is reached
    if user_data["count"] >= limit:
        remaining_time = (user_data["reset_time"] - now).seconds // 3600
        await update.message.reply_text(f"Daily limit reached! Wait {remaining_time} hours for more videos or purchase premium using /buy command.")
        return

    # Check if there are videos available
    if not video_ids:
        await update.message.reply_text("No videos found in the private Telegram channel.")
        return

    # Select the next unsent video
    unsent_videos = [video for video in video_ids if video not in user_data["sent_videos"]]
    if not unsent_videos:
        await update.message.reply_text("All videos have been sent. Please try again tomorrow or purchase premium.")
        return

    selected_video = random.choice(unsent_videos)
    try:
        # Send the selected video from the private channel
        await context.bot.send_video(chat_id=update.effective_chat.id, video=selected_video)

        # Update user data
        user_data["count"] += 1
        user_data["sent_videos"].add(selected_video)

    except Exception as e:
        await update.message.reply_text(f"Failed to send video: {e}")

def main():
    """Start the bot."""
    print("Bot is running... Press Ctrl+C to stop.")

    # Create the application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))

    # Run the bot
    application.run_polling()

# Run the Flask app
if __name__ == "__main__":
    fetch_video_ids()  # Fetch video IDs from the private channel on bot start
    main()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
