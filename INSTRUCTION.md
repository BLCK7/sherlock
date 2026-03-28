# 📖 Complete Installation & Usage Guide

## 📋 Table of Contents
1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Bot](#running-the-bot)
5. [Enabling Telegram Business Mode](#enabling-telegram-business-mode)
6. [Using the Web Dashboard](#using-the-web-dashboard)
7. [Bot Commands](#bot-commands)
8. [Hosting Options](#hosting-options)
9. [Troubleshooting](#troubleshooting)

---

## 🖥 System Requirements

- **Python**: 3.10 or later (Python 3.12 recommended)
- **Operating System**: Windows, Linux, or macOS
- **RAM**: Minimum 512MB (1GB+ recommended)
- **Storage**: 500MB+ for media cache
- **Internet**: Stable connection required

---

## 📦 Installation

### Step 1: Install Python
Download and install Python from [python.org](https://www.python.org/downloads/)

**Windows users**: Make sure to check "Add Python to PATH" during installation

### Step 2: Install Required Libraries
Open your terminal/command prompt and run:

```bash
pip install "python-telegram-bot>=22.0" telethon flask
```

If you encounter permission errors, try:
```bash
pip install --user "python-telegram-bot>=22.0" telethon flask
```

### Step 3: Download the Bot Files
Download all files to a folder:
- `sherlock.py` (main bot script)
- `README.md` (documentation)
- `INSTRUCTION.md` (this file)

---

## ⚙️ Configuration

### Step 1: Get Your Bot Token
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Admin ID
1. Search for `@userinfobot` on Telegram
2. Send `/start` to the bot
3. Copy your user ID (a number like: `123456789`)

### Step 3: Get API Credentials (Optional but Recommended)
These are needed for `/story` and `/get` commands:

1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click on "API development tools"
4. Create an application (any name/description)
5. Copy your `api_id` (integer) and `api_hash` (string)

### Step 4: Edit sherlock.py
Open `sherlock.py` in a text editor and fill in the configuration section at the top:

```python
BOT_TOKEN    = "YOUR_BOT_TOKEN_HERE"
ADMIN_ID     = YOUR_ADMIN_ID_HERE
API_ID       = YOUR_API_ID_HERE      # Optional
API_HASH     = "YOUR_API_HASH_HERE"  # Optional
WEB_PORT     = 5000                  # Dashboard port
CACHE_TTL    = 7                     # Days to keep messages
```

**Example:**
```python
BOT_TOKEN    = "8420281985:AAF5SwhWg5qK9c2b22Hc__v6ylmlS_kENU8"
ADMIN_ID     = 5982232938
API_ID       = 12345678
API_HASH     = "abcdef1234567890abcdef1234567890"
WEB_PORT     = 5000
CACHE_TTL    = 7
```

---

## 🚀 Running the Bot

### On Windows:
1. Open Command Prompt or PowerShell
2. Navigate to the bot folder:
   ```bash
   cd C:\path\to\bot\folder
   ```
3. Run the bot:
   ```bash
   python sherlock.py
   ```

### On Linux/macOS:
1. Open Terminal
2. Navigate to the bot folder:
   ```bash
   cd /path/to/bot/folder
   ```
3. Run the bot:
   ```bash
   python3 sherlock.py
   ```

### First Run with Telethon (if API_ID/API_HASH are set):
- The bot will ask for your phone number
- Enter it in international format: `+1234567890`
- Enter the verification code sent to your Telegram
- A `story_session.session` file will be created
- Future runs won't ask for this again

### Expected Output:
```
2024-03-26 10:30:15 | INFO     | Database initialised.
2024-03-26 10:30:16 | INFO     | Telethon started as: YourName (@yourusername)
2024-03-26 10:30:16 | INFO     | Web dashboard running at http://localhost:5000
2024-03-26 10:30:17 | INFO     | Bot is running. Press Ctrl+C to stop.
```

---

## 📱 Enabling Telegram Business Mode

### Step 1: Enable Business Bot in BotFather
1. Open `@BotFather` on Telegram
2. Send `/mybots`
3. Select your bot
4. Go to **Bot Settings** → **Business Bot**
5. Toggle it **ON**

### Step 2: Connect Bot to Your Business Account
1. Open Telegram mobile app (iOS or Android)
2. Go to **Settings** → **Telegram Business** → **Chatbot**
3. Search for your bot's `@username`
4. Select it
5. Choose which chats the bot can access:
   - **Recommended**: Select "All chats" for full monitoring
   - Or select specific chats only
6. Tap **Save**

### Step 3: Verify Connection
- Send a test message in any business chat
- Check the bot logs for: `Cached msg id=...`
- Open the dashboard at `http://localhost:5000`
- You should see the account and message appear

---

## 🌐 Using the Web Dashboard

### Accessing the Dashboard
1. Make sure the bot is running
2. Open your web browser
3. Go to: `http://localhost:5000`
4. Enter password: `a1234`
5. Click "Unlock"

### Dashboard Password
The default password is `a1234`. To change it:
1. Open `sherlock.py`
2. Find the line: `const CORRECT_PASSWORD = 'a1234';`
3. Change `a1234` to your desired password
4. Save and restart the bot

### Dashboard Structure

#### Level 1: Accounts View
- Shows all business accounts connected to your bot
- Each card displays:
  - Account name and ID
  - Total messages
  - Number of chats
  - Deleted/edited/media counts
- Click any account to view its chats

#### Level 2: Chats View
- Shows all chats for the selected account
- Each card displays:
  - Chat name and ID
  - Last message preview
  - Message count
  - Deleted/edited counts
- Click "← Back" to return to accounts
- Click any chat to view messages

#### Level 3: Messages View
- Shows all messages in the selected chat
- Features:
  - Search messages by text
  - Inline media playback (photos, videos, audio)
  - Color-coded messages:
    - Blue border: Normal message
    - Red background: Deleted message
    - Yellow background: Edited message
    - Green border: Media message
  - Shows original text for edited messages
  - Displays time remaining before auto-deletion
- Click "← Back" to return to chats

### Dashboard Features

#### Auto-Refresh
- Dashboard updates every 5 seconds automatically
- No need to manually refresh the page

#### Media Playback
- **Photos**: Click to view full size in lightbox
- **Videos/GIFs**: Play inline with controls
- **Voice Messages**: Play inline with audio player
- **Stickers**: Display inline (animated stickers auto-play)

#### Statistics Bar
Always visible at the top showing:
- Total accounts
- Total messages
- Total chats
- Deleted messages count
- Edited messages count
- Media files on disk

---

## 🤖 Bot Commands

All commands are admin-only (only work for the user ID set in `ADMIN_ID`).

### `/start`
- Registers the user in the database
- Anyone can use this command
- Used for broadcast feature

### `/admin`
- Shows the admin menu
- Lists all available commands
- Displays dashboard URL

### `/stats`
- Shows bot statistics:
  - Total registered users
  - Cached messages
  - Media files count
  - Message TTL setting
  - Dashboard URL

### `/ad [message]`
- Broadcasts a message to all users who have started the bot
- Example: `/ad Hello everyone! New update available.`
- Shows delivery report (delivered/failed)
- Uses 0.05s delay between sends to avoid flood limits

### `/get`
- Reply to any message with `/get` to save its media
- Works for:
  - Regular photos and videos
  - One-time/view-once photos (requires API_ID/API_HASH)
  - Documents and animations
- Sends the saved media to your admin DM

### `/story [@username or user_id]`
- Downloads all active stories from a user
- Examples:
  - `/story @username`
  - `/story 123456789`
- Requires API_ID and API_HASH
- Sends each story to your admin DM

---

## 🌍 Hosting Options

### Option 1: Local Computer (Easiest)
**Pros:**
- Free
- Full control
- Easy to set up

**Cons:**
- Computer must stay on 24/7
- Uses your internet connection
- Not accessible from outside your network

**Setup:**
1. Follow the installation steps above
2. Keep the terminal window open
3. Access dashboard at `http://localhost:5000`

---

### Option 2: VPS (Virtual Private Server) - Recommended
**Pros:**
- Runs 24/7
- Professional hosting
- Can access dashboard from anywhere (with proper security)

**Cons:**
- Costs $3-10/month
- Requires basic Linux knowledge

**Recommended Providers:**
- DigitalOcean (from $4/month)
- Vultr (from $2.50/month)
- Linode (from $5/month)
- Hetzner (from €3/month)

**Setup Steps:**

1. **Create a VPS:**
   - Choose Ubuntu 22.04 or 24.04
   - Minimum: 1GB RAM, 1 CPU core

2. **Connect via SSH:**
   ```bash
   ssh root@your_server_ip
   ```

3. **Update system:**
   ```bash
   apt update && apt upgrade -y
   ```

4. **Install Python and pip:**
   ```bash
   apt install python3 python3-pip -y
   ```

5. **Install required libraries:**
   ```bash
   pip3 install "python-telegram-bot>=22.0" telethon flask
   ```

6. **Upload bot files:**
   - Use SFTP client (FileZilla, WinSCP)
   - Or use `scp` command:
     ```bash
     scp sherlock.py root@your_server_ip:/root/
     ```

7. **Edit configuration:**
   ```bash
   nano sherlock.py
   ```
   - Fill in BOT_TOKEN, ADMIN_ID, etc.
   - Press Ctrl+X, then Y, then Enter to save

8. **Run the bot:**
   ```bash
   python3 sherlock.py
   ```

9. **Keep bot running after logout (using screen):**
   ```bash
   apt install screen -y
   screen -S telegram_bot
   python3 sherlock.py
   ```
   - Press Ctrl+A then D to detach
   - Reconnect anytime with: `screen -r telegram_bot`

10. **Access dashboard remotely:**
    - Option A: SSH tunnel (secure):
      ```bash
      ssh -L 5000:localhost:5000 root@your_server_ip
      ```
      Then open `http://localhost:5000` in your browser
    
    - Option B: Change WEB_PORT to public (less secure):
      - Edit sherlock.py: `WEB_PORT = 5000`
      - Open firewall: `ufw allow 5000`
      - Access: `http://your_server_ip:5000`
      - **Warning**: Anyone can access if they know the IP!

---

### Option 3: Raspberry Pi
**Pros:**
- One-time cost (~$35-75)
- Low power consumption
- Runs 24/7 at home

**Cons:**
- Initial hardware cost
- Requires setup

**Setup:**
1. Install Raspberry Pi OS
2. Follow the Linux/macOS installation steps
3. Keep it plugged in and connected to internet

---

### Option 4: Cloud Platforms (Free Tier)
Some platforms offer free tiers:

**Google Cloud Platform:**
- Free tier: e2-micro instance
- 1GB RAM, limited CPU
- Follow VPS setup steps

**Oracle Cloud:**
- Always free tier
- 1GB RAM ARM instance
- Follow VPS setup steps

**AWS Free Tier:**
- t2.micro instance
- Free for 12 months
- Follow VPS setup steps

---

## 🔒 Security Recommendations

### Dashboard Security
1. **Change default password:**
   - Edit `CORRECT_PASSWORD` in sherlock.py
   - Use a strong password

2. **Don't expose to internet without protection:**
   - Use SSH tunnel for remote access
   - Or add nginx with authentication
   - Or use VPN

3. **Keep bot token private:**
   - Never share your BOT_TOKEN
   - Don't commit it to public repositories

### VPS Security
1. **Use SSH keys instead of passwords**
2. **Enable firewall:**
   ```bash
   ufw enable
   ufw allow 22
   ufw allow 5000  # Only if needed
   ```
3. **Keep system updated:**
   ```bash
   apt update && apt upgrade -y
   ```

---

## 🔧 Troubleshooting

### Bot doesn't start
**Error: `ModuleNotFoundError: No module named 'telegram'`**
- Solution: Install dependencies:
  ```bash
  pip install "python-telegram-bot>=22.0" telethon flask
  ```

**Error: `telegram.error.InvalidToken`**
- Solution: Check your BOT_TOKEN in sherlock.py
- Make sure it's correct and in quotes

### Dashboard not accessible
**Can't open http://localhost:5000**
- Check if bot is running
- Check if port 5000 is already in use
- Try changing WEB_PORT to 5001 or 8080

**Dashboard shows "Loading..." forever**
- Check browser console for errors (F12)
- Make sure bot is running
- Try refreshing the page

### Messages not appearing
**Business messages not being logged**
- Verify Business Bot is enabled in BotFather
- Check if bot is connected in Telegram Business settings
- Make sure you selected "All chats" or specific chats
- Check bot logs for errors

### Telethon issues
**Error: `API_ID or API_HASH is invalid`**
- Double-check your API_ID and API_HASH from my.telegram.org
- API_ID should be a number (no quotes)
- API_HASH should be a string (in quotes)

**Phone number verification fails**
- Use international format: `+1234567890`
- Make sure you have access to that phone number
- Check for typos

### Media not playing
**Photos/videos not loading**
- Check if media_cache folder exists
- Check if files are in media_cache folder
- Check browser console for 404 errors
- Make sure bot has write permissions

### Database issues
**Error: `database is locked`**
- Close any SQLite browser tools
- Restart the bot
- Check file permissions

---

## 📞 Support

### Getting Help
1. Check this instruction file first
2. Review the README.md file
3. Check bot logs for error messages
4. Search for the error message online

### Common Log Messages
- `INFO | Bot is running` - Bot started successfully
- `INFO | Cached msg id=...` - Message saved successfully
- `WARNING | Media cache failed` - Media download failed (not critical)
- `ERROR | ...` - Something went wrong, check the error message

---

## 🔄 Updating the Bot

1. Stop the bot (Ctrl+C)
2. Backup your database:
   ```bash
   cp business_bot.db business_bot.db.backup
   ```
3. Replace sherlock.py with the new version
4. Keep your configuration values (BOT_TOKEN, ADMIN_ID, etc.)
5. Restart the bot

---

## 📝 Notes

- Messages are automatically deleted after 7 days (configurable via CACHE_TTL)
- Media files are NOT automatically deleted (only database records)
- The bot only works with Telegram Business accounts
- Dashboard password is stored in plain text in the JavaScript code
- For production use, consider adding proper authentication

---

## ✅ Quick Start Checklist

- [ ] Python 3.10+ installed
- [ ] Dependencies installed (`pip install ...`)
- [ ] Bot created via @BotFather
- [ ] BOT_TOKEN configured in sherlock.py
- [ ] ADMIN_ID configured in sherlock.py
- [ ] API_ID and API_HASH configured (optional)
- [ ] Business Bot enabled in BotFather
- [ ] Bot connected in Telegram Business settings
- [ ] Bot running (`python sherlock.py`)
- [ ] Dashboard accessible at http://localhost:5000
- [ ] Dashboard password changed from default

---

**Congratulations! Your Telegram Business Logger is now running! 🎉**
