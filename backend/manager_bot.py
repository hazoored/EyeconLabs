"""
EyeconBumps Manager Bot - @EyeconBumpsBot
Handles bot management commands and provides interface for campaign control.
"""

import os
import asyncio
import json
import logging
import random
import string
from datetime import datetime, timedelta
import zipfile
import tempfile
import shutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

# Telethon imports for session management
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError,
    UserDeactivatedError, AuthKeyUnregisteredError
)

# Import database and settings
from database import Database
from config import settings

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment
BOT_TOKEN = os.getenv("MANAGER_BOT_TOKEN", "7952018847:AAHsCvGPxxgUT4F9rC4dbnj2FHbk03Z_byA")

# Banner image paths
BANNER_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "banner.jpg")
PLANS_IMAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "14.jpg")
DEPOSIT_IMAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "depo.jpg")
WALLET_IMAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "wallet.jpg")

# Initialize database using production path from settings
db = Database(os.getenv("DATABASE_PATH", settings.DATABASE_PATH))

# Admin IDs
ADMIN_IDS = [6926297956, 6415230806]

# Telegram API credentials for Telethon
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")

# Plan Prices
PLAN_PRICES = {
    "buy_bronze": {"name": "Bronze Bundle", "price": 9.99},
    "buy_gold": {"name": "Gold Bundle", "price": 49.99},
    "buy_premium": {"name": "Premium Bundle", "price": 119.99},
    "buy_amber": {"name": "Amber Bundle", "price": 39.99},
    "buy_copper": {"name": "Copper Bundle", "price": 89.99},
    "buy_obsidian": {"name": "Obsidian Bundle", "price": 199.99}
}

# Conversation states
CHOOSING, DEPOSIT_AMOUNT, CRYPTO_SELECTION, AWAITING_JOIN_COUNT, AWAITING_CHECK_FILE, AWAITING_GLOBAL_LINKS, AWAITING_GLOBAL_FOLDER = range(7)

ACCOUNTS_PER_PAGE = 50

