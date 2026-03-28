╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║              LOCALHOST:5000 MUAMMOSI VA HOSTING SOZLAMALARI                  ║
║                         TO'LIQ TUSHUNTIRISH                                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


═══════════════════════════════════════════════════════════════════════════════
  1-QISM: LOCALHOST NIMA VA MUAMMO NIMADA?
═══════════════════════════════════════════════════════════════════════════════

LOCALHOST NIMA?
---------------
• localhost = sizning kompyuteringiz
• localhost:5000 = faqat sizning kompyuteringizda ochiladi
• Boshqa odamlar kirololmaydi
• Internet orqali ochilmaydi

MUAMMO:
-------
Agar siz botni hostingga joylashtirsangiz:

❌ NOTO'G'RI:
   http://localhost:5000  ← Bu ishlamaydi!
   
✅ TO'G'RI:
   http://45.123.45.67:5000  ← Server IP manzili
   yoki
   http://mybot.uz  ← Domen nomi


═══════════════════════════════════════════════════════════════════════════════
  2-QISM: KODDA NIMA O'ZGARTIRISH KERAK?
═══════════════════════════════════════════════════════════════════════════════

HOZIRGI KOD (sherlock.py):
---------------------------
```python
def run_flask() -> None:
    import logging as _l
    _l.getLogger("werkzeug").setLevel(_l.WARNING)
    flask_app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False)
```

Bu kod ALLAQACHON TO'G'RI! ✅
• host="0.0.0.0" = barcha tarmoq interfeyslarida tinglaydi
• Bu degani: localhost ham, server IP ham ishlaydi


ADMIN PANEL'DAGI XABARLAR:
---------------------------
Kodda quyidagi joylar bor:

1) /admin buyrug'ida:
```python
f"🌐 <b>Dashboard:</b> http://localhost:{WEB_PORT}\n"
```

2) /stats buyrug'ida:
```python
f"🌐 Dashboard: http://localhost:{WEB_PORT}"
```

Bu faqat KO'RSATISH uchun. Haqiqiy muammo emas!


═══════════════════════════════════════════════════════════════════════════════
  3-QISM: HOSTING'DA QANDAY OCHISH KERAK?
═══════════════════════════════════════════════════════════════════════════════

VARIANT 1: SERVER IP MANZILI BILAN
-----------------------------------
Agar serveringizning IP manzili: 45.123.45.67

Brauzerda oching:
http://45.123.45.67:5000

Parol: a1234


VARIANT 2: DOMEN NOMI BILAN (Nginx)
------------------------------------
Agar domeningiz bor: mybot.uz

1) Nginx o'rnatish:
   sudo apt install nginx -y

2) Konfiguratsiya yaratish:
   sudo nano /etc/nginx/sites-available/telegram_bot

3) Quyidagi kodni kiriting:
```nginx
server {
    listen 80;
    server_name mybot.uz www.mybot.uz;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

4) Faollashtirish:
   sudo ln -s /etc/nginx/sites-available/telegram_bot /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx

5) Brauzerda oching:
   http://mybot.uz


VARIANT 3: HTTPS (SSL) BILAN
-----------------------------
1) Certbot o'rnatish:
   sudo apt install certbot python3-certbot-nginx -y

2) SSL sertifikat olish:
   sudo certbot --nginx -d mybot.uz -d www.mybot.uz

3) Brauzerda oching:
   https://mybot.uz


═══════════════════════════════════════════════════════════════════════════════
  4-QISM: KODDA O'ZGARTIRISH (Ixtiyoriy)
═══════════════════════════════════════════════════════════════════════════════

Agar /admin va /stats buyruqlaridagi habarlarni o'zgartirmoqchi bo'lsangiz:

VARIANT A: SERVER IP MANZILINI QO'YISH
---------------------------------------
sherlock.py faylida quyidagi qatorlarni toping va o'zgartiring:

1) Konfiguratsiya qismida qo'shing:
```python
BOT_TOKEN    = "..."
ADMIN_ID     = 123456789
DB_PATH      = "business_bot.db"
MEDIA_CACHE  = "media_cache"
WEB_PORT     = 5000
CACHE_TTL    = 10

