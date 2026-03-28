# 📡 Telegram Business Logger Bot

A powerful Telegram bot for logging and managing business messages with a web dashboard interface.

## ✨ Features

- 📊 **Web Dashboard** - Real-time message monitoring at `http://your-server:5000`
- 💬 **Message Logging** - Automatically logs all business messages
- 🖼️ **Media Support** - Photos, videos, audio, stickers, documents
- 🔐 **Password Protection** - Secure dashboard access
- 📢 **Broadcast** - Send messages to all users
- 🔓 **View-Once Media** - Save disappearing photos/videos with `/get`
- 📖 **Story Downloader** - Download Telegram stories
- 🗑️ **Auto-Delete** - Messages expire after 10 days
- 🎨 **Modern UI** - Telegram-style 2-panel interface

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Telegram API credentials (from [my.telegram.org](https://my.telegram.org))

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/telegram-business-logger.git
cd telegram-business-logger
```

2. Install dependencies:
```bash
pip install "python-telegram-bot>=22.0" telethon flask
```

3. Configure the bot:
Edit `sherlock.py` and set your credentials:
```python
BOT_TOKEN    = "YOUR_BOT_TOKEN"
ADMIN_ID     = YOUR_TELEGRAM_ID
API_ID       = YOUR_API_ID
API_HASH     = "YOUR_API_HASH"
DASHBOARD_URL = "http://YOUR_SERVER_IP:5000"
```

4. Run the bot:
```bash
python sherlock.py
```

5. Open dashboard:
```
http://localhost:5000
Password: a1234
```

## 📖 Commands

### User Commands
- `/start` - Start the bot
- `/get` - Reply to any message to save its media (works in all chats)

### Admin Commands
- `/admin` - Show admin panel
- `/stats` - View bot statistics
- `/ad` - Broadcast message (reply to a message with `/ad`)
- `/clear` - Clear all messages from database
- `/story @username` - Download user's stories

## 🌐 Web Dashboard

The dashboard provides:
- **Chats Panel** - List of all conversations with contact names
- **Messages Panel** - View messages, media, and metadata
- **Search & Filter** - Find messages quickly
- **Media Playback** - Play videos and audio directly
- **Expired Messages** - View expired content (not deleted)

### Dashboard Features
- Auto-refresh (pauses when media is playing)
- Scroll position preservation
- Password protection
- Responsive design
- Dark theme

## 🔧 Configuration

### Environment Variables
You can use environment variables instead of hardcoding:
```bash
export BOT_TOKEN="your_token"
export ADMIN_ID="your_id"
export API_ID="your_api_id"
export API_HASH="your_api_hash"
```

### Settings
- `WEB_PORT` - Dashboard port (default: 5000)
- `CACHE_TTL` - Message expiration in days (default: 10)
- `DASHBOARD_URL` - Public dashboard URL

## 🐳 Docker Deployment

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install "python-telegram-bot>=22.0" telethon flask
CMD ["python", "sherlock.py"]
```

```bash
docker build -t telegram-bot .
docker run -d -p 5000:5000 telegram-bot
```

## 🌍 Hosting

### VPS/VDS (Recommended)

1. Upload files to server
2. Install dependencies
3. Open port 5000:
```bash
sudo ufw allow 5000/tcp
```
4. Run with systemd (see `hos.txt` for details)

### With Nginx (Domain)

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL/HTTPS

```bash
sudo certbot --nginx -d yourdomain.com
```

## 📁 Project Structure

```
telegram-business-logger/
├── sherlock.py              # Main bot file
├── business_bot.db          # SQLite database (auto-created)
├── media_cache/             # Cached media files (auto-created)
├── README.md                # This file
├── hos.txt                  # Hosting guide (Uzbek)
├── HOSTING_LOCALHOST.md     # Localhost/hosting guide (Uzbek)
├── INSTRUCTION.md           # Usage instructions
├── MEDIA_PLAYBACK.md        # Media playback documentation
├── PASSWORD_FEATURE.md      # Password feature documentation
└── .gitignore               # Git ignore file
```

## 🔒 Security

- Change default password in `sherlock.py`:
```javascript
const CORRECT_PASSWORD = 'your_strong_password';
```

- Set correct `ADMIN_ID` to restrict admin commands
- Use HTTPS in production
- Keep `BOT_TOKEN` and `API_HASH` secret
- Don't commit `.env` or `config.py` files

## 🛠️ Troubleshooting

### Dashboard not accessible
- Check if port 5000 is open: `sudo ufw allow 5000/tcp`
- Verify bot is running: `ps aux | grep sherlock.py`

### /get command not working
- Ensure `API_ID` and `API_HASH` are set correctly
- Check Telethon session is created

### Media not loading
- Check `media_cache/` folder exists
- Verify file permissions

## 📝 License

MIT License - feel free to use and modify

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Support

For issues and questions, please open an issue on GitHub.

## 🌟 Features Roadmap

- [ ] Multi-language support
- [ ] Export messages to CSV/JSON
- [ ] Advanced search filters
- [ ] User management panel
- [ ] Message analytics
- [ ] Webhook support

## 📸 Screenshots

### Web Dashboard
![Dashboard](https://via.placeholder.com/800x400?text=Dashboard+Screenshot)

### Admin Panel
![Admin Panel](https://via.placeholder.com/400x300?text=Admin+Panel)

---

Made with ❤️ for Telegram Business users