def get_account_list_page(accounts, page, command_name, title_prefix):
    """Generate text and keyboard for a page of accounts."""
    start_idx = (page - 1) * ACCOUNTS_PER_PAGE
    end_idx = start_idx + ACCOUNTS_PER_PAGE
    page_accounts = accounts[start_idx:end_idx]
    total_pages = (len(accounts) + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE

    msg = f"<b>{title_prefix}: Account Selection (Page {page}/{total_pages})</b>\n\n"
    msg += f"Select accounts by sending their <b>numbers</b> (e.g. <code>1 2 5</code>) or type <code>global</code> to use all active accounts.\n\n"

    for idx, acc in enumerate(page_accounts, start_idx + 1):
        premium = "👑" if acc.get('is_premium') else "▫️"
        
        # Check account status properly
        status_emoji = "✅"  # Default to active
        status_text = "Active"
        
        # Check if account is actually valid
        is_active = acc.get('is_active', 1)
        if not is_active:
            status_emoji = "❌"
            status_text = "Invalid/Expired"
        elif acc.get('restricted_until'):
            try:
                from datetime import datetime
                # Handle potential space or T in ISO format
                res_str = acc['restricted_until']
                if ' ' in res_str: res_str = res_str.replace(' ', 'T')
                restricted_until = datetime.fromisoformat(res_str)
                if restricted_until > datetime.now():
                    status_emoji = "🚫"
                    status_text = "Restricted"
            except:
                pass
        
        phone = acc['phone_number']
        display = acc.get('display_name') or "No Name"
        username = acc.get('telegram_username') or "No Username"
        
        msg += f"{idx}. {status_emoji} {premium} <code>+{phone}</code> - {display}\n"
        msg += f"    └─ @{username} | {status_text}\n\n"

    keyboard = []
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_acc_page_{command_name}_{page-1}"))
    if end_idx < len(accounts):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_acc_page_{command_name}_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    return msg, InlineKeyboardMarkup(keyboard)

async def handle_account_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination buttons for account lists."""
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    # admin_acc_page_{command_name}_{page}
    command_name = data[3]
    page = int(data[4])

    mapping_key = f"{command_name}_mapping"
    mapping = context.user_data.get(mapping_key, {})
    
    # We need to reconstruct the simplified account list for display from the mapping
    # Since the mapping is {idx: id}, we can fetch or rebuild a list.
    # To keep it simple, let's just fetch all accounts again as they are sorted by ID usually.
    accounts = db.get_all_accounts_summary()
    
    titles = {
        "join": "Bulk Join & Nuclear Wipe",
        "otp": "OTP Retrieval",
        "monitor": "Session Monitor",
        "configure": "Bulk Configuration"
    }
    title = titles.get(command_name, "Account Selection")

    msg, reply_markup = get_account_list_page(accounts, page, command_name, title)
    await query.edit_message_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

DEFAULT_JOIN_LINKS = [
    "https://t.me/addlist/myTx-Y8XkFxmNmRk",
    "https://t.me/addlist/z151epfV7IRhZjQ0",
    "https://t.me/addlist/RoqUaVNNAOo1ZGI0",
    "https://t.me/addlist/pqmMO4ujGohkNGM0",
    "https://t.me/addlist/lddn33GV8rJjZTg0",
    "https://t.me/addlist/AU0B0AL0UVhlZDc0",
    "https://t.me/addlist/IhB6Vll8olA3Yjdk",
    "https://t.me/addlist/_htIPOPdhv8yMzU8",
    "https://t.me/addlist/HtYA2ZXs2k44NWM0",
    "https://t.me/addlist/08o5cX8D22pjOGY0",
    "https://t.me/addlist/w-NXajaXK3NkZDI0",
    "https://t.me/addlist/OaQofEv1dos4MWU0",
    "https://t.me/addlist/c8os_V_BJVo5Nzhk",
    "https://t.me/addlist/JC_cD1R7ibYwZmI0",
    "https://t.me/addlist/QWI8F3wV5Ok2YjJk",
    "https://t.me/addlist/MLYSiwlZ7uU5NzM1",
    "https://t.me/addlist/In__y5M3f-hhYWE1",
    "https://t.me/addlist/aRtYnq1CSL42NTM0",
    "https://t.me/addlist/2r-oeCI0E-FiNTg0",
    "https://t.me/addlist/QlgDHVRRo21jMTE0",
    "https://t.me/addlist/KedMVZMhcnBmYmJk",
    "https://t.me/addlist/uqkQLkmqHeI1MTZk",
    "https://t.me/addlist/7gkl4lRYEtNmMjk0",
    "https://t.me/addlist/db7XGRc0JPZhNmNk",
    "https://t.me/addlist/2fHSP9aB-Ck4MTc0",
    "https://t.me/addlist/6xZiJrhtLPs2MWY0",
    "https://t.me/addlist/wRrLc8l31iI4MDQ0",
    "https://t.me/addlist/_at1nLRF6ABjYjc1"
]

# Load Crypto Addresses
def load_addresses():
    try:
        json_path = os.path.join(os.path.dirname(__file__), 'addy.json')
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading addy.json: {e}")
        return {}

CRYPTO_ADDRESSES = load_addresses()

def ensure_user_registered(user):
    """Ensure user exists in prospects table (not clients - only paying users are clients)."""
    telegram_id = user.id
    
    try:
        # Check if already a paying client
        client_row = db.get_client_by_telegram_id(telegram_id)
        if client_row:
            # User is already a client, update name if needed
            current_name = client_row['name']
            if current_name.startswith("User_") and user.full_name and not user.full_name.startswith("User_"):
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE clients SET name = ? WHERE telegram_id = ?", (user.full_name, telegram_id))
                        logger.info(f"Updated client name for {telegram_id} to {user.full_name}")
                except Exception as e:
                    logger.error(f"Error updating client name for {telegram_id}: {e}")
            return
        
        # Check if exists as prospect
        prospect_row = db.get_prospect_by_telegram_id(telegram_id)
        
        if not prospect_row:
            # Register as new prospect
            logger.info(f"Registering new prospect: {telegram_id}")
            db.create_prospect(
                telegram_id=telegram_id,
                telegram_username=user.username,
                name=user.full_name or f"User_{telegram_id}"
            )
        else:
                logger.info(f"Updated prospect name for {telegram_id} to {user.full_name}")
                
    except Exception as e:
        logger.error(f"Error in ensure_user_registered for {telegram_id}: {e}")

def get_user_balance(telegram_id: int) -> float:
    """Get user's balance from database by telegram_id (checks both clients and prospects)."""
    try:
        # First check if they're a client
        client = db.get_client_by_telegram_id(telegram_id)
        if client:
            return float(client.get('balance', 0.0) or 0.0)
        
        # Otherwise check prospects
        prospect = db.get_prospect_by_telegram_id(telegram_id)
        if prospect:
            return float(prospect.get('balance', 0.0) or 0.0)
        
        return 0.0
    except Exception as e:
        logger.error(f"Error fetching balance for user {telegram_id}: {e}")
        return 0.0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    ensure_user_registered(user)
    
    context.user_data['user_name'] = user.first_name or user.username or "there"
    return await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the main menu."""
    user = update.effective_user
    user_name = context.user_data.get('user_name', user.first_name or "there")
    user_name = user_name.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
    
    # Get balance
    balance = get_user_balance(user.id)
    
    msg = (
        f"<b>Welcome to @EyeconBumpsBot, {user_name}!</b>\n\n"
        f"<b>@EyeconBumps is the #1 fully automated Telegram advertising service—engineered for people who want results now, not excuses later. "
        f"Launch ads in seconds. Edit campaigns instantly. Scale to thousands of real users without lifting a finger.</b>\n\n"
        f"<b><u>This is not \"another service.\"</u></b>\n"
        f"<b><u>This is the system serious advertisers use to win.</u></b>\n\n"
        f"<tg-spoiler>If you're ready to flood Telegram with visibility, @EyeconBumps is the only move that makes sense.</tg-spoiler>\n\n"
        f"<a href=\"https://t.me/jaalebis\">Support</a> — <a href=\"https://eyeconlabs.com/terms-conditions.html\">Terms of Service</a>\n\n"
        f"Choose an option below:"
    )
    
    keyboard = [
        [InlineKeyboardButton("Open App", url="https://app.eyeconlabs.com/")],
        [InlineKeyboardButton("Purchase a Plan", callback_data="purchase_plan")],
        [
            InlineKeyboardButton("Deposit", callback_data="deposit_start"),
            InlineKeyboardButton("Wallet", callback_data="wallet")
        ],
        [InlineKeyboardButton("Support", url="https://t.me/jaalebis")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=open(BANNER_PATH, 'rb'),
                    caption=msg,
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=reply_markup
            )
        except Exception:
            await query.edit_message_caption(caption=msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return CHOOSING
    else:
        try:
            with open(BANNER_PATH, 'rb') as banner:
                await update.message.reply_photo(
                    photo=banner,
                    caption=msg,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
        except FileNotFoundError:
            await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return CHOOSING


async def start_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the deposit flow: ask for amount."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    
    message = (
        f"<b>Deposit</b>\n\n"
        f"<b>Balance Deposit</b>\n"
        f"<b>Current Balance:</b> ${balance:.2f}\n\n"
        f"How much would you like to deposit? (USD)"
    )
    
    keyboard = [[InlineKeyboardButton("Cancel", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=open(DEPOSIT_IMAGE_PATH, 'rb'),
                caption=message,
                parse_mode=ParseMode.HTML
            ),
            reply_markup=reply_markup
        )
    except Exception:
        await query.edit_message_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    context.user_data['deposit_message_id'] = query.message.message_id
    context.user_data['chat_id'] = query.message.chat_id
    
    return DEPOSIT_AMOUNT


async def receive_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the amount entered by user."""
    text = update.message.text.strip().replace('$', '')
    
    try:
        await update.message.delete()
    except:
        pass

    try:
        amount = float(text)
        if amount <= 0:
            return DEPOSIT_AMOUNT
            
        context.user_data['deposit_amount'] = amount
        return await show_crypto_selection(update, context)
        
    except ValueError:
        return DEPOSIT_AMOUNT


async def show_crypto_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the crypto selection grid."""
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    amount = context.user_data.get('deposit_amount', 0.0)
    
    message = (
        f"<b>Deposit</b>\n\n"
        f"<b>Balance Deposit</b>\n"
        f"<b>Current Balance:</b> ${balance:.2f}\n"
        f"<b>Deposit Amount:</b> ${amount:.2f}\n\n"
        f"Select a payment method below"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("BTC", callback_data="pay_BTC"),
            InlineKeyboardButton("LTC", callback_data="pay_LTC"),
            InlineKeyboardButton("ETH", callback_data="pay_ETH")
        ],
        [
            InlineKeyboardButton("SOL", callback_data="pay_SOL"),
            InlineKeyboardButton("TON", callback_data="pay_TON"),
            InlineKeyboardButton("BNB", callback_data="pay_BNB")
        ],
        [
            InlineKeyboardButton("TRX", callback_data="pay_TRX"),
            InlineKeyboardButton("DOGE", callback_data="pay_DOGE"),
            InlineKeyboardButton("USDC (SOL)", callback_data="pay_USDC (SOL)")
        ],
        [
            InlineKeyboardButton("USDC (BSC)", callback_data="pay_USDC (BSC)"),
            InlineKeyboardButton("DAI (ETH)", callback_data="pay_DAI (ETH)"),
            InlineKeyboardButton("USDT (TRX)", callback_data="pay_USDT (TRX)")
        ],
        [
            InlineKeyboardButton("USDT (ETH)", callback_data="pay_USDT (ETH)"),
            InlineKeyboardButton("USDT (SOL)", callback_data="pay_USDT (SOL)"),
            InlineKeyboardButton("USDT (BSC)", callback_data="pay_USDT (BSC)")
        ],
        [
            InlineKeyboardButton("Binance ID (Recommended)", callback_data="pay_BINANCE")
        ],
        [
            InlineKeyboardButton("Support", url="https://t.me/jaalebis"),
            InlineKeyboardButton("Back to Menu", callback_data="back_to_start")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(open(DEPOSIT_IMAGE_PATH, 'rb'), caption=message, parse_mode=ParseMode.HTML),
                reply_markup=reply_markup
            )
        except Exception:
            await query.edit_message_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        chat_id = context.user_data.get('chat_id')
        msg_id = context.user_data.get('deposit_message_id')
        if chat_id and msg_id:
            try:
                await context.bot.edit_message_media(
                    chat_id=chat_id, message_id=msg_id,
                    media=InputMediaPhoto(open(DEPOSIT_IMAGE_PATH, 'rb'), caption=message, parse_mode=ParseMode.HTML),
                    reply_markup=reply_markup
                )
            except Exception:
                pass

    return CRYPTO_SELECTION


async def show_payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the specific payment details."""
    query = update.callback_query
    await query.answer()
    
    # Reload addresses dynamically to avoid stale config
    addresses = load_addresses()
    crypto_code = query.data.replace("pay_", "")
    
    if crypto_code == "BINANCE":
        address = "861324344"
        name_info = "\n<b>Name:</b> Yousuf Omer"
        instr_type = "Binance ID"
    else:
        address = addresses.get(crypto_code, "Address pending...")
        name_info = ""
        instr_type = crypto_code

    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    amount = context.user_data.get('deposit_amount', 0.0)
    
    message = (
        f"<b>Deposit</b>\n\n"
        f"<b>Balance Deposit</b>\n"
        f"<b>Current Balance:</b> ${balance:.2f}\n"
        f"<b>Deposit Amount:</b> ${amount:.2f}\n"
        f"<b>Method:</b> {instr_type}{name_info}\n\n"
        f"Please send <u>${amount:.2f}</u> via {instr_type} to\n"
        f"<code>{address}</code>\n\n"
        f"There is a 1% fee on deposits. Consider that when sending.\n\n"
        f"<b>Send Payment Screenshot here and to @Jaalebis</b>\n\n"
        f"<b>Support:</b> @Jaalebis"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("Contact Support", url="https://t.me/jaalebis"),
            InlineKeyboardButton("Back to Selection", callback_data="back_to_crypto")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return CRYPTO_SELECTION


async def handle_purchase_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show plan category options."""
    query = update.callback_query
    await query.answer()
    
    message = (
        "<b><u>Select Your Acquisition Category</u></b>\n\n"
        "Please choose the tier of service that aligns with your operational requirements. "
        "Standard Plans offer consistent, reliable exposure, while Advanced Bundles provide "
        "aggressive scaling for professional-grade advertising campaigns.\n\n"
        "Select a category below to view detailed specifications:"
    )
    
    keyboard = [
        [InlineKeyboardButton("Standard Plans", callback_data="show_plans")],
        [InlineKeyboardButton("Advanced Bundles", callback_data="show_bundles")],
        [InlineKeyboardButton("Back to Menu", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(open(PLANS_IMAGE_PATH, 'rb'), caption=message, parse_mode=ParseMode.HTML),
            reply_markup=reply_markup
        )
    except Exception:
        await query.edit_message_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    return CHOOSING

async def handle_show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show standard plan options."""
    query = update.callback_query
    await query.answer()
    
    message = (
        "<b><u>Bronze Bundle — Basic Month</u></b>\n"
        "  1 Adbot Account (2 with your ALT)\n"
        "  300-600 posts every hour\n"
        "  Offered at 9.99$ Month\n\n"
        "<b><u>Gold Bundle — Gold Month</u></b>\n"
        "  5 Adbot Accounts\n"
        "  1k-2k posts every hour\n"
        "  Offered at 49.99$ Month\n\n"
        "<b><u>Premium Bundle — Premium Month</u></b>\n"
        "  10 Adbot Accounts\n"
        "  5K-10K posts every hour\n"
        "  Offered at 119.99$ Month\n\n"
        "Looking for something specific? PM @jaalebis to craft a custom plan."
    )
    
    keyboard = [
        [InlineKeyboardButton("Select Bronze ($9.99)", callback_data="buy_bronze")],
        [InlineKeyboardButton("Select Gold ($49.99)", callback_data="buy_gold")],
        [InlineKeyboardButton("Select Premium ($119.99)", callback_data="buy_premium")],
        [
            InlineKeyboardButton("Back to Selection", callback_data="purchase_plan"),
            InlineKeyboardButton("Back to Menu", callback_data="back_to_start")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return CHOOSING

async def handle_show_bundles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show advanced bundle options."""
    query = update.callback_query
    await query.answer()
    
    message = (
        "<b><u>Amber Bundle — Amber Month</u></b>\n"
        "  3 Adbot Accounts\n"
        "  2K–4K posts per hour\n"
        "  Offered at 39.99$ Month\n\n"
        "<b><u>Copper Bundle — Copper Month</u></b>\n"
        "  7 Adbot Accounts\n"
        "  6K–12K posts per hour\n"
        "  Offered at 89.99$ Month\n\n"
        "<b><u>Obsidian Bundle — Obsidian Month</u></b>\n"
        "  20 Adbot Accounts\n"
        "  15K–30K posts per hour\n"
        "  Offered at 199.99$ Month\n\n"
        "<b>Higher Scaling:</b> Contact @Jaalebis for custom configurations."
    )
    
    keyboard = [
        [InlineKeyboardButton("Select Amber ($39.99)", callback_data="buy_amber")],
        [InlineKeyboardButton("Select Copper ($89.99)", callback_data="buy_copper")],
        [InlineKeyboardButton("Select Obsidian ($199.99)", callback_data="buy_obsidian")],
        [
            InlineKeyboardButton("Back to Selection", callback_data="purchase_plan"),
            InlineKeyboardButton("Back to Menu", callback_data="back_to_start")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    return CHOOSING

async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle actual purchase - promotes prospects to clients on first purchase."""
    query = update.callback_query
    await query.answer()

    plan_key = query.data
    logger.info(f"[PURCHASE] User {update.effective_user.id} clicked: {plan_key}")
    
    plan_info = PLAN_PRICES.get(plan_key)
    if not plan_info: 
        logger.warning(f"[PURCHASE] Plan not found: {plan_key}")
        return CHOOSING

    price = plan_info['price']
    plan_name = plan_info['name']
    user_id = update.effective_user.id

    # Check Balance
    balance = get_user_balance(user_id)
    logger.info(f"[PURCHASE] User {user_id} balance: ${balance:.2f}, price: ${price:.2f}")
    
    if balance < price:
        logger.warning(f"[PURCHASE] Insufficient funds for user {user_id}")
        insufficient_msg = (
            f"<b><u>Insufficient Infrastructure Credit</u></b>\n\n"
            f"Your current balance of <code>${balance:.2f}</code> is below the requirement for the <b>{plan_name}</b> (<code>${price:.2f}</code>).\n\n"
            f"To maintain your competitive advantage and activate this tier, please deposit the required funds into your wallet.\n\n"
            f"<b>Need Assistance?</b> Contact @Jaalebis"
        )
        await query.answer("Insufficient funds for this acquisition.", show_alert=True)
        try:
            await query.edit_message_caption(
                caption=insufficient_msg,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Deposit Funds", callback_data="deposit_start")],
                    [InlineKeyboardButton("Back to Plans", callback_data="purchase_plan")]
                ]),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await query.message.reply_text(insufficient_msg, parse_mode=ParseMode.HTML)
        return CHOOSING

    try:
        logger.info(f"[PURCHASE] Starting database transaction for user {user_id}")
        
        # Determine subscription type
        sub_type_map = {
            "buy_bronze": "bronze",
            "buy_gold": "gold",
            "buy_premium": "premium",
            "buy_amber": "amber",
            "buy_copper": "copper",
            "buy_obsidian": "obsidian"
        }
        new_sub_type = sub_type_map.get(plan_key, "starter")
        
        # Check if user is already a client
        existing_client = db.get_client_by_telegram_id(user_id)
        
        if existing_client:
            # Existing client - update their subscription
            logger.info(f"[PURCHASE] Existing client {user_id}, updating subscription")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                client_id_pk = existing_client['id']
                current_balance = float(existing_client.get('balance', 0.0) or 0.0)
                
                # Double-check balance
                if current_balance < price:
                    logger.warning(f"[PURCHASE] DB balance check failed for user {user_id}")
                    await query.answer("Insufficient funds error.", show_alert=True)
                    return CHOOSING
                
                # Check for existing active plan (Admins can bypass this for testing/renewal)
                # CRITICAL FIX: Only check active plan if the client record itself is active
                is_client_active = bool(existing_client.get('is_active', True))
                
                if is_client_active and existing_client.get('expires_at') and user_id not in ADMIN_IDS:
                    try:
                        exp_str = existing_client['expires_at']
                        # Handle SQLite space in timestamp
                        if ' ' in exp_str:
                            exp_str = exp_str.replace(' ', 'T')
                        # Strip microseconds if present to avoid parsing issues
                        if '.' in exp_str:
                            exp_str = exp_str.split('.')[0]
                        
                        exp_date = datetime.fromisoformat(exp_str)
                        if exp_date > datetime.now() and existing_client.get('subscription_type') != 'starter':
                            logger.warning(f"[PURCHASE] User {user_id} already has active plan until {exp_date}")
                            msg = (
                                "⚠️ <b>You already have an active plan!</b>\n\n"
                                f"Your current subscription is active until: <code>{exp_date.strftime('%Y-%m-%d %H:%M')}</code>\n\n"
                                "Please wait for your current plan to expire before purchasing a new one. "
                                "If you need to upgrade for more accounts, contact @Jaalebis."
                            )
                            await query.answer("You already have an active plan.", show_alert=True)
                            try:
                                await query.edit_message_caption(
                                    caption=msg,
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Menu", callback_data="back_to_start")]]),
                                    parse_mode=ParseMode.HTML
                                )
                            except Exception:
                                await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
                            return CHOOSING
                    except Exception as e:
                        logger.warning(f"Note: Subscription check skipped due to date format: {e}")
                elif existing_client.get('expires_at') and user_id in ADMIN_IDS:
                    logger.info(f"[PURCHASE] Admin {user_id} bypassing active plan check.")

                new_balance = current_balance - price
                access_token = existing_client['access_token'] or "UNKNOWN"
                
                # Update Expiry (+30 days) and Subscription Type
                new_expiry = datetime.now() + timedelta(days=30)

                # Deduct Balance and update plan
                logger.info(f"[PURCHASE] Updating balance: ${current_balance:.2f} -> ${new_balance:.2f}")
                cursor.execute("""
                    UPDATE clients 
                    SET balance = ?, expires_at = ?, subscription_type = ?, is_active = 1
                    WHERE telegram_id = ?
                """, (new_balance, new_expiry, new_sub_type, user_id))
                
                # Create Order using system's native 16-character format
                order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                logger.info(f"[PURCHASE] Creating order {order_id} for {plan_name}")
                cursor.execute("""
                    INSERT INTO orders (order_id, client_id, product_name, status) 
                    VALUES (?, ?, ?, 'submitted')
                """, (order_id, client_id_pk, plan_name))
                
        else:
            # New client - promote from prospect
            logger.info(f"[PURCHASE] New client {user_id}, promoting from prospect")
            
            # Get prospect data
            prospect = db.get_prospect_by_telegram_id(user_id)
            if not prospect:
                logger.error(f"[PURCHASE] User {user_id} not found in prospects or clients!")
                await query.answer("Registration error. Please restart the bot.", show_alert=True)
                return CHOOSING
            
            current_balance = float(prospect.get('balance', 0.0) or 0.0)
            
            # Double-check balance
            if current_balance < price:
                logger.warning(f"[PURCHASE] Prospect balance check failed for user {user_id}")
                await query.answer("Insufficient funds error.", show_alert=True)
                return CHOOSING
            
            new_balance = current_balance - price
            
            # Promote prospect to client
            new_client = db.promote_prospect_to_client(user_id, new_sub_type, expires_days=30)
            
            if not new_client:
                logger.error(f"[PURCHASE] Failed to promote prospect {user_id} to client")
                await query.answer("Purchase error. Contact support.", show_alert=True)
                return CHOOSING
            
            # Update balance after promotion
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE clients SET balance = ? WHERE telegram_id = ?", (new_balance, user_id))
                
                # Create Order
                order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                logger.info(f"[PURCHASE] Creating order {order_id} for new client {plan_name}")
                cursor.execute("""
                    INSERT INTO orders (order_id, client_id, product_name, status) 
                    VALUES (?, ?, ?, 'submitted')
                """, (order_id, new_client['id'], plan_name))
            
            access_token = new_client['access_token']
            logger.info(f"[PURCHASE] Successfully promoted prospect {user_id} to client with token {access_token}")
        
        # Success message (same for both paths)
        message = (
            f"<b><u>Order Submitted:</u></b> Your Order ID\n\n"
            f"<code>{order_id}</code>\n\n"
            f"Your transaction has been successfully processed and your order is now queued for provisioning. We appreciate your investment in EyeconLabs infrastructure.\n\n"
            f"<u><a href=\"https://app.eyeconlabs.com/track\">Monitor Your Provisioning Status via the Real-Time Tracker</a></u>\n\n"
            f"In the interim, please authenticate your session on the <b>Client Portal</b> at <a href=\"https://app.eyeconlabs.com\">app.eyeconlabs.com</a> using your unique access code: <code>{access_token}</code>\n\n"
            f"<u>Our technical team will review your order details and finalize the provisioning process at the earliest convenience. This ensures your environment is optimized for peak performance from the moment of activation.</u>\n\n"
            f"<b>Support:</b> @Jaalebis"
        )
        
        logger.info(f"[PURCHASE] Order {order_id} created successfully")
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(open(BANNER_PATH, 'rb'), caption=message, parse_mode=ParseMode.HTML),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Menu", callback_data="back_to_start")]])
            )
        except Exception as edit_err:
             logger.warning(f"[PURCHASE] Media edit failed: {edit_err}, trying caption edit")
             await query.edit_message_caption(caption=message, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Purchase error: {e}", exc_info=True)
        await query.answer("An error occurred. Contact support.", show_alert=True)
        
    return CHOOSING


async def handle_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show wallet balance."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    balance = get_user_balance(user_id)
    
    response = (
        f"<b>Your EyeconBumps Wallet</b>\n\n"
        f"<b>Current Balance:</b> <code>${balance:.2f}</code>\n\n"
        f"<i>Your wallet is the fuel that powers unstoppable visibility.</i>\n\n"
        f"<b>With auto top-ups enabled, you never go dark.</b>\n"
        f"<i>This is not just a balance—it's your competitive edge.</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("Top Up", callback_data="deposit_start")],
        [InlineKeyboardButton("Back to Menu", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(open(WALLET_IMAGE_PATH, 'rb'), caption=response, parse_mode=ParseMode.HTML),
            reply_markup=reply_markup
        )
    except Exception:
        await query.edit_message_caption(caption=response, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    return CHOOSING


async def dummy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Placeholder."""
    query = update.callback_query
    await query.answer("Coming soon!", show_alert=True)
    return CHOOSING


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation."""
    return await show_main_menu(update, context)

# ---------------- STANDALONE COMMANDS ---------------- #

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /wallet command."""
    user = update.effective_user
    ensure_user_registered(user)
    balance = get_user_balance(user.id)
    
    response = (
        f"<b>Your EyeconBumps Wallet</b>\n\n"
        f"<b>Current Balance:</b> <code>${balance:.2f}</code>\n\n"
        f"<i>Your wallet is the fuel that powers unstoppable visibility.</i>\n\n"
        f"<b>With auto top-ups enabled, you never go dark.</b>\n"
        f"<i>This is not just a balance—it's your competitive edge.</i>"
    )
    
    keyboard = [[InlineKeyboardButton("Deposit", callback_data="deposit_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if os.path.exists(WALLET_IMAGE_PATH):
        await update.message.reply_photo(
            photo=open(WALLET_IMAGE_PATH, 'rb'),
            caption=response,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(response, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def my_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /my_orders command."""
    user = update.effective_user
    ensure_user_registered(user)
    await show_orders_list(update, context)

async def show_orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shared logic for listing orders."""
    user = update.effective_user
    is_callback = update.callback_query is not None
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM clients WHERE telegram_id = ?", (user.id,))
        client = cursor.fetchone()
        
        if not client:
            msg = "You don't have any orders yet."
            if is_callback:
                await update.callback_query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return

        client_id_pk = client['id']
        cursor.execute("""
            SELECT order_id, product_name, status, created_at
            FROM orders 
            WHERE client_id = ? 
            ORDER BY created_at DESC LIMIT 50
        """, (client_id_pk,))
        orders = cursor.fetchall()

    if not orders:
        msg = "You don't have any orders yet."
        if is_callback:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    message = (
        "<b><u>Account Order History</u></b>\n\n"
        "Welcome to your centralized order management dashboard. Below is far-reaching log of all historical transactions and service acquisitions associated with your infrastructure. "
        "Our system preserves these records to ensure full auditability and transparency of your EyconLabs environment.\n\n"
        "Please select a specific entry from the chronological log below to review provisioning details, technical identifiers, and status history."
    )
    keyboard = []
    for o in orders:
        # Format the date for the button text to make it look like a log
        try:
            date_str = o['created_at'].split(' ')[0] if o['created_at'] else "N/A"
        except:
            date_str = "N/A"
            
        status_label = o['status'].upper()
        keyboard.append([InlineKeyboardButton(
            f"[{date_str}] {o['product_name']} - {status_label}", 
            callback_data=f"view_order_{o['order_id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="back_to_start")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def handle_order_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show details for a specific order."""
    query = update.callback_query
    await query.answer()
    
    order_id = query.data.replace("view_order_", "")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.*, c.access_token 
            FROM orders o 
            JOIN clients c ON o.client_id = c.id
            WHERE o.order_id = ?
        """, (order_id,))
        order = cursor.fetchone()

    if not order:
        await query.edit_message_text("Order not found.")
        return

    status = order['status']
    is_completed = status == 'completed'
    access_token = order['access_token'] or "UNKNOWN"
    
    if is_completed:
        message = (
            f"<b><u>Order Completed:</u></b> Your Order ID\n\n"
            f"<code>{order_id}</code>\n\n"
            f"Confirmation of Service Provisioning: Your order has been successfully fulfilled and all associated digital assets have been deployed to your account profile.\n\n"
            f"<b>Service Level:</b> {order['product_name']}\n"
            f"<b>Final Status:</b> Successfully Provisioned\n\n"
            f"All features associated with this upgrade are now active. You may immediately proceed to manage your campaigns and monitor performance metrics through the Web Portal dashboard. "
            f"Thank you for your continued trust in our marketing infrastructure.\n\n"
            f"<b>Operational Support:</b> @Jaalebis"
        )
    else:
        message = (
            f"<b><u>Order Submitted:</u></b> Your Order ID\n\n"
            f"<code>{order_id}</code>\n\n"
            f"Thank you for choosing EyeconLabs. Your request for service activation has been successfully logged within our provisioning system and is currently prioritized for manual "
            f"review by our technical team.\n\n"
            f"<b>Tier Identification:</b> {order['product_name']}\n"
            f"<b>Current Phase:</b> Technical Verification\n\n"
            f"<u><a href=\"https://app.eyeconlabs.com/track\">Monitor Provisioning Progress via Our Status Tracker</a></u>\n\n"
            f"While our team finalizes your configuration, we invite you to explore the <b>Web Portal</b>. You may authenticate your session at <a href=\"https://app.eyeconlabs.com\">app.eyeconlabs.com</a> "
            f"using the following administrative access code: <code>{access_token}</code>\n\n"
            f"<u>Please be advised that our specialists will review your order and complete the final deployment at the earliest convenience. This manual verification ensures the highest level of service "
            f"reliability for your account.</u>\n\n"
            f"<b>Operational Support:</b> @Jaalebis"
        )

    keyboard = [
        [InlineKeyboardButton("Back to Orders", callback_data="my_orders_list")],
        [InlineKeyboardButton("Back to Menu", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        text=message, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.HTML, 
        disable_web_page_preview=True
    )

# ---------------- ADMIN COMMANDS ---------------- #

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Show administrative dashboard options."""
    if update.effective_user.id not in ADMIN_IDS: return
    
    msg = (
        "<b>Admin Control Panel</b>\n\n"
        "Manage accounts, orders, and infrastructure:"
    )
    
    keyboard = [
        [InlineKeyboardButton("Account Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("Pending Orders", callback_data="admin_pending")],
        [InlineKeyboardButton("Restock Accounts", callback_data="admin_restock_info")],
        [InlineKeyboardButton("Bulk Join", callback_data="admin_join_info")],
        [InlineKeyboardButton("Session Monitor", callback_data="admin_monitor_info")],
        [InlineKeyboardButton("OTP Fetcher", callback_data="admin_otp_info")],
        [InlineKeyboardButton("Back", callback_data="back_to_start")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_caption(caption=msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper for admin_accounts."""
    if update.effective_user.id not in ADMIN_IDS: return
    await admin_accounts(update, context)

async def admin_pending_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper for admin_pending_orders."""
    if update.effective_user.id not in ADMIN_IDS: return
    await admin_pending_orders(update, context)

async def admin_restock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper for admin_restock."""
    if update.effective_user.id not in ADMIN_IDS: return
    await admin_restock(update, context)

async def admin_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper for admin_join."""
    if update.effective_user.id not in ADMIN_IDS: return
    await admin_join(update, context)

async def admin_monitor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper for admin_monitor."""
    if update.effective_user.id not in ADMIN_IDS: return
    await admin_monitor(update, context)

async def admin_otp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback wrapper for admin_otp."""
    if update.effective_user.id not in ADMIN_IDS: return
    await admin_otp(update, context)

async def admin_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /days <client_telegram_id> <days> - Set expiry days for a client."""
    if update.effective_user.id not in ADMIN_IDS: return

    if len(context.args) < 1:
        # Show all active plans if no args
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id, name, expires_at FROM clients WHERE is_active = 1 AND expires_at IS NOT NULL ORDER BY expires_at DESC")
            rows = cursor.fetchall()
            
        if not rows:
            await update.message.reply_text("No active client plans found.")
            return
            
        text = "📅 <b>Active Client Plans</b>\n\n"
        for row in rows:
            expiry_str = row['expires_at']
            if expiry_str:
                if ' ' in expiry_str: expiry_str = expiry_str.replace(' ', 'T')
                if '.' in expiry_str: expiry_str = expiry_str.split('.')[0]
                try:
                    expiry = datetime.fromisoformat(expiry_str)
                    expiry_display = expiry.strftime('%Y-%m-%d %H:%M')
                    
                    # Add remaining days
                    remaining = (expiry - datetime.now()).days
                    text += f"• <code>{row['telegram_id']}</code> | {row['name']} | <b>{remaining}d left</b> (<code>{expiry_display}</code>)\n"
                except:
                    text += f"• <code>{row['telegram_id']}</code> | {row['name']} | Exp: <code>{expiry_str}</code>\n"
            else:
                text += f"• <code>{row['telegram_id']}</code> | {row['name']} | Exp: <code>N/A</code>\n"
        
        text += "\nUse <code>/days &lt;client_telegram_id&gt; &lt;days&gt;</code> to modify an expiry."
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "📅 <b>Set Client Expiry Days</b>\n\n"
            "Please send the <b>Client's Telegram ID</b> and <b>Days</b> (e.g. <code>/days 6926297956 30</code>).\n"
            "The Client's Telegram ID is their personal ID, not an account ID.",
            parse_mode=ParseMode.HTML
        )
        context.user_data['awaiting_admin_input'] = 'set_days'
        context.user_data['days_target_id'] = context.args[0] # Store first arg if only one is given
        return

    return await execute_days(update, context, context.args[0], context.args[1])

async def execute_days(update: Update, context: ContextTypes.DEFAULT_TYPE, client_telegram_id_str: str, days_str: str):
    try:
        client_telegram_id = int(client_telegram_id_str)
        days = int(days_str)
        
        if days < 0:
            await update.message.reply_text("Days must be a non-negative number.")
            return

        from datetime import datetime, timedelta
        new_expiry = (datetime.now() + timedelta(days=days)).isoformat(sep=' ', timespec='seconds') # Format for SQLite

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clients SET expires_at = ?, is_active = 1 WHERE telegram_id = ?", (new_expiry, client_telegram_id))
            updated = cursor.rowcount > 0
            
        if not updated:
            await update.message.reply_text(f"❌ Client with Telegram ID <code>{client_telegram_id}</code> not found in the Clients table.", parse_mode=ParseMode.HTML)
            return
            
        text = (
            f"<b>✅ Plan Expiry Updated!</b>\n\n"
            f"Your plan has been extended by <b>{days} days</b>.\n"
            f"New Expiry: <b>{new_expiry}</b>"
        )
        
        try:
            await context.bot.send_message(client_telegram_id, text, parse_mode=ParseMode.HTML)
            await update.message.reply_text(f"✅ Successfully updated client <code>{client_telegram_id}</code> expiry to <code>{new_expiry}</code> and notified user.", parse_mode=ParseMode.HTML)
        except Exception as e:
            await update.message.reply_text(f"✅ Expiry updated for client <code>{client_telegram_id}</code> to <code>{new_expiry}</code>, but could not notify user: <i>{e}</i>", parse_mode=ParseMode.HTML)
            
    except ValueError:
        await update.message.reply_text("❌ Invalid format. Use: <code>/days &lt;client_telegram_id&gt; &lt;days&gt;</code> (numbers only)", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in execute_days: {e}", exc_info=True)
        await update.message.reply_text(f"❌ An unexpected error occurred: <i>{e}</i>", parse_mode=ParseMode.HTML)

async def admin_add_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /add_funds <telegram_id> <amount>"""
    if update.effective_user.id not in ADMIN_IDS: return

    # If args are missing, start interactive prompt
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 <b>Add Funds</b>\n\n"
            "Please send the <b>User ID</b> and <b>Amount</b> separated by a space.\n"
            "Example: <code>6926297956 120</code>",
            parse_mode=ParseMode.HTML
        )
        context.user_data['awaiting_admin_input'] = 'add_funds'
        return

    return await execute_add_funds(update, context, context.args[0], context.args[1])


async def admin_order_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /order_complete <order_id>"""
    if update.effective_user.id not in ADMIN_IDS: return

    # If args are missing, start interactive prompt
    if not context.args:
        await update.message.reply_text(
            "📝 <b>Complete Order</b>\n\n"
            "Please send the <b>Order ID</b> to mark as completed:",
            parse_mode=ParseMode.HTML
        )
        context.user_data['awaiting_admin_input'] = 'order_complete'
        return

    return await execute_order_complete(update, context, context.args[0])


async def execute_add_funds(update: Update, context: ContextTypes.DEFAULT_TYPE, target_id_str: str, amount_str: str):
    """Actual logic for adding funds."""
    try:
        target_id = int(target_id_str)
        amount = float(amount_str)
        
        user_row = None
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM clients WHERE telegram_id = ?", (target_id,))
            user_row = cursor.fetchone()
            
        if not user_row:
            # Check prospects first to see if they have a balance there
            prospect = db.get_prospect_by_telegram_id(target_id)
            current_balance = float(prospect.get('balance', 0.0) or 0.0) if prospect else 0.0
            
            await update.message.reply_text(f"User {target_id} not in Clients. Attempting promotion from Prospects...")
            
            # Attempt to fetch real name from Telegram
            real_name = f"User_{target_id}"
            username = None
            try:
                chat = await context.bot.get_chat(target_id)
                real_name = chat.full_name or chat.username or real_name
                username = chat.username
            except Exception as e:
                logger.warning(f"Could not fetch chat info for {target_id}: {e}")

            db.create_client(
                name=real_name, 
                telegram_id=target_id, 
                telegram_username=username,
                notes="Auto-registered via admin"
            )
        else:
            current_balance = float(user_row['balance'] or 0)
            
        new_balance = current_balance + amount
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE clients SET balance = ? WHERE telegram_id = ?", (new_balance, target_id))
            # Also update prospect balance just in case both tables are checked
            cursor.execute("UPDATE prospects SET balance = ? WHERE telegram_id = ?", (new_balance, target_id))
            
        notification_text = (
            f"<b>Wallet Update</b>\n\n"
            f"Your balance has been updated! Received: <b>${amount:.2f}</b>\n"
            f"Current Balance: <b>${new_balance:.2f}</b>"
        )
        
        if update.effective_user.id == target_id:
            await update.message.reply_text(notification_text, parse_mode=ParseMode.HTML)
        else:
            try:
                await context.bot.send_message(target_id, notification_text, parse_mode=ParseMode.HTML)
                await update.message.reply_text(f"Success: ${amount:.2f} added to user {target_id}.")
            except Exception as e:
                await update.message.reply_text(f"Balance updated, but could not notify user: {e}")

    except ValueError:
        await update.message.reply_text("Invalid format. Please provide numeric ID and Amount.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def execute_order_complete(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str):
    """Actual logic for completing an order."""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT client_id FROM orders WHERE order_id = ?", (order_id,))
            order = cursor.fetchone()
            
            if not order:
                await update.message.reply_text(f"Order <code>{order_id}</code> not found.", parse_mode=ParseMode.HTML)
                return
            
            client_id_pk = order['client_id']
            cursor.execute("SELECT telegram_id FROM clients WHERE id = ?", (client_id_pk,))
            client = cursor.fetchone()
            
            if not client:
                await update.message.reply_text("Client not found for this order.")
                return
                
            cursor.execute("UPDATE orders SET status = 'completed' WHERE order_id = ?", (order_id,))
            await update.message.reply_text(f"Order <code>{order_id}</code> marked as completed.", parse_mode=ParseMode.HTML)
            try:
                await context.bot.send_message(client['telegram_id'], f"<b>Order Completed!</b>\n\nYour order <b>{order_id}</b> has been fulfilled.", parse_mode=ParseMode.HTML)
            except: pass

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for admins when they are in a specific state."""
    if update.effective_user.id not in ADMIN_IDS: return
    
    state = context.user_data.get('awaiting_admin_input')
    if not state: return

    text = update.message.text.strip()
    
    if state == 'add_funds':
        parts = text.split()
        if len(parts) >= 2:
            del context.user_data['awaiting_admin_input']
            return await execute_add_funds(update, context, parts[0], parts[1])
        else:
            await update.message.reply_text("Please send both ID and Amount (e.g. `12345 100`):")
            
    elif state == 'order_complete':
        del context.user_data['awaiting_admin_input']
        return await execute_order_complete(update, context, text)
        
    elif state == 'join_count':
        if text.isdigit():
            del context.user_data['awaiting_admin_input']
            count = int(text)
            await update.message.reply_text(f"<b>Nuclear Sequence: {count} Accounts</b> starting in background...")
            context.job_queue.run_once(execute_bulk_join, 0, data={"mode": "specific", "count": count, "admin_id": update.effective_user.id})
        else:
            await update.message.reply_text("Please enter a valid number:")

    elif state == 'join_selection':
        text = update.message.text.strip().lower()
        mapping = context.user_data.get('join_mapping', {})
        
        if text == 'global':
            del context.user_data['awaiting_admin_input']
            context.args = ['global']
            return await admin_join(update, context)
        
        parts = text.replace(',', ' ').split()
        target_ids = []
        for p in parts:
            if p.isdigit():
                idx = int(p)
                db_id = mapping.get(idx)
                if db_id:
                    target_ids.append(str(db_id))
        
        if target_ids:
            del context.user_data['awaiting_admin_input']
            context.args = target_ids
            return await admin_join(update, context)
        else:
            await update.message.reply_text("Invalid selection. Please enter numbers from the list (e.g. 1 2 3) or 'global':")

    elif state == 'otp_selection':
        text = update.message.text.strip()
        mapping = context.user_data.get('otp_mapping', {})
        
        if text.isdigit():
            idx = int(text)
            acc_id = mapping.get(idx)
            if acc_id:
                del context.user_data['awaiting_admin_input']
                return await execute_otp_fetch(update, context, acc_id)
        
        await update.message.reply_text("Invalid selection. Please enter a number from the list.")

    elif state == 'monitor_selection':
        text = update.message.text.strip().lower()
        mapping = context.user_data.get('monitor_mapping', {})
        
        if text == 'global':
            del context.user_data['awaiting_admin_input']
            context.args = ['global']
            return await admin_monitor(update, context)
        
        parts = text.replace(',', ' ').split()
        target_ids = []
        for p in parts:
            if p.isdigit():
                idx = int(p)
                db_id = mapping.get(idx)
                if db_id:
                    target_ids.append(str(db_id))
        
        if target_ids:
            del context.user_data['awaiting_admin_input']
            context.args = target_ids
            return await admin_monitor(update, context)
        else:
            await update.message.reply_text("Invalid selection. Please enter numbers from the list (e.g. 1 2 3) or 'global':")

    elif state == 'configure_selection':
        text = update.message.text.strip().lower()
        mapping = context.user_data.get('configure_mapping', {})
        target_ids = []
        
        if text == 'global':
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM client_accounts WHERE is_active = 1")
                target_ids = [r[0] for r in cursor.fetchall()]
        else:
            parts = text.replace(',', ' ').split()
            for p in parts:
                if p.isdigit():
                    idx = int(p)
                    db_id = mapping.get(idx)
                    if db_id: target_ids.append(db_id)
        
        if target_ids:
            context.user_data['configure_target_ids'] = target_ids
            context.user_data['awaiting_admin_input'] = 'configure_pfp'
            await update.message.reply_text("📸 <b>Step 2/5: Profile Photo</b>\n\nPlease upload the <b>Profile Photo</b> to apply to all selected accounts.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Invalid selection. Please enter numbers from the list or 'global':")

    elif state == 'configure_name_prefix':
        context.user_data['configure_name_prefix'] = text
        context.user_data['awaiting_admin_input'] = 'configure_username_pattern'
        await update.message.reply_text("🔡 <b>Step 4/5: Username Pattern</b>\n\nPlease send the username pattern (e.g. <code>aigncybumps</code>). Numbers will be appended sequentially.", parse_mode=ParseMode.HTML)

    elif state == 'configure_username_pattern':
        context.user_data['configure_username_pattern'] = text
        context.user_data['awaiting_admin_input'] = 'configure_bio'
        await update.message.reply_text("📝 <b>Step 5/5: Bio Text</b>\n\nPlease send the <b>Bio/About</b> text for all accounts.", parse_mode=ParseMode.HTML)

    elif state == 'configure_bio':
        context.user_data['configure_bio'] = text
        target_ids = context.user_data.get('configure_target_ids', [])
        
        del context.user_data['awaiting_admin_input']
        
        msg = (
            f"🚀 <b>Configuration Sequence Initialized</b>\n\n"
            f"👥 <b>Accounts:</b> {len(target_ids)}\n"
            f"🏷 <b>Name Prefix:</b> {context.user_data.get('configure_name_prefix')}\n"
            f"🔡 <b>User Pattern:</b> {context.user_data.get('configure_username_pattern')}\n"
            f"📝 <b>Bio Length:</b> {len(text)} chars\n\n"
            f"Processing in background..."
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        
        # Trigger background task
        context.job_queue.run_once(execute_bulk_configure, 0, data={
            "target_ids": target_ids,
            "pfp_path": context.user_data.get('configure_pfp_path'),
            "name_prefix": context.user_data.get('configure_name_prefix'),
            "user_pattern": context.user_data.get('configure_username_pattern'),
            "bio": context.user_data.get('configure_bio'),
            "admin_id": update.effective_user.id
        })


async def admin_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /pending_orders"""
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE status = 'submitted' LIMIT 10")
            orders = cursor.fetchall()
            if not orders:
                await update.message.reply_text("No pending orders.")
                return
            msg = "<b>Pending Orders:</b>\n"
            for o in orders:
                msg += f"ID: <code>{o['order_id']}</code> | Client: {o['client_id']} | Product: {o['product_name']}\n"
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def admin_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /accounts - Show summary of all connected accounts."""
    if update.effective_user.id not in ADMIN_IDS: return
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total in pool (no client)
            cursor.execute("SELECT COUNT(*) FROM client_accounts WHERE client_id IS NULL")
            pool_count = cursor.fetchone()[0]
            
            # Total assigned to clients
            cursor.execute("SELECT COUNT(*) FROM client_accounts WHERE client_id IS NOT NULL")
            assigned_count = cursor.fetchone()[0]
            
            # Active vs Inactive
            cursor.execute("SELECT COUNT(*) FROM client_accounts WHERE is_active = 1")
            active_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM client_accounts WHERE is_active = 0")
            inactive_count = cursor.fetchone()[0]
            
            # Premium count
            cursor.execute("SELECT COUNT(*) FROM client_accounts WHERE is_premium = 1")
            premium_count = cursor.fetchone()[0]
            
            # Total PMs sent (aggregate)
            cursor.execute("SELECT SUM(total_pms) FROM client_accounts")
            total_pms = cursor.fetchone()[0] or 0
            
            # Most active client
            cursor.execute("""
                SELECT c.name, COUNT(a.id) as acc_count 
                FROM clients c 
                JOIN client_accounts a ON c.id = a.client_id 
                GROUP BY c.id 
                ORDER BY acc_count DESC 
                LIMIT 1
            """)
            top_client = cursor.fetchone()
            top_client_str = f"Top Client: {top_client['name']} ({top_client['acc_count']} accs)" if top_client else "No clients assigned yet."

        msg = (
            f"<b>Account Infrastructure Summary</b>\n\n"
            f"<b>Total Connected:</b> {pool_count + assigned_count}\n"
            f"  In Pool: {pool_count}\n"
            f"  Assigned: {assigned_count}\n\n"
            f"<b>Status Breakdown:</b>\n"
            f"  Active: {active_count}\n"
            f"  Inactive: {inactive_count}\n\n"
            f"<b>Premium Accounts:</b> {premium_count}\n"
            f"<b>Total PMs Dispatched:</b> {total_pms:,}\n\n"
            f"<b>{top_client_str}</b>\n\n"
            f"<i>Use the Web Panel at app.eyeconlabs.com for detailed management.</i>"
        )
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in /accounts: {e}", exc_info=True)
        await update.message.reply_text(f"Error fetching account stats: {e}")

async def admin_restock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /restock - Ask for a ZIP file containing .session files."""
    if update.effective_user.id not in ADMIN_IDS: return
    
    await update.message.reply_text(
        "<b>Account Restock</b>\n\n"
        "Please upload a <b>ZIP file</b> containing your <code>.session</code> files.\n\n"
        "I will extract them, verify the logins, and add them to the system with the default group <b>'Eyecon'</b>.",
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_admin_input'] = 'restock_zip'

async def handle_restock_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the uploaded ZIP file for restocking accounts."""
    if update.effective_user.id not in ADMIN_IDS: return
    if context.user_data.get('awaiting_admin_input') != 'restock_zip': return
    
    document = update.message.document
    if not document or not document.file_name.lower().endswith('.zip'):
        await update.message.reply_text("Please upload a valid <b>ZIP file</b>.", parse_mode=ParseMode.HTML)
        return

    del context.user_data['awaiting_admin_input']
    status_msg = await update.message.reply_text("<b>Processing ZIP...</b>", parse_mode=ParseMode.HTML)
    
    temp_dir = tempfile.mkdtemp()
    try:
        # Download ZIP
        zip_file = await document.get_file()
        zip_path = os.path.join(temp_dir, "restock.zip")
        await zip_file.download_to_drive(zip_path)
        
        # Extract ZIP
        extract_path = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
            
        session_files = []
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                if file.lower().endswith('.session'):
                    session_files.append(os.path.join(root, file))
        
        if not session_files:
            await status_msg.edit_text("No <code>.session</code> files found in the ZIP.", parse_mode=ParseMode.HTML)
            return

        await status_msg.edit_text(f"🔍 <b>Found {len(session_files)} sessions.</b> Starting verification...", parse_mode=ParseMode.HTML)
        
        success_count = 0
        error_count = 0
        
        API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
        API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
        
        for sess_path in session_files:
            try:
                # FIX: Telethon adds .session suffix, so we remove it from the file path string
                client_path = sess_path[:-8] if sess_path.endswith('.session') else sess_path
                
                temp_client = TelegramClient(client_path, API_ID, API_HASH)
                await temp_client.connect()
                
                if not await temp_client.is_user_authorized():
                    logger.warning(f"Session unauthorized/banned: {sess_path}")
                    error_count += 1
                    await temp_client.disconnect()
                    continue
                
                me = await temp_client.get_me()
                phone = me.phone
                
                # CRITICAL FIX: Extract the connection string from the SQLite session file
                from telethon.sessions import StringSession
                string_session = StringSession.save(temp_client.session)
                
                display_name = (f"{me.first_name or ''} {me.last_name or ''}").strip() or f"User_{me.id}"
                is_premium = bool(getattr(me, 'premium', False))
                
                await temp_client.disconnect()
                
                # Add to DB
                new_acc = db.add_account(
                    phone_number=phone,
                    session_string=string_session,
                    display_name=display_name,
                    is_premium=is_premium,
                    client_id=None # Add to pool
                )
                
                # Mark as success
                db.update_account(new_acc['id'], notes="Eyecon")
                success_count += 1
                if success_count % 5 == 0:
                    await status_msg.edit_text(f"Progress: {success_count} added, {error_count} failed...", parse_mode=ParseMode.HTML)
                    
            except Exception as e:
                logger.error(f"Error processing session {sess_path}: {e}")
                error_count += 1
        
        await status_msg.edit_text(
            f"<b>Restock Complete!</b>\n\n"
            f"<b>Success:</b> {success_count}\n"
            f"<b>Failed:</b> {error_count}\n\n"
            f"All accounts tagged with 'Eyecon' in notes.",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Restock error: {e}", exc_info=True)
        await status_msg.edit_text(f"<b>Fatal Error during restock:</b> {e}", parse_mode=ParseMode.HTML)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

        shutil.rmtree(temp_dir, ignore_errors=True)

def parse_group_link(link: str) -> dict:
    """Parse a Telegram group link and return type + identifier."""
    import re
    link = link.strip()
    if link.startswith('@'): return {"type": "username", "value": link[1:]}
    joinchat = re.search(r't\.me/joinchat/([a-zA-Z0-9_-]+)', link)
    if joinchat: return {"type": "invite", "value": joinchat.group(1)}
    plus = re.search(r't\.me/\+([a-zA-Z0-9_-]+)', link)
    if plus: return {"type": "invite", "value": plus.group(1)}
    folders = re.search(r't\.me/addlist/([a-zA-Z0-9_-]+)', link)
    if folders: return {"type": "folder", "value": folders.group(1)}
    username = re.search(r't\.me/([a-zA-Z0-9_]+)', link)
    if username: return {"type": "username", "value": username.group(1)}
    return {"type": "unknown", "value": link}

async def admin_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /join - Bulk join folders with nuclear wipe."""
    if update.effective_user.id not in ADMIN_IDS: return
    
    args = context.args
    if not args:
        # Fetch all accounts to show a list
        accounts = db.get_all_accounts_summary()
        if not accounts:
            await update.message.reply_text("No accounts found in database.")
            return

        mapping = {}
        for idx, acc in enumerate(accounts, 1):
            mapping[idx] = acc['id']
        
        context.user_data['join_mapping'] = mapping
        context.user_data['awaiting_admin_input'] = 'join_selection'
        
        msg, reply_markup = get_account_list_page(accounts, 1, "join", "Bulk Join & Nuclear Wipe")
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return

    await update.message.reply_text("<b>Bulk Join Initialized</b> starting in background...", parse_mode=ParseMode.HTML)
    
    target_ids = []
    if args[0].lower() == 'global':
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM client_accounts WHERE is_active = 1")
            target_ids = [r[0] for r in cursor.fetchall()]
    else:
        try:
            target_ids = [int(x) for x in args]
        except ValueError:
            await update.message.reply_text("Invalid account IDs provided.")
            return

    if not target_ids:
        await update.message.reply_text("No target accounts found.")
        return

    # Start background task
    context.job_queue.run_once(execute_bulk_join, 0, data={"mode": "specific", "target_ids": target_ids, "admin_id": update.effective_user.id})

async def handle_join_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle choice for /join command."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "join_global":
        await query.edit_message_text("<b>Nuclear Sequence: GLOBAL</b> starting in background...")
        # Start background task
        context.job_queue.run_once(execute_bulk_join, 0, data={"mode": "global", "admin_id": update.effective_user.id})
    else:
        await query.edit_message_text("<b>How many accounts</b> should I use? (e.g. 15)")
        context.user_data['awaiting_admin_input'] = 'join_count'

async def execute_bulk_join(context: ContextTypes.DEFAULT_TYPE):
    """The heavy lifting for /join."""
    data = context.job.data
    mode = data.get("mode")
    count = data.get("count")
    admin_id = data.get("admin_id")
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if mode == "global":
            cursor.execute("SELECT id, session_string FROM client_accounts WHERE is_active = 1")
        elif data.get("target_ids"):
            targets = data.get("target_ids")
            placeholders = ','.join(['?'] * len(targets))
            cursor.execute(f"SELECT id, session_string FROM client_accounts WHERE id IN ({placeholders})", targets)
        else:
            cursor.execute("SELECT id, session_string FROM client_accounts WHERE is_active = 1 LIMIT ?", (count,))
        accounts = [{'id': r[0], 'session_string': r[1]} for r in cursor.fetchall()]
    
    if not accounts:
        try: await context.bot.send_message(admin_id, "No active accounts found to join."); return
        except: return

    try: await context.bot.send_message(admin_id, f"<b>Sequence Initiated</b> for {len(accounts)} accounts. Status updates will follow.", parse_mode=ParseMode.HTML)
    except: pass
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    from telethon.tl.functions.channels import LeaveChannelRequest
    from telethon.tl.functions.messages import DeleteChatRequest, DeleteHistoryRequest, GetDialogFiltersRequest, UpdateDialogFilterRequest
    from telethon.tl.types import Channel, Chat, User, DialogFilterChatlist
    from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest
    from telethon.tl.types.chatlists import ChatlistInvite, ChatlistInviteAlready

    for acc in accounts:
        try:
            async with TelegramClient(StringSession(acc['session_string']), API_ID, API_HASH) as client:
                # --- PHASE 0: NUCLEAR WIPE ---
                try:
                    filters_list = await client(GetDialogFiltersRequest())
                    for f in filters_list:
                        if isinstance(f, DialogFilterChatlist):
                            await client(UpdateDialogFilterRequest(id=f.id, filter=None))
                except: pass

                dialogs = await client.get_dialogs()
                for d in dialogs:
                    try:
                        if isinstance(d.entity, Channel): await client(LeaveChannelRequest(d.entity))
                        elif isinstance(d.entity, Chat): await client(DeleteChatRequest(d.entity.id))
                        elif isinstance(d.entity, User): await client(DeleteHistoryRequest(d.entity, max_id=0, just_clear=False, revoke=True))
                    except: pass
                
                # --- PHASE 1: FOLDER JOINS ---
                for link in DEFAULT_JOIN_LINKS:
                    parsed = parse_group_link(link)
                    if parsed['type'] == 'folder':
                        slug = parsed['value']
                        try:
                            res = await client(CheckChatlistInviteRequest(slug=slug))
                            peers = []
                            if isinstance(res, ChatlistInvite): peers = res.peers
                            elif isinstance(res, ChatlistInviteAlready): peers = getattr(res, 'missing_peers', [])
                            
                            if peers:
                                await client(JoinChatlistInviteRequest(slug=slug, peers=peers))
                            
                            # Clean up icon
                            filters_list = await client(GetDialogFiltersRequest())
                            for f in filters_list:
                                if isinstance(f, DialogFilterChatlist):
                                    await client(UpdateDialogFilterRequest(id=f.id, filter=None))
                        except: pass
            
            logger.info(f"Account {acc['id']} wiped and joined folders.")
            
        except Exception as e:
            logger.error(f"Error in nuclear join for account {acc['id']}: {e}")

    try: await context.bot.send_message(admin_id, f"<b>Bulk Join Sequence Complete</b> for {len(accounts)} accounts.", parse_mode=ParseMode.HTML)
    except: pass


# --- NEW: Group Link Checker ---

async def admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /check - Validate Telegram group links from a .txt file."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return CHOOSING

    msg = (
        "<b>🔍 Group Link Checker</b>\n\n"
        "Please upload a <code>.txt</code> file containing Telegram group links (one per line).\n\n"
        "The bot will use an active session to check which links are valid and return a filtered list of only live groups."
    )
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_start")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    
    return AWAITING_CHECK_FILE

async def handle_check_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the uploaded .txt file for checking group links."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        logger.warning(f"Unauthorized access attempt to /check by user {user_id}")
        return CHOOSING

    if not update.message.document:
        await update.message.reply_text("❌ Please upload a <code>.txt</code> file.", parse_mode=ParseMode.HTML)
        return AWAITING_CHECK_FILE

    file_name = update.message.document.file_name or ""
    if not file_name.lower().endswith('.txt'):
        await update.message.reply_text("❌ Please upload a valid <code>.txt</code> file.", parse_mode=ParseMode.HTML)
        return AWAITING_CHECK_FILE

    status_msg = await update.message.reply_text("⏳ <b>Processing file...</b>", parse_mode=ParseMode.HTML)
    
    temp_dir = tempfile.mkdtemp()
    try:
        # Download the file using proven method
        document = update.message.document
        tg_file = await document.get_file()
        temp_input_path = os.path.join(temp_dir, "input_links.txt")
        await tg_file.download_to_drive(temp_input_path)
        
        # Read links with robust encoding handling
        links = []
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(temp_input_path, 'r', encoding=encoding) as f:
                    links = [line.strip() for line in f if line.strip()]
                break
            except UnicodeDecodeError:
                continue

        if not links:
            await status_msg.edit_text("❌ The file is empty or could not be read.")
            return CHOOSING

        await status_msg.edit_text(f"⏳ <b>Checking {len(links)} links...</b>\n<i>Connecting to Telegram...</i>", parse_mode=ParseMode.HTML)

        # Get an active account to use for checking
        accounts = db.get_active_monitored_accounts()
        if not accounts:
            accounts = [a for a in db.get_all_accounts() if a.get('is_active')]
        
        if not accounts:
            await status_msg.edit_text("❌ No active accounts available to perform the check.")
            return CHOOSING

        # Pick the first active account
        acc = accounts[0]
        session_str = acc['session_string']
        phone = acc.get('phone_number', 'Unknown')
        
        await status_msg.edit_text(f"⏳ <b>Checking {len(links)} links...</b>\n<i>Using account: +{phone}</i>", parse_mode=ParseMode.HTML)

        valid_links = []
        invalid_count = 0
        
        from telethon.tl.functions.messages import CheckChatInviteRequest
        
        async with TelegramClient(StringSession(session_str), TELEGRAM_API_ID, TELEGRAM_API_HASH) as client:
            for i, link in enumerate(links, 1):
                if i % 10 == 0:
                    await status_msg.edit_text(f"⏳ <b>Progress: {i}/{len(links)}</b>\n✅ Valid: {len(valid_links)}\n❌ Invalid: {invalid_count}", parse_mode=ParseMode.HTML)
                
                parsed = parse_group_link(link)
                is_valid = False
                
                try:
                    if parsed['type'] == 'invite':
                        await client(CheckChatInviteRequest(hash=parsed['value']))
                        is_valid = True
                    elif parsed['type'] == 'username':
                        await client.get_entity(parsed['value'])
                        is_valid = True
                except Exception as e:
                    logger.debug(f"Link check failed for {link}: {e}")
                    is_valid = False
                
                if is_valid:
                    valid_links.append(link)
                else:
                    invalid_count += 1
                
                # Small sleep to avoid flood
                await asyncio.sleep(0.3)

        if not valid_links:
            await status_msg.edit_text(f"✅ Check complete. <b>0</b> valid links found out of {len(links)}.")
            return CHOOSING

        # Create output file
        temp_output_path = os.path.join(temp_dir, f"valid_groups_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(temp_output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(valid_links))

        await update.message.reply_document(
            document=open(temp_output_path, 'rb'),
            filename=os.path.basename(temp_output_path),
            caption=(
                f"✅ <b>Check Complete!</b>\n\n"
                f"📊 <b>Total Checked:</b> {len(links)}\n"
                f"✅ <b>Valid Links:</b> {len(valid_links)}\n"
                f"❌ <b>Invalid/Dead:</b> {invalid_count}\n\n"
                f"Filtered list attached below."
            ),
            parse_mode=ParseMode.HTML
        )
        
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error in handle_check_file: {e}", exc_info=True)
        try:
            await status_msg.edit_text(f"❌ <b>Error processing file:</b> {str(e)}", parse_mode=ParseMode.HTML)
        except:
            await update.message.reply_text(f"❌ <b>Error processing file:</b> {str(e)}", parse_mode=ParseMode.HTML)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return CHOOSING

# --- NEW: Global Joiner Commands ---

async def admin_globallinks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /globallinks - Join a list of chats on ALL accounts."""
    if update.effective_user.id not in ADMIN_IDS: return CHOOSING
    
    msg = (
        "<b>🌍 Global Link Joiner</b>\n\n"
        "Please send the list of Telegram links (one per line) or upload a <code>.txt</code> file.\n\n"
        "This will join <b>ALL</b> active accounts to <b>EVERY</b> link in the list.\n"
        "<i>Note: No existing data will be removed.</i>"
    )
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_start")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return AWAITING_GLOBAL_LINKS

async def admin_globalfolder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /globalfolder - Join folder(s) on ALL accounts and clean up filters."""
    if update.effective_user.id not in ADMIN_IDS: return CHOOSING
    
    msg = (
        "<b>📂 Global Folder Joiner</b>\n\n"
        "Please send the Telegram folder link(s) (e.g., <code>t.me/addlist/...</code>).\n\n"
        "This will:\n"
        "1. Join the folder(s) for <b>ALL</b> accounts.\n"
        "2. Remove the folder tab/icon immediately.\n"
        "3. <b>Keep</b> all chats from the folder in the main list."
    )
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_start")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return AWAITING_GLOBAL_FOLDER

async def handle_global_links_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the list of links for global joining."""
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS: return CHOOSING

    links = []
    if update.message.document:
        if not update.message.document.file_name.lower().endswith('.txt'):
            await update.message.reply_text("Please upload a .txt file.")
            return AWAITING_GLOBAL_LINKS
        
        temp_dir = tempfile.mkdtemp()
        try:
            tg_file = await update.message.document.get_file()
            temp_path = os.path.join(temp_dir, "links.txt")
            await tg_file.download_to_drive(temp_path)
            with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                links = [l.strip() for l in f if l.strip()]
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    elif update.message.text:
        links = [l.strip() for l in update.message.text.splitlines() if l.strip()]

    if not links:
        await update.message.reply_text("No valid links found. Please try again.")
        return AWAITING_GLOBAL_LINKS

    accounts = [a for a in db.get_all_accounts() if a.get('is_active')]
    if not accounts:
        await update.message.reply_text("No active accounts found in database.")
        return CHOOSING

    await update.message.reply_text(
        f"🚀 <b>Global Joiner Started!</b>\n\n"
        f"📊 <b>Accounts:</b> {len(accounts)}\n"
        f"🔗 <b>Links:</b> {len(links)}\n\n"
        f"This runs in the background. I will notify you when complete.",
        parse_mode=ParseMode.HTML
    )

    # Start background task
    asyncio.create_task(execute_global_join_task(admin_id, links, accounts, context.bot))
    return CHOOSING

async def handle_global_folder_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process folder links for global joining."""
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_IDS: return CHOOSING

    if not update.message.text:
        await update.message.reply_text("Please send the folder link(s) as text.")
        return AWAITING_GLOBAL_FOLDER

    import re
    folder_links = re.findall(r't\.me/addlist/([a-zA-Z0-9_-]+)', update.message.text)
    if not folder_links:
        await update.message.reply_text("No valid folder links (t.me/addlist/...) found.")
        return AWAITING_GLOBAL_FOLDER

    accounts = [a for a in db.get_all_accounts() if a.get('is_active')]
    if not accounts:
        await update.message.reply_text("No active accounts found in database.")
        return CHOOSING

    await update.message.reply_text(
        f"🚀 <b>Global Folder Joiner Started!</b>\n\n"
        f"📊 <b>Accounts:</b> {len(accounts)}\n"
        f"📂 <b>Folders:</b> {len(folder_links)}\n\n"
        f"Bot will join folders and clean up icons automatically.",
        parse_mode=ParseMode.HTML
    )

    # Start background task
    asyncio.create_task(execute_global_folder_task(admin_id, folder_links, accounts, context.bot))
    return CHOOSING

async def execute_global_join_task(admin_id, links, accounts, bot):
    """Background task to join links on all accounts with live progress."""
    total_accounts = len(accounts)
    total_links = len(links)
    success_joins = 0
    fail_joins = 0
    accounts_done = 0
    
    logger.info(f"Starting global join for {total_accounts} accounts and {total_links} links")
    
    # Send initial status message
    status_msg = await bot.send_message(
        admin_id,
        f"🌍 <b>Global Link Joiner — In Progress</b>\n\n"
        f"📊 Accounts: <code>0/{total_accounts}</code>\n"
        f"🔗 Links per account: <code>{total_links}</code>\n"
        f"✅ Joined: <code>0</code> | ❌ Failed: <code>0</code>\n\n"
        f"⏳ Starting...",
        parse_mode=ParseMode.HTML
    )
    
    logs = []
    
    for acc in accounts:
        phone = acc.get('phone_number', '???')
        session_str = acc['session_string']
        acc_success = 0
        acc_fail = 0
        try:
            async with TelegramClient(StringSession(session_str), TELEGRAM_API_ID, TELEGRAM_API_HASH) as client:
                for link in links:
                    parsed = parse_group_link(link)
                    try:
                        if parsed['type'] == 'invite':
                            from telethon.tl.functions.messages import ImportChatInviteRequest
                            await client(ImportChatInviteRequest(hash=parsed['value']))
                        elif parsed['type'] == 'username':
                            from telethon.tl.functions.channels import JoinChannelRequest
                            await client(JoinChannelRequest(parsed['value']))
                        acc_success += 1
                    except Exception as e:
                        if "already" in str(e).lower():
                            acc_success += 1
                        else:
                            acc_fail += 1
                    await asyncio.sleep(0.5)
        except Exception as e:
            acc_fail = total_links
            logger.error(f"Global join failed for account +{phone}: {e}")

        accounts_done += 1
        success_joins += acc_success
        fail_joins += acc_fail
        logs.append(f"{'✅' if acc_fail == 0 else '⚠️'} +{phone}: {acc_success} ok, {acc_fail} fail")
        
        # Update status every account
        log_tail = "\n".join(logs[-8:])  # Show last 8 logs
        try:
            await status_msg.edit_text(
                f"🌍 <b>Global Link Joiner — In Progress</b>\n\n"
                f"📊 Accounts: <code>{accounts_done}/{total_accounts}</code>\n"
                f"🔗 Links per account: <code>{total_links}</code>\n"
                f"✅ Joined: <code>{success_joins}</code> | ❌ Failed: <code>{fail_joins}</code>\n\n"
                f"<b>Recent:</b>\n<code>{log_tail}</code>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass  # Ignore edit failures (e.g. message not modified)

    # Final summary
    log_tail = "\n".join(logs[-10:])
    try:
        await status_msg.edit_text(
            f"✅ <b>Global Link Joiner — Complete!</b>\n\n"
            f"📊 <b>Accounts:</b> {total_accounts}\n"
            f"🔗 <b>Links:</b> {total_links}\n"
            f"✅ <b>Joined:</b> {success_joins}\n"
            f"❌ <b>Failed:</b> {fail_joins}\n\n"
            f"<b>Log:</b>\n<code>{log_tail}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await bot.send_message(
            admin_id,
            f"✅ <b>Global Link Joiner Complete!</b>\n"
            f"Accounts: {total_accounts} | Joined: {success_joins} | Failed: {fail_joins}",
            parse_mode=ParseMode.HTML
        )

async def execute_global_folder_task(admin_id, folder_slugs, accounts, bot):
    """Background task to join folders and clean filters with live progress."""
    total_accounts = len(accounts)
    total_folders = len(folder_slugs)
    accounts_done = 0
    total_joined = 0
    total_failed = 0
    
    from telethon.tl.functions.chatlists import CheckChatlistInviteRequest, JoinChatlistInviteRequest
    from telethon.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest
    from telethon.tl.types import DialogFilterChatlist
    from telethon.tl.types.chatlists import ChatlistInvite, ChatlistInviteAlready
    
    # Send initial status message
    status_msg = await bot.send_message(
        admin_id,
        f"📂 <b>Global Folder Joiner — In Progress</b>\n\n"
        f"📊 Accounts: <code>0/{total_accounts}</code>\n"
        f"📂 Folders: <code>{total_folders}</code>\n"
        f"✅ Joined: <code>0</code> | ❌ Failed: <code>0</code>\n\n"
        f"⏳ Starting...",
        parse_mode=ParseMode.HTML
    )
    
    logs = []
    
    for acc in accounts:
        phone = acc.get('phone_number', '???')
        session_str = acc['session_string']
        acc_joined = 0
        acc_failed = 0
        try:
            async with TelegramClient(StringSession(session_str), TELEGRAM_API_ID, TELEGRAM_API_HASH) as client:
                for slug in folder_slugs:
                    try:
                        # 1. Check and join folder
                        invite = await client(CheckChatlistInviteRequest(slug=slug))
                        
                        peers = []
                        if isinstance(invite, ChatlistInvite):
                            peers = invite.peers
                        elif isinstance(invite, ChatlistInviteAlready):
                            peers = getattr(invite, 'missing_peers', [])
                        
                        if peers:
                            await client(JoinChatlistInviteRequest(slug=slug, peers=peers))
                        
                        # 2. Clean up folder icons
                        await asyncio.sleep(2)
                        filters_list = await client(GetDialogFiltersRequest())
                        for f in filters_list:
                            if isinstance(f, DialogFilterChatlist):
                                try:
                                    await client(UpdateDialogFilterRequest(id=f.id, filter=None))
                                except:
                                    pass
                        
                        acc_joined += 1
                    except Exception as e:
                        acc_failed += 1
                        logger.error(f"Folder join error for +{phone} slug {slug}: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            acc_failed = total_folders
            logger.error(f"Global folder join failed for +{phone}: {e}")

        accounts_done += 1
        total_joined += acc_joined
        total_failed += acc_failed
        logs.append(f"{'✅' if acc_failed == 0 else '⚠️'} +{phone}: {acc_joined} joined, {acc_failed} fail")
        
        # Update status every account
        log_tail = "\n".join(logs[-8:])
        try:
            await status_msg.edit_text(
                f"📂 <b>Global Folder Joiner — In Progress</b>\n\n"
                f"📊 Accounts: <code>{accounts_done}/{total_accounts}</code>\n"
                f"📂 Folders: <code>{total_folders}</code>\n"
                f"✅ Joined: <code>{total_joined}</code> | ❌ Failed: <code>{total_failed}</code>\n\n"
                f"<b>Recent:</b>\n<code>{log_tail}</code>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

    # Final summary
    log_tail = "\n".join(logs[-10:])
    try:
        await status_msg.edit_text(
            f"✅ <b>Global Folder Joiner — Complete!</b>\n\n"
            f"📊 <b>Accounts:</b> {total_accounts}\n"
            f"📂 <b>Folders:</b> {total_folders}\n"
            f"✅ <b>Joined & Cleaned:</b> {total_joined}\n"
            f"❌ <b>Failed:</b> {total_failed}\n\n"
            f"<b>Log:</b>\n<code>{log_tail}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await bot.send_message(
            admin_id,
            f"✅ <b>Global Folder Joiner Complete!</b>\n"
            f"Accounts: {total_accounts} | Joined: {total_joined} | Failed: {total_failed}",
            parse_mode=ParseMode.HTML
        )

async def admin_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /otp - Select an account to retrieve the latest login code."""
    if update.effective_user.id not in ADMIN_IDS: return
    
    accounts = db.get_all_accounts_summary()
    if not accounts:
        await update.message.reply_text("No accounts found in database.")
        return

    mapping = {}
    for idx, acc in enumerate(accounts, 1):
        mapping[idx] = acc['id']
    
    context.user_data['otp_mapping'] = mapping
    context.user_data['awaiting_admin_input'] = 'otp_selection'
    
    msg, reply_markup = get_account_list_page(accounts, 1, "otp", "OTP Retrieval")
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def execute_otp_fetch(update: Update, context: ContextTypes.DEFAULT_TYPE, acc_id: int):
    """Fetch the latest message from Telegram for a specific account."""
    acc = db.get_account_by_id(acc_id)
    if not acc:
        await update.message.reply_text("Account not found.")
        return

    # Pre-validate session before connecting
    session_str = acc.get('session_string', '')
    if not session_str or len(session_str) < 50:
        await update.message.reply_text("❌ Account has invalid session. Cannot fetch OTP.")
        return

    status_msg = await update.message.reply_text(f"🔍 Fetching OTP for <b>+{acc['phone_number']}</b>...", parse_mode=ParseMode.HTML)
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    client = None
    try:
        # Create client with explicit session handling
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        
        # Connect with timeout
        await asyncio.wait_for(client.connect(), timeout=15)
        
        # Check authorization
        if not await client.is_user_authorized():
            await status_msg.edit_text("❌ Session is no longer authorized. Cannot fetch OTP.")
            return
        
        # Try multiple approaches to get Telegram service messages
        messages = None
        service_entity = None
        
        # Method 1: Try getting by ID 777000
        try:
            service_entity = await client.get_entity(777000)
            messages = await client.get_messages(service_entity, limit=5)
        except Exception as e1:
            logger.info(f"Method 1 failed: {e1}")
        
        # Method 2: Try by username 'Telegram' if method 1 failed
        if not messages:
            try:
                service_entity = await client.get_entity("Telegram")
                messages = await client.get_messages(service_entity, limit=5)
            except Exception as e2:
                logger.info(f"Method 2 failed: {e2}")
        
        # Method 3: Try getting from user dialog list
        if not messages:
            try:
                async for dialog in client.iter_dialogs():
                    if dialog.entity.id == 777000 or (hasattr(dialog.entity, 'username') and dialog.entity.username == 'Telegram'):
                        messages = await client.get_messages(dialog.entity, limit=5)
                        break
            except Exception as e3:
                logger.info(f"Method 3 failed: {e3}")
        
        if not messages:
            await status_msg.edit_text("📭 No recent messages found from Telegram service.")
            return
        
        # Find the latest OTP message (look for login codes)
        otp_message = None
        for msg in messages:
            if msg.text and any(keyword in msg.text.lower() for keyword in ['login code', 'code is', 'verification', 'otp']):
                otp_message = msg
                break
        
        if not otp_message:
            # If no OTP found, show the latest message anyway
            otp_message = messages[0]
        
        msg_text = otp_message.text
        msg_time = otp_message.date.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        await status_msg.edit_text(
            f"📨 <b>Latest Telegram Message</b>\n\n"
            f"📱 <b>+{acc['phone_number']}</b>\n"
            f"⏰ <b>{msg_time}</b>\n\n"
            f"<code>{msg_text}</code>\n\n"
            f"<i>💡 Look for 5-digit login codes in the message above.</i>",
            parse_mode=ParseMode.HTML
        )
        
    except asyncio.TimeoutError:
        await status_msg.edit_text("⏰ Connection timeout. Please try again.")
    except (UserDeactivatedError, AuthKeyUnregisteredError) as e:
        logger.warning(f"Account {acc_id} flagged as BANNED/DEACTIVATED: {e}")
        await status_msg.edit_text(f"🚫 Account is banned or deactivated. Cannot fetch OTP.")
    except Exception as e:
        logger.error(f"Error fetching OTP for {acc_id}: {e}")
        if "EOF" in str(e) or "connection" in str(e).lower():
            await status_msg.edit_text("🔌 Connection error. Please try again in a few seconds.")
        elif "session" in str(e).lower() or "auth" in str(e).lower():
            await status_msg.edit_text("❌ Session error. Account may need re-authentication.")
        else:
            await status_msg.edit_text(f"❌ Error fetching OTP: {str(e)[:100]}")
    finally:
        # Always disconnect client
        if client:
            try:
                await client.disconnect()
            except:
                pass

async def admin_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /monitor - Scans and reports the health of account sessions."""
    if update.effective_user.id not in ADMIN_IDS: return
    
    args = context.args
    if not args:
        # If no args, show the account selection list
        accounts = db.get_all_accounts_summary()
        if not accounts:
            await update.message.reply_text("No accounts found in the database.")
            return

        mapping = {idx: acc['id'] for idx, acc in enumerate(accounts, 1)}
        context.user_data['monitor_mapping'] = mapping
        context.user_data['awaiting_admin_input'] = 'monitor_selection'
        
        msg, reply_markup = get_account_list_page(accounts, 1, "monitor", "Session Health Monitor")
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return

    status_msg = await update.message.reply_text("🔍 <b>Scanning Account Health...</b>\n<i>This may take a moment.</i>", parse_mode=ParseMode.HTML)
    
    target_ids = []
    if args[0].lower() == 'global':
        accounts = db.get_all_accounts_summary()
        target_ids = [acc['id'] for acc in accounts]
    else:
        try:
            target_ids = [int(x) for x in args]
        except ValueError:
            await status_msg.edit_text("❌ Invalid account IDs provided.")
            return

    if not target_ids:
        await status_msg.edit_text("❌ No target accounts found.")
        return

    report_lines = []
    total_checked = 0
    good_count = 0
    bad_count = 0
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")

    for i, acc_id in enumerate(target_ids):
        acc = db.get_account_by_id(acc_id)
        if not acc:
            report_lines.append(f"❓ Account ID {acc_id} not found.")
            continue

        total_checked += 1
        phone = acc.get('phone_number', 'N/A')
        display_name = acc.get('display_name', 'No Name')
        status = "..."
        
        # Update status message every 5 accounts
        if i % 5 == 0:
            try:
                await status_msg.edit_text(f"🔍 <b>Scanning Account Health...</b>\n<i>Checked {i}/{len(target_ids)}</i>", parse_mode=ParseMode.HTML)
            except: # Ignore "not modified" errors
                pass

        session_str = acc.get('session_string', '')
        if not session_str or len(session_str) < 50:
            status = "❌ Invalid Session"
            bad_count += 1
            report_lines.append(f"{status} | <code>+{phone}</code> | {display_name}")
            db.update_account(acc_id, is_active=0) # Deactivate bad session
            continue

        client = None
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await asyncio.wait_for(client.connect(), timeout=10)

            if await client.is_user_authorized():
                me = await client.get_me()
                username = f"@{me.username}" if me.username else "No Username"
                status = "✅ Good"
                good_count += 1
                report_lines.append(f"{status} | <code>+{phone}</code> | {display_name} ({username})")
            else:
                status = "❌ Expired Session"
                bad_count += 1
                report_lines.append(f"{status} | <code>+{phone}</code> | {display_name}")
                db.update_account(acc_id, is_active=0) # Deactivate expired session

        except (UserDeactivatedError, AuthKeyUnregisteredError):
            status = "🚫 Banned/Deactivated"
            bad_count += 1
            report_lines.append(f"{status} | <code>+{phone}</code> | {display_name}")
            db.update_account(acc_id, is_active=0) # Deactivate banned session
        except Exception:
            status = "❌ Bad Session"
            bad_count += 1
            report_lines.append(f"{status} | <code>+{phone}</code> | {display_name}")
            db.update_account(acc_id, is_active=0) # Deactivate other bad sessions
        finally:
            if client and client.is_connected():
                await client.disconnect()
        
        await asyncio.sleep(0.2) # Small delay to prevent hitting rate limits

    # Build and send the final report
    final_report = (
        f"<b>🔬 Session Health Report</b>\n\n"
        f"<b>Total Checked:</b> {total_checked}\n"
        f"✅ <b>Good Sessions:</b> {good_count}\n"
        f"❌ <b>Bad/Expired/Banned:</b> {bad_count}\n"
        f"---------------------------------\n"
    )
    
    # Send the report in chunks if it's too long
    for i in range(0, len(report_lines), 50):
        chunk = report_lines[i:i+50]
        report_chunk = "\n".join(chunk)
        if i == 0:
            await status_msg.edit_text(final_report + report_chunk, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(report_chunk, parse_mode=ParseMode.HTML)

    if not report_lines:
        await status_msg.edit_text("No accounts were checked.", parse_mode=ParseMode.HTML)


async def admin_configure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /configure - Bulk configure accounts profile & privacy."""
    if update.effective_user.id not in ADMIN_IDS: return
    
    accounts = db.get_all_accounts_summary()
    if not accounts:
        await update.message.reply_text("No accounts found.")
        return

    mapping = {}
    for idx, acc in enumerate(accounts, 1):
        mapping[idx] = acc['id']
    
    context.user_data['configure_mapping'] = mapping
    context.user_data['awaiting_admin_input'] = 'configure_selection'

    msg, reply_markup = get_account_list_page(accounts, 1, "configure", "Bulk Configuration")
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def handle_configure_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PFP upload during /configure flow."""
    if update.effective_user.id not in ADMIN_IDS: return
    if context.user_data.get('awaiting_admin_input') != 'configure_pfp': return
    
    photo = update.message.photo[-1]
    file = await photo.get_file()
    
    # Save to temp file
    temp_dir = tempfile.gettempdir()
    pfp_path = os.path.join(temp_dir, f"conf_pfp_{update.effective_user.id}.jpg")
    await file.download_to_drive(pfp_path)
    
    context.user_data['configure_pfp_path'] = pfp_path
    context.user_data['awaiting_admin_input'] = 'configure_name_prefix'
    
    await update.message.reply_text("🏷 <b>Step 3/5: Name Prefix</b>\n\nPlease send the <b>Name Prefix</b> (e.g. <code>AIGNCY</code>). Names will be: <i>Prefix | Advert #01</i>", parse_mode=ParseMode.HTML)


async def execute_bulk_configure(context: ContextTypes.DEFAULT_TYPE):
    """Background task to apply configuration to multiple accounts."""
    data = context.job.data
    target_ids = data['target_ids']
    pfp_path = data['pfp_path']
    name_prefix = data['name_prefix']
    user_pattern = data['user_pattern']
    bio = data['bio']
    admin_id = data['admin_id']
    
    API_ID = int(os.getenv("TELEGRAM_API_ID", "21219293"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "cff5d321b676104840cf282a742381e0")
    
    from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest, SetPrivacyRequest
    from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
    from telethon.tl.types import (
        InputPrivacyKeyPhoneNumber, InputPrivacyKeyStatusTimestamp, InputPrivacyKeyChatInvite,
        InputPrivacyKeyPhoneCall, InputPrivacyKeyForwards, InputPrivacyKeyProfilePhoto,
        InputPrivacyKeyAbout, InputPrivacyValueAllowAll, InputPrivacyValueDisallowAll
    )
    from telethon.errors import SessionPasswordNeededError, FloodWaitError, UserDeactivatedError, AuthKeyUnregisteredError

    success_count = 0
    failed_accounts_details = []
    
    for i, acc_id in enumerate(target_ids, 1):
        acc = db.get_account_by_id(acc_id)
        if not acc or not acc.get('session_string'):
            failed_accounts_details.append(f"Account {acc_id}: Session string missing or account not found.")
            continue

        client = None
        try:
            client = TelegramClient(StringSession(acc['session_string']), API_ID, API_HASH)
            await asyncio.wait_for(client.connect(), timeout=15) # Add timeout for connection

            if not await client.is_user_authorized():
                failed_accounts_details.append(f"Account {acc_id}: Session invalid/expired. Marked inactive.")
                db.update_account(acc_id, is_active=0)
                await client.disconnect()
                continue
            
            account_errors = []

            # PHASE 1: PRIVACY
            try:
                privacy_keys = [
                    InputPrivacyKeyStatusTimestamp(),
                    InputPrivacyKeyChatInvite(),
                    InputPrivacyKeyPhoneCall(),
                    InputPrivacyKeyForwards(),
                    InputPrivacyKeyProfilePhoto(),
                    InputPrivacyKeyAbout()
                ]
                for key in privacy_keys:
                    await client(SetPrivacyRequest(key=key, rules=[InputPrivacyValueAllowAll()]))
                
                # Phone Number -> Nobody
                await client(SetPrivacyRequest(key=InputPrivacyKeyPhoneNumber(), rules=[InputPrivacyValueDisallowAll()]))
            except Exception as pe:
                account_errors.append(f"Privacy error: {str(pe)[:100]}")
                logger.error(f"Privacy error for {acc_id}: {pe}")

            # PHASE 2: PFP
            try:
                old_photos = await client.get_profile_photos('me')
                if old_photos: await client(DeletePhotosRequest(id=old_photos))
                if pfp_path and os.path.exists(pfp_path):
                    uploaded = await client.upload_file(pfp_path)
                    await client(UploadProfilePhotoRequest(file=uploaded))
            except Exception as pe:
                account_errors.append(f"PFP error: {str(pe)[:100]}")
                logger.error(f"PFP error for {acc_id}: {pe}")

            # PHASE 3: NAME
            new_first_name = f"{name_prefix} | Advert #{i:02d}"
            try:
                await client(UpdateProfileRequest(first_name=new_first_name, last_name="", about=bio))
                db.update_account(acc_id, display_name=new_first_name)
            except Exception as ne:
                account_errors.append(f"Name/Bio error: {str(ne)[:100]}")
                logger.error(f"Name/Bio error for {acc_id}: {ne}")

            # PHASE 4: USERNAME
            try:
                new_username = f"{user_pattern}{i}"
                await client(UpdateUsernameRequest(username=new_username))
            except Exception as ue:
                account_errors.append(f"Username error: {str(ue)[:100]}")
                logger.error(f"Username error for {acc_id}: {ue}")

            if not account_errors:
                success_count += 1
            else:
                failed_accounts_details.append(f"Account {acc_id} (+{acc.get('phone_number', 'N/A')}): {'; '.join(account_errors)}")
            
            if i < len(target_ids):
                await asyncio.sleep(random.randint(5, 15)) # Delay between accounts

        except asyncio.TimeoutError:
            failed_accounts_details.append(f"Account {acc_id} (+{acc.get('phone_number', 'N/A')}): Connection timeout.")
            db.update_account(acc_id, is_active=0) # Mark as inactive on timeout
        except (UserDeactivatedError, AuthKeyUnregisteredError) as e:
            failed_accounts_details.append(f"Account {acc_id} (+{acc.get('phone_number', 'N/A')}): Banned/Deactivated. Marked inactive. ({str(e)[:100]})")
            db.update_account(acc_id, is_active=0)
        except Exception as e:
            failed_accounts_details.append(f"Account {acc_id} (+{acc.get('phone_number', 'N/A')}): Unexpected error - {str(e)[:100]}.")
        finally:
            if client and client.is_connected():
                await client.disconnect()

    # Final notification
    final_msg = (
        f"✅ <b>Bulk Configuration Complete</b>\n\n"
        f"📈 <b>Success:</b> {success_count}\n"
        f"❌ <b>Failed:</b> {len(failed_accounts_details)}\n\n"
    )
    if failed_accounts_details:
        final_msg += "<b>Details of Failed Accounts:</b>\n"
        final_msg += "\n".join(failed_accounts_details[:10]) # Limit to first 10 errors for brevity
        if len(failed_accounts_details) > 10:
            final_msg += f"\n... and {len(failed_accounts_details) - 10} more."
    
    try: await context.bot.send_message(admin_id, final_msg, parse_mode=ParseMode.HTML)
    except Exception as e: logger.error(f"Error sending final config report: {e}")
    
    # Cleanup PFP if any
    if pfp_path and os.path.exists(pfp_path):
        try: os.remove(pfp_path)
        except: pass
