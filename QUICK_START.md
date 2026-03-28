# 🚀 Quick Start Guide

## Getting Started in 3 Steps

### 1️⃣ Start the Bot
```bash
python sherlock.py
```

You should see:
```
2026-03-27 14:30:15 | INFO | Database initialised.
2026-03-27 14:30:16 | INFO | Web dashboard running at http://localhost:5000
2026-03-27 14:30:17 | INFO | Bot is running. Press Ctrl+C to stop.
```

### 2️⃣ Open Dashboard
Open your browser and go to:
```
http://localhost:5000
```

### 3️⃣ Enter Password
Type: `a1234` and click "Unlock"

---

## 🎯 What You'll See

### Dashboard Layout (3 Panels)

```
┌─────────────────────────────────────────────────────────────┐
│  📡 Telegram Business Logger              🟢 Live  2:30 PM  │
├─────────────────────────────────────────────────────────────┤
│  Users: 5  │  Messages: 326  │  Chats: 9  │  Deleted: 1    │
├──────────┬──────────────┬───────────────────────────────────┤
│          │              │                                   │
│ CONTACTS │    CHATS     │          MESSAGES                 │
│          │              │                                   │
│  👤 Alex │  💬 Alice    │  Alex: Hello!                     │
│  21 msgs │  15 msgs     │  Alice: Hi there!                 │
│          │              │  Alex: [📷 Photo]                 │
│  👤 Bob  │  💬 Carol    │  Alice: [🎵 Voice message]        │
│  10 msgs │  6 msgs      │  Alex: How are you?               │
│          │              │  Alice: Great! [🎬 Video]         │
│          │              │                                   │
│          │              │  [Search messages...]             │
└──────────┴──────────────┴───────────────────────────────────┘
```

---

## 📱 Using the Dashboard

### Panel 1: Contacts
- Shows everyone who has messaged through your business account
- Click any contact to see their chats

### Panel 2: Chats  
- Shows all conversations for the selected contact
- Click any chat to see messages

### Panel 3: Messages
- Shows full conversation
- Media plays inline automatically
- Search, filter, and manage messages

---

## 🎬 Media Playback Examples

### When You See a Photo Message:
```
┌─────────────────────────────────┐
│ Alex  @alex  123456             │
│ 2m ago                          │
│                                 │
│ Check out this picture!         │
│                                 │
│ ┌─────────────────────────┐    │
│ │                         │    │
│ │     [Photo Preview]     │    │
│ │   Click to enlarge      │    │
│ │                         │    │
│ └─────────────────────────┘    │
│                                 │
│ ⏳ 6d left                      │
└─────────────────────────────────┘
```

### When You See a Video Message:
```
┌─────────────────────────────────┐
│ Alice  @alice  789012           │
│ 5m ago                          │
│                                 │
│ Watch this!                     │
│                                 │
│ ┌─────────────────────────┐    │
│ │     ▶️  [Video]         │    │
│ │  ━━━━━━━━━━━━━━━━━━━━  │    │
│ │  0:15 / 1:23    🔊  ⛶   │    │
│ └─────────────────────────┘    │
│                                 │
│ ⏳ 6d left                      │
└─────────────────────────────────┘
```

### When You See a Voice Message:
```
┌─────────────────────────────────┐
│ Bob  @bob  345678               │
│ 10m ago                         │
│                                 │
│ ┌─────────────────────────┐    │
│ │  ▶️  ━━━━━━━━━━━━━━━━  │    │
│ │  0:05 / 0:23    🔊       │    │
│ └─────────────────────────┘    │
│                                 │
│ ⏳ 6d left                      │
└─────────────────────────────────┘
```

### When You See a Sticker:
```
┌─────────────────────────────────┐
│ Carol  @carol  567890           │
│ 15m ago                         │
│                                 │
│      ┌──────┐                   │
│      │ 😊   │  (animated)       │
│      └──────┘                   │
│                                 │
│ ⏳ 6d left                      │
└─────────────────────────────────┘
```

---

## 🎮 Interactive Features

### Click on Photos
- Opens full-screen lightbox
- Shows photo at full resolution
- Click anywhere or press ESC to close

### Video Controls
- ▶️ Play/Pause
- 🔊 Volume control
- ⛶ Fullscreen
- Timeline scrubbing

### Audio Controls
- ▶️ Play/Pause
- 🔊 Volume control
- Timeline scrubbing
- Duration display

---

## 🔍 Search & Filter

### Search Messages
Type in the search box to find:
- Message text
- Sender names
- Usernames

### Filter Messages
Click "Filter" button to cycle through:
- **All**: Show everything
- **Deleted**: Only deleted messages
- **Edited**: Only edited messages
- **Media**: Only messages with media

---

## 🎨 Message Colors

- 🔵 **Blue border**: Normal message
- 🔴 **Red background**: Deleted message (content preserved!)
- 🟡 **Yellow background**: Edited message (shows original)
- 🟢 **Green border**: Message with media

---

## ⚡ Quick Tips

1. **Auto-refresh**: Dashboard updates every 5 seconds automatically
2. **Lazy loading**: Media loads only when you scroll to it
3. **Keyboard shortcuts**: Press ESC to close lightbox
4. **Message expiry**: Messages auto-delete after 7 days
5. **Media preserved**: Deleted messages still show their media if cached

---

## 🔧 Common Actions

### View a Contact's Messages
1. Click contact in left panel
2. Click chat in middle panel
3. See messages in right panel

### Play a Video
1. Navigate to message with video
2. Click ▶️ play button
3. Use controls to pause, seek, adjust volume

### Enlarge a Photo
1. Click on any photo
2. Full-screen lightbox opens
3. Click anywhere or press ESC to close

### Listen to Voice Message
1. Navigate to message with voice
2. Click ▶️ play button
3. Audio plays inline

### Search Messages
1. Type in search box (top right of messages panel)
2. Results filter in real-time
3. Clear search to see all messages

---

## 📊 Statistics Bar

Always visible at top showing:
- **Users**: Total contacts
- **Messages**: Total cached messages
- **Chats**: Total conversations
- **Deleted**: Count of deleted messages (🔴)
- **Edited**: Count of edited messages (🟡)
- **Media files**: Total media on disk (🟢)

---

## 🎯 What's Automatic

✅ Message logging (all business chats)  
✅ Media downloading (photos, videos, voice, etc.)  
✅ Edit tracking (shows original text)  
✅ Delete tracking (preserves content)  
✅ Media playback (inline, automatic)  
✅ Dashboard refresh (every 5 seconds)  
✅ Message expiry (after 7 days)  

---

## 🆘 Troubleshooting

### Dashboard won't load?
- Check bot is running
- Try http://localhost:5000
- Clear browser cache (Ctrl+F5)

### Password not working?
- Default is: `a1234`
- Check for typos
- Case-sensitive

### Media not playing?
- Check media_cache folder exists
- Check files are in media_cache/
- Try different browser

### Messages not appearing?
- Check bot is connected to Telegram Business
- Send test message
- Wait 5 seconds for auto-refresh

---

## 🎉 You're All Set!

Your Telegram Business Logger is now running with:
- ✅ Password protection
- ✅ Full media playback
- ✅ Real-time monitoring
- ✅ 3-panel dashboard
- ✅ Search & filter
- ✅ Edit/delete tracking

Enjoy monitoring your business chats! 🚀

---

**Need Help?** Check:
- `README.md` - Full documentation
- `MEDIA_PLAYBACK.md` - Media features
- `PASSWORD_FEATURE.md` - Password info
- `INSTRUCTION.md` - Detailed setup guide