# Dashboard URL (o'z server IP yoki domeningizni yozing)
DASHBOARD_URL = "http://45.123.45.67:5000"  # ← O'z IP manzilini yozing
# yoki
# DASHBOARD_URL = "http://mybot.uz"  # ← Domeningiz bo'lsa
```

2) /admin buyrug'ida o'zgartiring:
```python
@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    menu = (
        "🛠 <b>Admin Panel</b>\n\n"
        "• /stats — Bot statistics\n"
        "• /ad — Broadcast message\n"
        "• /story @username — Download stories\n"
        "• /get — Save view-once media\n"
        "• /admin — This menu\n\n"
        f"🌐 <b>Dashboard:</b> {DASHBOARD_URL}\n"  # ← O'zgardi
        f"<i>Messages auto-deleted after {CACHE_TTL} days.</i>"
    )
    await update.message.reply_text(menu, parse_mode="HTML")
```

3) /stats buyrug'ida o'zgartiring:
```python
@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    media_count = len(os.listdir(MEDIA_CACHE)) if os.path.exists(MEDIA_CACHE) else 0
    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total users: <code>{count_users()}</code>\n"
        f"💬 Cached messages: <code>{count_cache()}</code>\n"
        f"🖼 Cached media files: <code>{media_count}</code>\n"
        f"⏳ Message TTL: <code>{CACHE_TTL} days</code>\n\n"
        f"🌐 Dashboard: {DASHBOARD_URL}"  # ← O'zgardi
    )
    await update.message.reply_text(text, parse_mode="HTML")
```


VARIANT B: DINAMIK URL (Avtomatik)
-----------------------------------
Agar server IP manzilini avtomatik aniqlashni xohlasangiz:

```python
import socket

def get_server_ip():
    """Get server's public IP address"""
    try:
        # Try to get public IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

