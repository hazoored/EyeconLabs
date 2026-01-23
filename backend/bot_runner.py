"""
EyeconBumps Web App - Telegram Bot Runner
Run separately from FastAPI: python bot_runner.py
"""
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

from message_collector_bot import (
    BOT_TOKEN, start, add_message_callback, view_templates_callback,
    receive_client_id, receive_message, receive_template_name, cancel,
    init_message_templates_table, WAITING_CLIENT_ID, WAITING_MESSAGE, WAITING_TEMPLATE_NAME
)


def main():
    """Run the message collector bot."""
    print("🤖 EyeconBumps Message Collector Bot starting...")
    
    # Initialize database table
    init_message_templates_table()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(add_message_callback, pattern="^add_message$"),
            CallbackQueryHandler(view_templates_callback, pattern="^view_templates$"),
        ],
        states={
            WAITING_CLIENT_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_client_id)
            ],
            WAITING_MESSAGE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_message)
            ],
            WAITING_TEMPLATE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_template_name)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
    )
    
    application.add_handler(conv_handler)
    
    print("🤖 Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
