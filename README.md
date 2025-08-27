# Instagram Username Swap Telegram Bot

This is a Python Telegram bot that helps users attempt Instagram username swaps. It uses the pyTelegramBotAPI library and interacts with Instagram via session IDs. The bot enforces daily swap limits, referral tracking, and requires users to join a specified Telegram channel before use.

## Features
- Force users to join a Telegram channel before using the bot
- Daily swap limit per user
- Referral system with tracking
- Admin broadcast and notifications
- Instagram session validation and username swap logic

## Setup Instructions

### 1. Clone the Repository
```sh
git clone https://github.com/afflictedvivek/instagram-username-swap.git
cd instagram-username-swap
```

### 2. Install Dependencies
Make sure you have Python 3.7+ installed. Then install required packages:
```sh
pip install pyTelegramBotAPI requests
```

### 3. Configure the Bot
Edit `botfinal.py` and replace the following placeholders with your own values:
- `<YOUR_BOT_TOKEN>`: Your Telegram bot token
- `@yourchannel`: Your Telegram channel username
- `123456789`: Your Telegram user ID(s) for admin
- `https://yourhelplink.com`: Your help link (optional)
- `@yourbot`: Your bot signature (optional)

### 4. Run the Bot
```sh
python botfinal.py
```

### 5. Usage
- Start the bot in Telegram with `/start`
- Follow instructions to join the required channel
- Use `/swap` to begin the Instagram username swap process
- Use `/refer` to get your referral link
- Use `/stats` to view your daily usage and referrals
- Use `/do_swap` to execute the swap after setting sessions
- Admins can use `/broadcast <message>` to send a message to all users

### 6. Database
The bot uses a local SQLite database (`swapbot.db`) to store user, referral, and session data. No setup required; it will be created automatically.

## Notes
- This bot is for educational purposes only. Use responsibly and respect Instagram's terms of service.
- You must provide valid Instagram session IDs for the swap to work.
- The bot does not store passwords or sensitive information, only session IDs and basic user data.

## License
MIT
