# Translate Bot 🌐

Bot Telegram dịch tự động Anh ↔ Việt.

- Gửi tiếng Việt → nhận lại tiếng Anh
- Gửi tiếng Anh → nhận lại tiếng Việt

## Setup

1. Tạo bot mới qua [@BotFather](https://t.me/BotFather) và lấy token.

2. Cài dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variable:
   ```bash
   export BOT_TOKEN="your-bot-token-here"
   ```

4. Chạy bot:
   ```bash
   python bot.py
   ```

## Cách hoạt động

- Bot sử dụng **langdetect** để nhận diện ngôn ngữ đầu vào.
- Nếu là tiếng Việt → dịch sang tiếng Anh bằng Google Translate.
- Nếu không phải tiếng Việt → dịch sang tiếng Việt.
- Chỉ trả về câu đã dịch, không có gì thêm.
