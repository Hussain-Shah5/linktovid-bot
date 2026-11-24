# LinkToVid Bot v2 - Long Video Support

TikTok / Instagram / Facebook / YouTube se video download karne wala Telegram Bot.
TikTok ki video **without watermark** aayegi.
**Long video bhi download hogi** - parts mein aayegi.

Ye bot Syed ke GTA channel se **alag** hai. Ye alag kaam hai.

## Bot kya karega

- Link bhejo, video mil jayegi
- TikTok - without watermark
- Instagram Reels - HD
- Facebook Video - HD
- YouTube / Shorts - HD
- **Long video - 50 MB se bari ho to parts mein bhej dega (Part 1, Part 2, Part 3...)**

## Long Video kaise kaam karegi

Telegram Bot ki limit 50 MB hai, ek file mein us se bari video nahi bhej sakta.
Is liye bot ye karega:

1. Video download karega (720p tak, taake size control mein rahe)
2. Agar 50 MB se chhoti hai to seedha bhej dega
3. Agar bari hai to:
   - **Default mode - split:** Video ko 45 MB wale parts mein tod dega, quality same rahegi. Tumhe Part 1, Part 2, Part 3 milenge.
   - **Compress mode:** `/mode compress` likho to video ko 480p mein compress karke ek file mein bhejne ki koshish karega. Quality thodi kam hogi, lekin ek hi file aayegi. Agar compress ke baad bhi bari hui to phir parts mein bhej dega.
   - Wapas split par aane ke liye: `/mode split`

**Long video ke liye ffmpeg zaroori hai:**
- Windows: https://ffmpeg.org/download.html se download karo aur install karo
- Linux: `sudo apt install ffmpeg`
- Mac: `brew install ffmpeg`

Agar ffmpeg nahi hoga to bot lambi video ko parts mein nahi tod payega.

## Step 1 - Bot banao (BotFather)

1. Telegram kholo, search karo `@BotFather`
2. `/start` bhejo, phir `/newbot` bhejo
3. Naam likho: `LinkToVid Bot`
4. Username likho: `LinkToVid1_Bot` - ye tumhara bot hai: t.me/LinkToVid1_Bot
5. BotFather tumhe ek **TOKEN** dega, wo copy karke apne paas rakho
   - Token kisi ko mat bhejo, ye bot ki chabi hai
   - Token chat mein share ho jaye to BotFather se `/revoke` karke naya token lo

## Step 2 - Apni Telegram ID nikalo

1. Telegram mein search karo `@userinfobot`
2. `/start` bhejo
3. Wo tumhari ID bhej dega, jaise `123456789`
4. Ye ID Admin ID hai

## Step 3 - Bot chalao (Computer par)

Computer mein Python hona chahiye. Agar nahi hai to python.org se install karo.

```bash
# Folder mein jao
cd vidgrab-bot

# Cheezein install karo (pehli dafa sirf)
pip install -r requirements.txt

# .env file banao
# .env.example ko copy karke .env naam do, phir us mein TOKEN aur ADMIN_ID dalo
# Windows: copy .env.example .env
# Mac / Linux: cp .env.example .env

# Bot chalao
python bot.py
```

Bot chalne lagega. Jab tak computer on aur ye command chal rahi hai, bot kaam karega.

Band karne ke liye `Ctrl + C` dabao.

## Step 4 - 24/7 chalana ho to (Hosting)

Agar chaho ke computer band hone par bhi bot chale, to free hosting use karo:

**Option A - Railway / Render (Free)**
1. Is folder ko GitHub par dalo
2. Railway.app ya Render.com par account banao
3. GitHub repo connect karo
4. Environment Variables mein `BOT_TOKEN` aur `ADMIN_ID` dalo
5. Start Command: `python bot.py`

**Option B - VPS**
Kisi bhi VPS par yehi files dal kar `python bot.py` chalao, ya `systemd` se hamesha on rakho.

## Bot ko kaise use karein

1. Telegram mein apne bot ko kholo, `/start` bhejo
2. Kisi bhi video ka link copy karke bhejo
3. Video mil jayegi

## Aap khud kaise manage karoge

Sirf tum Admin ho. Ye commands sirf tum chala sakte ho:

| Command | Kaam |
|---|---|
| `/allow 123456789` | Is user ko allow karo |
| `/remove 123456789` | Is user ko hatao |
| `/users` | Allowed users ki list dekho |
| `/public` | Public kar do - koi bhi use kar sake |
| `/private` | Private kar do - sirf allowed users |
| `/mode split` | Long video parts mein bhejo (default) |
| `/mode compress` | Long video compress karke ek file mein bhejo |
| `/stats` | Bot ka status dekho |

**Default mode: Private hai.**
Shuru mein sirf tum use kar sakte ho. Jab chaho `/public` likh kar public kar do, jab chaho `/private` likh kar wapas private.

Kisi ki ID janne ke liye us se kaho ke `@userinfobot` ko `/start` bheje.

## Limits

- Telegram Bot ek file mein 50 MB se bari video nahi bhej sakta - is liye lambi video parts mein aayegi. Agar ek hi 2 GB wali file chahiye to alag tareeqa hai: Local Bot API Server chalana hota hai, wo advanced setup hai, zaroorat ho to bata dena.
- Private account ki video download nahi hogi
- Bahut lambi video (1 ghanta+) mein download aur parts banane mein time zyada lag sakta hai
- Kabhi kabhi TikTok / Instagram link fail ho sakta hai, dobara try karo ya dusra link bhejo

## Files

- `bot.py` - Bot ka code
- `requirements.txt` - Zaroori cheezein
- `.env.example` - Token aur ID ki sample file
- `allowed_users.json` - Allowed users ki list (bot khud update karta hai)
- `settings.json` - Public / Private setting (bot khud update karta hai)
- `downloads/` - Download hone wali videos ka temp folder, bot khud saaf karta hai