# Konfiguratsiyada:
SERVER_IP = get_server_ip()
DASHBOARD_URL = f"http://{SERVER_IP}:{WEB_PORT}"
```


═══════════════════════════════════════════════════════════════════════════════
  5-QISM: FIREWALL SOZLAMALARI
═══════════════════════════════════════════════════════════════════════════════

MUHIM! Port 5000 ni ochish kerak:
----------------------------------

# UFW (Ubuntu Firewall)
sudo ufw allow 5000/tcp
sudo ufw reload

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload

# Portni tekshirish
sudo netstat -tulpn | grep 5000


HOSTING PROVAYDERDA:
--------------------
Ba'zi hosting provayderlar (DigitalOcean, Vultr, AWS, etc.) o'z firewall'lariga ega:

1) DigitalOcean:
   - Networking → Firewalls
   - Inbound Rules → Add Rule
   - Custom → TCP → 5000

2) AWS (Security Groups):
   - EC2 → Security Groups
   - Inbound Rules → Edit
   - Custom TCP → Port 5000 → 0.0.0.0/0

3) Vultr:
   - Firewall → Add Rule
   - Protocol: TCP
   - Port: 5000


═══════════════════════════════════════════════════════════════════════════════
  6-QISM: TEZKOR SOZLASH (5 DAQIQA)
═══════════════════════════════════════════════════════════════════════════════

QADAMLAR:
---------

1. SERVERGA ULANISH
   ssh root@SERVER_IP

2. PORTNI OCHISH
   sudo ufw allow 5000/tcp
   sudo ufw reload

3. BOTNI ISHGA TUSHIRISH
   cd /home/telegram_bot
   source venv/bin/activate
   python3 sherlock.py

4. BRAUZERDA OCHISH
   http://SERVER_IP:5000
   Parol: a1234

TAYYOR! ✅


═══════════════════════════════════════════════════════════════════════════════
  7-QISM: MUAMMOLARNI HAL QILISH
═══════════════════════════════════════════════════════════════════════════════

MUAMMO 1: Dashboard ochilmayapti
---------------------------------
Sabab: Port yopiq

Yechim:
sudo ufw allow 5000/tcp
sudo ufw status


MUAMMO 2: "Connection refused"
-------------------------------
Sabab: Bot ishlamayapti

Yechim:
ps aux | grep sherlock.py
# Agar ishlamasa:
python3 sherlock.py


MUAMMO 3: "This site can't be reached"
--------------------------------------
Sabab: Noto'g'ri IP manzil

Yechim:
# Server IP manzilini tekshiring:
hostname -I
# yoki
curl ifconfig.me


MUAMMO 4: Nginx bilan ishlamayapti
-----------------------------------
Sabab: Nginx konfiguratsiyasi noto'g'ri

Yechim:
sudo nginx -t
sudo systemctl status nginx
sudo systemctl restart nginx


MUAMMO 5: SSL sertifikat xatosi
--------------------------------
Sabab: Certbot to'g'ri o'rnatilmagan

Yechim:
sudo certbot --nginx -d mybot.uz
# Agar xato bo'lsa:
sudo certbot renew --dry-run


═══════════════════════════════════════════════════════════════════════════════
  8-QISM: XAVFSIZLIK MASLAHATLARI
═══════════════════════════════════════════════════════════════════════════════

1. PAROLNI O'ZGARTIRING
   sherlock.py da:
   const CORRECT_PASSWORD = 'a1234';  ← Kuchli parol qo'ying

2. FAQAT KERAKLI PORTLARNI OCHING
   sudo ufw default deny incoming
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 80/tcp    # HTTP
   sudo ufw allow 443/tcp   # HTTPS
   sudo ufw allow 5000/tcp  # Dashboard
   sudo ufw enable

3. HTTPS ISHLATING
   sudo certbot --nginx -d mybot.uz

4. ADMIN_ID NI TO'G'RI SOZLANG
   sherlock.py da:
   ADMIN_ID = 123456789  ← Faqat sizning ID raqamingiz


═══════════════════════════════════════════════════════════════════════════════
  9-QISM: TURLI HOSTING PROVAYDERLAR UCHUN
═══════════════════════════════════════════════════════════════════════════════

DIGITALOCEAN:
-------------
1. Droplet yarating (Ubuntu 22.04)
2. IP manzilni oling: 45.123.45.67
3. Dashboard: http://45.123.45.67:5000
4. Firewall: Networking → Firewalls → Port 5000


VULTR:
------
1. Server yarating (Ubuntu 22.04)
2. IP manzilni oling: 149.28.123.45
3. Dashboard: http://149.28.123.45:5000
4. Firewall: Settings → Firewall → Port 5000


AWS EC2:
--------
1. Instance yarating (Ubuntu 22.04)
2. Elastic IP oling: 54.123.45.67
3. Dashboard: http://54.123.45.67:5000
4. Security Group: Inbound Rules → Port 5000


HETZNER:
--------
1. Server yarating (Ubuntu 22.04)
2. IP manzilni oling: 95.123.45.67
3. Dashboard: http://95.123.45.67:5000
4. Firewall: Firewall → Rules → Port 5000


CONTABO:
--------
1. VPS yarating (Ubuntu 22.04)
2. IP manzilni oling: 194.123.45.67
3. Dashboard: http://194.123.45.67:5000
4. Firewall: Control Panel → Firewall → Port 5000


═══════════════════════════════════════════════════════════════════════════════
  10-QISM: XULOSA
═══════════════════════════════════════════════════════════════════════════════

ASOSIY NUQTALAR:
----------------

✅ Kod allaqachon to'g'ri (host="0.0.0.0")
✅ Faqat portni ochish kerak (5000)
✅ Server IP manzili bilan kirish: http://IP:5000
✅ Domen bilan: http://mybot.uz (Nginx kerak)
✅ HTTPS uchun: Certbot o'rnatish

LOCALHOST MUAMMOSI YO'Q!
------------------------
• localhost:5000 faqat ko'rsatish uchun
• Haqiqatda server IP bilan ishlaydi
• Kod o'zgartirish shart emas
• Faqat port ochish kerak


QISQA QILIB:
------------
1. Botni serverga yuklang
2. Port 5000 ni oching: sudo ufw allow 5000/tcp
3. Botni ishga tushiring: python3 sherlock.py
4. Brauzerda oching: http://SERVER_IP:5000
5. Parol kiriting: a1234

TAYYOR! 🚀


═══════════════════════════════════════════════════════════════════════════════
  QISQA MISOL
═══════════════════════════════════════════════════════════════════════════════

Server IP: 45.123.45.67

# 1. Serverga ulanish
ssh root@45.123.45.67

# 2. Portni ochish
sudo ufw allow 5000/tcp

# 3. Botni ishga tushirish
cd /home/telegram_bot
python3 sherlock.py

# 4. Brauzerda ochish
http://45.123.45.67:5000

# 5. Parol
a1234

MUVAFFAQIYATLAR! ✨
