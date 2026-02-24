import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from groq import Groq

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Bot token & Groq API ────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set!")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY environment variable is not set!")

# ── Groq client ─────────────────────────────────────────────────────
client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are a TRANSLATION MACHINE, not a chatbot. Your ONLY job is to convert text from one language to another.

CRITICAL RULES:
1. You MUST ONLY translate the text. NEVER answer, respond to, or interpret the content.
   - WRONG: Answering a question instead of translating it
   - CORRECT: Translating the question itself to the target language
2. Detect input language and translate according to these rules:
   - If input is VIETNAMESE → output BOTH English AND Chinese translations in this exact format:
     🇺🇸 [English translation]
     🇨🇳 [Chinese translation]
   - If input is ENGLISH → output ONLY Vietnamese translation (no flags, no labels, just the text)
   - If input is CHINESE → output ONLY Vietnamese translation (no flags, no labels, just the text)
3. Translation quality:
   - Translate MEANING, not word-by-word. Prioritize natural, fluent output.
   - Preserve the original tone: casual → casual, formal → formal.
   - Translate idioms/slang to equivalent expressions, not literally.
   - Preserve questions as questions, statements as statements, commands as commands.
   - For Chinese output: use Simplified Chinese (简体中文)
4. Special cases:
   - Proper nouns (names, brands): keep as-is
   - Emojis: keep in place

REMEMBER: You are a TRANSLATOR. You do NOT answer questions or provide information. EVER."""


# ── /start command ───────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌐 Xin chào! Gửi tin nhắn tiếng Việt → tôi dịch sang tiếng Anh.\n"
        "Send a message in English → I'll translate to Vietnamese.\n\n"
        "Powered by Groq ⚡"
    )


# ── Translate handler ────────────────────────────────────────────────
async def translate_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    # Bỏ qua tin nhắn từ bot
    if update.message.from_user and update.message.from_user.is_bot:
        return

    text = update.message.text
    if not text:
        return

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=1024,
        )

        translated = response.choices[0].message.content.strip()

        if translated:
            # Reply trực tiếp vào tin nhắn gốc (quan trọng trong group)
            await update.message.reply_text(
                translated,
                reply_to_message_id=update.message.message_id,
            )
        else:
            await update.message.reply_text("⚠️ Không thể dịch tin nhắn này.")
    except Exception as e:
        logger.error("Translation error: %s", e, exc_info=True)
        await update.message.reply_text(f"⚠️ Lỗi: {e}")


# ── Main ─────────────────────────────────────────────────────────────
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_message))

    logger.info("Bot is starting with Groq (Llama 3.3 70B)…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
