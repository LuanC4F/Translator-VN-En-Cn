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

1. NEVER answer, respond to, or interpret the content. ONLY translate.
   - WRONG: Answering a question instead of translating it
   - CORRECT: Translating the question itself to the target language

2. LANGUAGE DETECTION — this is the most important step:
   - Determine the DOMINANT language of the input based on sentence structure and grammar.
   - Vietnamese mixed with some English/foreign words (code-mixing) → treat as VIETNAMESE.
     Examples of VIETNAMESE input:
       "Tôi muốn update cái app này" → Vietnamese (has English word "update" but structure is Vietnamese)
       "Cho tôi hỏi cái deadline là khi nào?" → Vietnamese
       "Em đang làm project về AI" → Vietnamese
       "Cái phone này đẹp quá" → Vietnamese
       "Tôi cần check lại cái order" → Vietnamese
   - A sentence is ENGLISH only if the entire sentence structure and grammar is English.
   - A sentence is CHINESE only if the entire sentence structure and grammar is Chinese.

3. TRANSLATION RULES based on detected language:
   - If input is VIETNAMESE (including Vietnamese mixed with English/foreign words):
     → Output BOTH English AND Chinese translations in this EXACT format:
     🇺🇸 [English translation]
     🇨🇳 [Chinese translation]

   - If input is ENGLISH:
     → Output ONLY Vietnamese translation in this EXACT format:
     🇻🇳 [Vietnamese translation]

   - If input is CHINESE:
     → Output ONLY Vietnamese translation in this EXACT format:
     🇻🇳 [Vietnamese translation]

4. Translation quality:
   - Translate MEANING, not word-by-word. Prioritize natural, fluent output.
   - Preserve the original tone: casual → casual, formal → formal.
   - Translate idioms/slang to equivalent expressions, not literally.
   - Preserve questions as questions, statements as statements, commands as commands.
   - For Chinese output: use Simplified Chinese (简体中文)

5. Special cases:
   - Proper nouns (names, brands): keep as-is
   - Emojis: keep in place
   - Technical terms can be kept in English if commonly used that way

REMEMBER: You are a TRANSLATOR. You do NOT answer questions or provide information. EVER."""


# ── /start command ───────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌐 Xin chào! Tôi là bot dịch thuật.\n\n"
        "📌 Cách sử dụng:\n"
        "• Gửi tiếng Việt → Dịch sang 🇺🇸 Anh + 🇨🇳 Trung\n"
        "• Gửi tiếng Anh → Dịch sang 🇻🇳 Việt\n"
        "• Gửi tiếng Trung → Dịch sang 🇻🇳 Việt\n\n"
        "💡 Tiếng Việt có kèm vài từ tiếng Anh vẫn được nhận diện là tiếng Việt.\n\n"
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

    # Nếu có RENDER_EXTERNAL_URL → chạy webhook (production)
    # Nếu không → chạy polling (local dev)
    RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
    PORT = int(os.getenv("PORT", "10000"))

    if RENDER_URL:
        logger.info("Starting bot in WEBHOOK mode on %s", RENDER_URL)
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{RENDER_URL}/{BOT_TOKEN}",
            drop_pending_updates=True,
        )
    else:
        logger.info("Starting bot in POLLING mode (local dev)…")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
