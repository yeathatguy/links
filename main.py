import os
import random
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request, jsonify

# Flask app for handling the webhook
app = Flask(__name__)

# Path to your video folder
VIDEO_FOLDER = r"C:\Users\vivek\Downloads\Videos"

# Daily limit for free users
DAILY_LIMIT = 3

# Track user limits and sent videos
user_limits = {}

# NOWPayments API Key
NOWPAYMENTS_API_KEY = "YOUR_NOWPAYMENTS_API_KEY"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with reply keyboard."""
    chat_id = update.effective_chat.id

    # Define the reply keyboard buttons
    reply_keyboard = [["View Plan 💵", "Get Video 🍒"]]

    # Create the reply keyboard markup
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

    await context.bot.send_message(chat_id=chat_id, text="Welcome! Choose an option below:", reply_markup=reply_markup)

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message with payment details."""
    chat_id = update.effective_chat.id
    # Payment link for NOWPayments (use your API or specific link)
    payment_link = "https://nowpayments.io/payment-url"  # Replace with your generated payment URL
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Buy premium for 99/- using this link: {payment_link}. Once paid, you will get access to 100 videos/day for one month!"
    )

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

    # Initialize user data if not present
    if user_id not in user_limits:
        user_limits[user_id] = {
            "count": 0,
            "reset_time": datetime.now(),
            "sent_videos": set(),
            "premium": False  # Default to non-premium
        }

    user_data = user_limits[user_id]
    now = datetime.now()

    # Reset daily limit if the time has passed
    if now >= user_data["reset_time"]:
        user_data["count"] = 0
        user_data["reset_time"] = now + timedelta(days=1)
        user_data["sent_videos"] = set()

    # Set daily limit based on premium status
    daily_limit = 100 if user_data.get("premium", False) else DAILY_LIMIT

    # Check if daily limit is reached
    if user_data["count"] >= daily_limit:
        remaining_time = (user_data["reset_time"] - now).seconds // 3600
        await update.message.reply_text(
            f"Daily limit reached! Wait {remaining_time} hours for more videos or purchase premium using /buy command."
        )
        return

    # Get list of videos from the folder
    try:
        video_files = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith((".mp4", ".avi", ".mkv"))]
        if not video_files:
            await update.message.reply_text("No videos found in the folder. Please check the path!")
            return
    except Exception as e:
        await update.message.reply_text(f"Error accessing video folder: {e}")
        return

    # Split videos into unsent and already sent
    unsent_videos = [video for video in video_files if video not in user_data["sent_videos"]]
    sent_videos = [video for video in video_files if video in user_data["sent_videos"]]

    # Merge unsent first, followed by sent
    prioritized_videos = unsent_videos + sent_videos

    if not prioritized_videos:
        await update.message.reply_text("No videos available. Please try again later!")
        return

    # Select the next video and send it
    selected_video = prioritized_videos[0]  # Send the next video in the priority list
    video_path = os.path.join(VIDEO_FOLDER, selected_video)

    try:
        await context.bot.send_video(chat_id=update.effective_chat.id, video=open(video_path, "rb"))
        # Update user data
        user_data["count"] += 1
        user_data["sent_videos"].add(selected_video)
    except Exception as e:
        await update.message.reply_text(f"Failed to send video: {e}")

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle payment success notifications from NOWPayments."""
    global user_limits

    data = request.json
    if data.get("payment_status") == "finished":
        user_id = int(data.get("order_id"))  # Order ID is the user_id in this implementation
        if user_id in user_limits:
            user_limits[user_id]["premium"] = True
            user_limits[user_id]["reset_time"] = datetime.now() + timedelta(days=30)  # Premium valid for 30 days
            user_limits[user_id]["count"] = 0  # Reset video count
    return jsonify({"status": "success"})

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
    from threading import Thread

    # Run Flask app in a separate thread
    thread = Thread(target=lambda: app.run(host="0.0.0.0", port=5000))
    thread.start()

    # Start the bot
    main()
