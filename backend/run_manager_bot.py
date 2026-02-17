"""
EyeconBumps Manager Bot Runner
Run this script to start the @EyeconBumpsBot manager bot.

Usage:
    python run_manager_bot.py
"""

import asyncio
import logging
from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters, ContextTypes
# Removed special command imports - not found in manager_bot

# Import everything from manager_bot
from manager_bot import (
    BOT_TOKEN,
    ADMIN_IDS,
    start,
    wallet_command,
    start_deposit,
    receive_deposit_amount,
    show_crypto_selection,
    show_payment_details,
    handle_wallet,
    handle_purchase_plan,
    handle_show_plans,       # New
    handle_show_bundles,     # New
    process_purchase,
    dummy_callback,
    my_orders_command,
    show_orders_list,
    handle_order_selection,
    cancel,
    show_main_menu,
    admin_panel,
    admin_stats_callback,
    admin_pending_callback,
    admin_restock_callback,
    admin_join_callback,
    admin_monitor_callback,
    admin_add_funds,
    admin_order_complete,
    admin_days,
    admin_pending_orders,
    admin_accounts,
    admin_restock,
    handle_restock_zip,
    admin_join,
    handle_join_selection,
    admin_monitor,
    admin_otp,
    admin_otp_callback,
    admin_check,
    handle_check_file,
    admin_globallinks,
    handle_global_links_input,
    admin_globalfolder,
    handle_global_folder_input,
    admin_configure,
    handle_configure_photo,
    handle_admin_text_input,
    handle_account_pagination,
    CHOOSING,
    DEPOSIT_AMOUNT,
    CRYPTO_SELECTION,
    AWAITING_JOIN_COUNT,
    AWAITING_CHECK_FILE,
    AWAITING_GLOBAL_LINKS,
    AWAITING_GLOBAL_FOLDER
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    """Set up command visibility for different users."""
    # List of commands for all users
    user_commands = [
        BotCommand("start", "Launch the interface"),
        BotCommand("wallet", "Check your wallet balance"),
        BotCommand("my_orders", "View your order history"),
    ]
    
    # List of commands for admins
    admin_commands = user_commands + [
        BotCommand("add_funds", "Admin: Add money by ID"),
        BotCommand("days", "Admin: Manage Plan Expiry"),
        BotCommand("order_complete", "Admin: Tick an order as done"),
        BotCommand("pending_orders", "Admin: See all waiting orders"),
        BotCommand("accounts", "Admin: Account stats"),
        BotCommand("restock", "Admin: Upload .session ZIP"),
        BotCommand("join", "Admin: Nuclear Join Folders"),
        BotCommand("monitor", "Admin: 24h Session Watch"),
        BotCommand("otp", "Admin: Fetch Login Code"),
        BotCommand("configure", "Admin: Bulk Setup Accounts"),
        BotCommand("check", "Admin: Validate Group Links"),
        BotCommand("globallinks", "Admin: Mass Join Links"),
        BotCommand("globalfolder", "Admin: Mass Join Folder"),
        BotCommand("special", "Admin: Special Verification"),
    ]
    
    # Set default commands (visible to everyone)
    await application.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    
    # Set custom commands for each Admin ID
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info(f"Set admin commands for {admin_id}")
        except Exception as e:
            logger.warning(f"Could not set admin commands for {admin_id}: {e}")

async def debug_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catch-all handler for debugging unhandled callbacks."""
    query = update.callback_query
    if query:
        logger.warning(f"[DEBUG] Unhandled callback: {query.data} from user {update.effective_user.id}")
        await query.answer("This button is not handled. Please /start again.", show_alert=True)

def main():
    """Run the EyeconBumps Manager Bot."""
    print("🤖 EyeconBumps Manager Bot (@EyeconBumpsBot) starting...")
    print(f"📡 Using bot token: {BOT_TOKEN[:20]}...")
    
    # Create application with post_init
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Define ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("check", admin_check),
            CommandHandler("globallinks", admin_globallinks),
            CommandHandler("globalfolder", admin_globalfolder),
            CallbackQueryHandler(show_main_menu, pattern="^back_to_start$")
        ],
        states={
            CHOOSING: [
                CallbackQueryHandler(start_deposit, pattern="^deposit_start$"),
                CallbackQueryHandler(handle_wallet, pattern="^wallet$"),
                CallbackQueryHandler(handle_purchase_plan, pattern="^purchase_plan$"),
                CallbackQueryHandler(handle_show_plans, pattern="^show_plans$"),
                CallbackQueryHandler(handle_show_bundles, pattern="^show_bundles$"),
                CallbackQueryHandler(show_main_menu, pattern="^back_to_start$"),
                CallbackQueryHandler(process_purchase, pattern="^buy_"), 
                CallbackQueryHandler(admin_panel, pattern="^admin_panel$"),
                CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"),
                CallbackQueryHandler(admin_pending_callback, pattern="^admin_pending$"),
                CallbackQueryHandler(admin_restock_callback, pattern="^admin_restock_info$"),
                CallbackQueryHandler(admin_join_callback, pattern="^admin_join_info$"),
                CallbackQueryHandler(admin_monitor_callback, pattern="^admin_monitor_info$"),
                CallbackQueryHandler(admin_otp_callback, pattern="^admin_otp_info$"),
                CommandHandler("check", admin_check),
                CommandHandler("globallinks", admin_globallinks),
                CommandHandler("globalfolder", admin_globalfolder),
            ],
            DEPOSIT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_deposit_amount),
                CallbackQueryHandler(show_main_menu, pattern="^back_to_start$")
            ],
            CRYPTO_SELECTION: [
                CallbackQueryHandler(show_payment_details, pattern="^pay_"),
                CallbackQueryHandler(show_main_menu, pattern="^back_to_start$"),
                CallbackQueryHandler(show_crypto_selection, pattern="^back_to_crypto$")
            ],
            AWAITING_CHECK_FILE: [
                MessageHandler(filters.Document.ALL & filters.Chat(ADMIN_IDS), handle_check_file),
                CallbackQueryHandler(show_main_menu, pattern="^back_to_start$")
            ],
            AWAITING_GLOBAL_LINKS: [
                MessageHandler((filters.TEXT | filters.Document.ALL) & filters.Chat(ADMIN_IDS) & ~filters.COMMAND, handle_global_links_input),
                CallbackQueryHandler(show_main_menu, pattern="^back_to_start$")
            ],
            AWAITING_GLOBAL_FOLDER: [
                MessageHandler(filters.TEXT & filters.Chat(ADMIN_IDS) & ~filters.COMMAND, handle_global_folder_input),
                CallbackQueryHandler(show_main_menu, pattern="^back_to_start$")
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )

    # Add handlers (IMPORTANT: Order matters)
    application.add_handler(conv_handler)
    
    # Standalone Command Handlers
    application.add_handler(CommandHandler("wallet", wallet_command))
    application.add_handler(CommandHandler("balance", wallet_command)) # Keep /balance as alias
    application.add_handler(CommandHandler("my_orders", my_orders_command))
    
    # Order viewing handlers (outside conversation as they are global)
    application.add_handler(CallbackQueryHandler(handle_order_selection, pattern="^view_order_"))
    application.add_handler(CallbackQueryHandler(show_orders_list, pattern="^my_orders_list$"))
    
    
    # Admin Handlers
    application.add_handler(CommandHandler("add_funds", admin_add_funds))
    application.add_handler(CommandHandler("order_complete", admin_order_complete))
    application.add_handler(CommandHandler("days", admin_days))
    application.add_handler(CommandHandler("pending_orders", admin_pending_orders))
    application.add_handler(CommandHandler("accounts", admin_accounts))
    application.add_handler(CommandHandler("restock", admin_restock))
    application.add_handler(CommandHandler("join", admin_join))
    application.add_handler(CommandHandler("monitor", admin_monitor))
    application.add_handler(CommandHandler("otp", admin_otp))
    application.add_handler(CommandHandler("configure", admin_configure))
    application.add_handler(CommandHandler("globallinks", admin_globallinks))
    application.add_handler(CommandHandler("globalfolder", admin_globalfolder))
    
    # Callback Handlers for Join selection
    application.add_handler(CallbackQueryHandler(handle_join_selection, pattern="^join_"))
    
    # Account Pagination Handler
    application.add_handler(CallbackQueryHandler(handle_account_pagination, pattern="^admin_acc_page_"))

    # Admin Text Input Handler (for interactive prompts)
    application.add_handler(MessageHandler(filters.TEXT & filters.Chat(ADMIN_IDS) & ~filters.COMMAND, handle_admin_text_input))
    
    # Admin Document Handler (for /restock ZIP)
    application.add_handler(MessageHandler(filters.Document.ALL & filters.Chat(ADMIN_IDS), handle_restock_zip))
    
    # Admin Photo Handler (for /configure PFP)
    application.add_handler(MessageHandler(filters.PHOTO & filters.Chat(ADMIN_IDS), handle_configure_photo))
    
    print("✅ Bot is running! Press Ctrl+C to stop.")
    print("💬 Send /start to @EyeconBumpsBot on Telegram to test")
    print("-" * 50)
    
    # Catch-all for debugging unhandled callbacks (MUST BE LAST)
    application.add_handler(CallbackQueryHandler(debug_callback))
    
    # Run the bot
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"❌ Bot crashed: {e}")
