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

The user's message starts with a [DETECTED LANGUAGE: ...] tag. ALWAYS trust and follow this tag to determine the input language. Translate the text AFTER the tag (do NOT include the tag in your output).

CRITICAL RULES:

1. NEVER answer, respond to, or interpret the content. ONLY translate.

2. LANGUAGE DETECTION — The [DETECTED LANGUAGE: ...] tag tells you the language. Use it:

   Step A: Does the text contain ANY Vietnamese diacritics (ă, â, đ, ê, ô, ơ, ư, à, á, ả, ã, ạ, è, é, ẻ, ẽ, ẹ, ì, í, ỉ, ĩ, ị, ò, ó, ỏ, õ, ọ, ù, ú, ủ, ũ, ụ, ỳ, ý, ỷ, ỹ, ỵ, etc.)?
   → YES → It is VIETNAMESE. Go to Rule 3a. (Even ONE diacritic = Vietnamese!)
   
   Step B: Does the text contain Chinese characters (汉字)?
   → YES → It is CHINESE. Go to Rule 3c.
   
   Step C: Otherwise → It is ENGLISH. Go to Rule 3b.

   EXAMPLES to clarify:
   - "Tôi muốn update cái app này" → VIETNAMESE (diacritics: ô, ậ, à)
   - "Cho tôi hỏi cái deadline là khi nào?" → VIETNAMESE
   - "Em đang làm project về AI" → VIETNAMESE
   - "gửi tôi menu" → VIETNAMESE (has "ử" = Vietnamese diacritic!)
   - "gửi link cho tôi" → VIETNAMESE (has "ử", "ô" = Vietnamese!)
   - "cái này đẹp quá" → VIETNAMESE
   - "give me a link" → ENGLISH (zero Vietnamese diacritics)
   - "How are you doing today?" → ENGLISH
   - "I want to update this app" → ENGLISH
   - "Send me the menu" → ENGLISH
   - "What time is it?" → ENGLISH
   - "你好，今天天气怎么样？" → CHINESE
   - "给我一个链接" → CHINESE
   - "我想更新这个应用" → CHINESE

3. TRANSLATION RULES:

   3a. Input is VIETNAMESE → Output BOTH English AND Chinese:
       🇺🇸 [English translation]
       🇨🇳 [Chinese translation]

   3b. Input is ENGLISH → Output ONLY Vietnamese:
       🇻🇳 [Vietnamese translation]

   3c. Input is CHINESE → Output ONLY Vietnamese:
       🇻🇳 [Vietnamese translation]

4. Translation quality:
   - Translate MEANING, not word-by-word. Prioritize natural, fluent output.
   - Preserve the original tone: casual → casual, formal → formal.
   - Translate idioms/slang to equivalent expressions, not literally.
   - For Chinese output: use Simplified Chinese (简体中文)

5. Special cases:
   - Proper nouns (names, brands): keep as-is
   - Emojis: keep in place

REMEMBER: You are a TRANSLATOR. You do NOT answer questions. EVER."""


import re


# ── Language detection helper ────────────────────────────────────────
# Vietnamese diacritics regex (unique to Vietnamese, not found in other Latin-script languages)
_VIET_PATTERN = re.compile(
    r'[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ'
    r'ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]'
)

# CJK Unified Ideographs range
_CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')


def detect_language(text: str) -> str:
    """Detect language using character analysis. Returns 'VIETNAMESE', 'CHINESE', or 'ENGLISH'."""
    if _VIET_PATTERN.search(text):
        return "VIETNAMESE"
    if _CJK_PATTERN.search(text):
        return "CHINESE"
    return "ENGLISH"


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

    # Detect language via code (reliable) and add hint for the LLM
    lang_hint = detect_language(text)
    user_content = f"[DETECTED LANGUAGE: {lang_hint}]\n{text}"

    # Show "typing..." indicator while processing
    await update.message.chat.send_action("typing")

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_tokens=1024,
                timeout=15,
            )

            translated = response.choices[0].message.content.strip()

            if translated:
                await update.message.reply_text(
                    translated,
                    reply_to_message_id=update.message.message_id,
                )
            else:
                await update.message.reply_text("⚠️ Không thể dịch tin nhắn này.")
            return  # Success, exit

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning("Attempt %d failed, retrying: %s", attempt + 1, e)
                await update.message.chat.send_action("typing")
                continue
            logger.error("Translation error: %s", e, exc_info=True)
            await update.message.reply_text("⚠️ Bot đang quá tải, vui lòng thử lại sau.")


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
