"""
Message Collector Bot - Captures formatted messages with premium emojis
Clients can send their ad messages with all formatting, which gets stored for campaigns.
"""

import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.constants import ParseMode
import sqlite3
from datetime import datetime

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required to run message_collector_bot")

# Conversation states
WAITING_CLIENT_ID, WAITING_MESSAGE, WAITING_TEMPLATE_NAME = range(3)

# Database path
DB_PATH = os.getenv("DATABASE_PATH", "eyeconbumps_webapp.db")

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_message_templates_table():
    """Create message_templates table if not exists."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS message_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            name TEXT NOT NULL,
            text_content TEXT NOT NULL,
            entities_json TEXT,
            has_media INTEGER DEFAULT 0,
            media_file_id TEXT,
            media_type TEXT,
            telegram_user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Message templates table initialized")

def entities_to_json(entities):
    """Convert Telegram entities to JSON for storage."""
    if not entities:
        return None
    
    entities_list = []
    for entity in entities:
        entity_dict = {
            "type": entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
            "offset": entity.offset,
            "length": entity.length
        }
        
        # Handle special entity attributes
        if entity.url:
            entity_dict["url"] = entity.url
        if entity.user:
            entity_dict["user_id"] = entity.user.id
        if hasattr(entity, 'custom_emoji_id') and entity.custom_emoji_id:
            entity_dict["custom_emoji_id"] = entity.custom_emoji_id
        if entity.language:
            entity_dict["language"] = entity.language
            
        entities_list.append(entity_dict)
    
    return json.dumps(entities_list)

def save_message_template(client_id: int, name: str, text: str, entities_json: str, 
                          telegram_user_id: int, media_file_id: str = None, media_type: str = None):
    """Save a message template to database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO message_templates (client_id, name, text_content, entities_json, 
                                       has_media, media_file_id, media_type, telegram_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (client_id, name, text, entities_json, 
          1 if media_file_id else 0, media_file_id, media_type, telegram_user_id))
    template_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return template_id

def get_client_by_id(client_id: int):
    """Get client from database by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None

def get_client_by_token(token: str):
    """Get client from database by token."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE access_token = ?", (token.strip().upper(),))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None

def get_template_count(client_id: int):
    """Get number of templates for a client."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM message_templates WHERE client_id = ?", (client_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    keyboard = [
        [InlineKeyboardButton("Add New Message", callback_data="add_message")],
        [InlineKeyboardButton("View My Templates", callback_data="view_templates")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """
<b>EyeconBumps Message Collector</b>

This bot helps you save your ad messages with all formatting:
- Bold, italic, underline styling
- Premium/custom emojis
- Links and mentions
- Everything preserved exactly!

<b>How to use:</b>
1. Click "Add New Message"
2. Enter your Client Token
3. Send your formatted ad message
4. Give it a name
5. Use it in campaigns!

Your formatting will be preserved exactly as you send it.
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def add_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Add Message button."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "<b>Step 1/3: Enter Client Token</b>\n\n"
        "Please send your Client Token.\n"
        "(You can find this in the EyeconBumps web panel under your client settings)",
        parse_mode=ParseMode.HTML
    )
    return WAITING_CLIENT_ID

async def receive_client_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle client token input."""
    token = update.message.text.strip()
    
    if len(token) < 3:
        await update.message.reply_text(
            "Invalid Client Token. Please check your token and try again.",
            parse_mode=ParseMode.HTML
        )
        return WAITING_CLIENT_ID
    
    # Verify client exists by token
    client = get_client_by_token(token)
    if not client:
        await update.message.reply_text(
            "Client not found. Please check your Client Token and try again.",
            parse_mode=ParseMode.HTML
        )
        return WAITING_CLIENT_ID
    
    # Store client ID in context
    context.user_data['client_id'] = client['id']
    context.user_data['client_name'] = client.get('name', 'Unknown')
    
    await update.message.reply_text(
        f"<b>Client verified: {client.get('name')}</b>\n\n"
        f"<b>Step 2/3: Send Your Ad Message</b>\n\n"
        f"Now send me your ad message with all the formatting you want:\n"
        f"- Use bold, italic, underline\n"
        f"- Add premium/custom emojis\n"
        f"- Include links and mentions\n\n"
        f"<i>The message will be saved exactly as you format it!</i>",
        parse_mode=ParseMode.HTML
    )
    return WAITING_MESSAGE

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the formatted message."""
    message = update.message
    
    # Extract text and entities
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities
    
    # Convert entities to JSON
    entities_json = entities_to_json(entities)
    
    # Check for media
    media_file_id = None
    media_type = None
    
    if message.photo:
        media_file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_file_id = message.video.file_id
        media_type = "video"
    elif message.animation:
        media_file_id = message.animation.file_id
        media_type = "animation"
    elif message.document:
        media_file_id = message.document.file_id
        media_type = "document"
    
    # Store in context
    context.user_data['message_text'] = text
    context.user_data['entities_json'] = entities_json
    context.user_data['media_file_id'] = media_file_id
    context.user_data['media_type'] = media_type
    
    # Count entities
    entity_count = len(entities) if entities else 0
    custom_emoji_count = sum(1 for e in (entities or []) if hasattr(e, 'custom_emoji_id') and e.custom_emoji_id)
    
    # Show preview
    preview_info = f"<b>Message captured!</b>\n\n"
    preview_info += f"Characters: {len(text)}\n"
    preview_info += f"Formatting entities: {entity_count}\n"
    if custom_emoji_count > 0:
        preview_info += f"Premium emojis: {custom_emoji_count}\n"
    if media_file_id:
        preview_info += f"Media: {media_type}\n"
    
    preview_info += f"\n<b>Step 3/3: Name Your Template</b>\n\n"
    preview_info += f"Give this message a name (e.g., 'Main Ad v1', 'Promo Message'):"
    
    await update.message.reply_text(preview_info, parse_mode=ParseMode.HTML)
    return WAITING_TEMPLATE_NAME

async def receive_template_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the template with the given name."""
    name = update.message.text.strip()
    
    if len(name) < 2:
        await update.message.reply_text("Name too short. Please enter at least 2 characters.")
        return WAITING_TEMPLATE_NAME
    
    # Save to database
    client_id = context.user_data.get('client_id')
    text = context.user_data.get('message_text')
    entities_json = context.user_data.get('entities_json')
    media_file_id = context.user_data.get('media_file_id')
    media_type = context.user_data.get('media_type')
    telegram_user_id = update.effective_user.id
    
    template_id = save_message_template(
        client_id=client_id,
        name=name,
        text=text,
        entities_json=entities_json,
        telegram_user_id=telegram_user_id,
        media_file_id=media_file_id,
        media_type=media_type
    )
    
    # Get total templates count
    template_count = get_template_count(client_id)
    
    await update.message.reply_text(
        f"<b>Template Saved!</b>\n\n"
        f"Name: {name}\n"
        f"Template ID: #{template_id}\n"
        f"Client: {context.user_data.get('client_name')}\n\n"
        f"Total templates for this client: {template_count}\n\n"
        f"<i>You can now use this template in your campaigns from the web panel!</i>\n\n"
        f"Use /start to add another message.",
        parse_mode=ParseMode.HTML
    )
    
    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def view_templates_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's templates."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Send your Client Token to view your saved templates:",
        parse_mode=ParseMode.HTML
    )
    context.user_data['viewing_templates'] = True
    return WAITING_CLIENT_ID

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation."""
    context.user_data.clear()
    await update.message.reply_text(
        "Cancelled. Use /start to begin again.",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

def main():
    """Run the bot."""
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
    
    # Start polling
    logger.info("Message Collector Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
