import disnake
from disnake.ext import commands, tasks
import firebase_admin
from firebase_admin import credentials, db
import requests, json, os, cv2, numpy as np
from pyzbar.pyzbar import decode

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
FB_CONF = os.getenv("FIREBASE_CONFIG")

DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
SETUP_CHANNEL_ID = 1501239836516946061

SLIPGO_KEY = "ใส่ SECRET KEY ตรงนี้"
SLIPGO_API = "https://api.slip2go.com/api/verify-slip/qr-code/info"

PROMPTPAY_ID = "0812345678"

store_message_id = None

# ===== BOT =====
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

# ===== FIREBASE =====
cred = credentials.Certificate(json.loads(FB_CONF))
firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})
ref = db.reference("/")

# ===== UTILS =====
def codeblock(t):
    return f"```\n{t}\n```"

# ===== QR READ =====
def read_qr_from_image(url):
    import requests
    resp = requests.get(url)
    img_arr = np.asarray(bytearray(resp.content), dtype=np.uint8)
    img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

    decoded = decode(img)
    if not decoded:
        return None

    return decoded[0].data.decode("utf-8")

# ===== SLIP VERIFY =====
def verify_slip(qr_code):
    headers = {
        "Authorization": f"Bearer {SLIPGO_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "payload": {
            "qrCode": qr_code
        }
    }

    res = requests.post(SLIPGO_API, json=data, headers=headers)

    if res.status_code != 200:
        print(res.text)
        return None

    return res.json()

# ===== EMBED =====
def build_embed():
    stocks = ref.child("stocks").get() or {}
    text = ""

    for cat, data in stocks.items():
        price = data.get("price", 0)
        items = data.get("items", {})
        text += f"{cat} | {price} บาท | {len(items)} ชิ้น\n"

    if not text:
        text = "ไม่มีสินค้า"

    emb = disnake.Embed(
        title="🛒 STORE AUTO",
        description="!topup <จำนวน>",
        color=0x2b2d31
    )
    emb.add_field(name="📦 สินค้า", value=codeblock(text), inline=False)
    return emb

# ===== VIEW =====
class StoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.load()

    def load(self):
        stocks = ref.child("stocks").get() or {}
        options = []

        for cat, data in stocks.items():
            items = data.get("items", {})
            if items:
                options.append(disnake.SelectOption(label=cat, value=cat))

        if not options:
            options = [disnake.SelectOption(label="ไม่มีสินค้า", value="none")]

        select = disnake.ui.Select(options=options)
        select.callback = self.buy

        self.clear_items()
        self.add_item(select)

    async def buy(self, inter):
        cat = inter.values[0]

        user_id = str(inter.author.id)
        user = ref.child(f"users/{user_id}").get() or {}
        bal = user.get("balance", 0)

        price = ref.child(f"stocks/{cat}/price").get() or 0

        if bal < price:
            return await inter.response.send_message("เงินไม่พอ", ephemeral=True)

        items = ref.child(f"stocks/{cat}/items").get() or {}
        if not items:
            return await inter.response.send_message("ของหมด", ephemeral=True)

        key = list(items.keys())[0]
        data = items[key]

        ref.child(f"users/{user_id}").update({"balance": bal - price})
        ref.child(f"stocks/{cat}/items/{key}").delete()

        await inter.author.send(f"สินค้า:\n{data}")
        await inter.response.send_message("ซื้อสำเร็จ", ephemeral=True)

# ===== TOPUP =====
@bot.command()
async def topup(ctx, amount: int):
    qr = f"https://promptpay.io/{PROMPTPAY_ID}/{amount}.png"

    emb = disnake.Embed(
        title="💳 เติมเงิน",
        description=f"{amount} บาท\nสแกนแล้วส่งสลิป",
        color=0x00ff00
    )
    emb.set_image(url=qr)

    await ctx.send(embed=emb)

# ===== SLIP CHECK =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        for att in message.attachments:
            if "image" in att.content_type:

                await message.reply("⏳ กำลังตรวจสลิป...")

                qr = read_qr_from_image(att.url)
                if not qr:
                    return await message.reply("❌ อ่าน QR ไม่ได้")

                slip = verify_slip(qr)
                if not slip:
                    return await message.reply("❌ ตรวจสลิปไม่ผ่าน")

                try:
                    amount = int(slip["data"]["amount"])
                    ref_code = slip["data"]["transRef"]
                except:
                    return await message.reply("❌ format API เปลี่ยน")

                # ===== กันโกง =====
                if ref.child(f"transactions/{ref_code}").get():
                    return await message.reply("❌ สลิปนี้ใช้แล้ว")

                user_id = str(message.author.id)
                bal = ref.child(f"users/{user_id}/balance").get() or 0

                ref.child(f"users/{user_id}").update({
                    "balance": bal + amount
                })

                ref.child(f"transactions/{ref_code}").set({
                    "amount": amount,
                    "user": user_id
                })

                await message.reply(f"✅ เติมเงินสำเร็จ +{amount}")

    await bot.process_commands(message)

# ===== READY =====
@bot.event
async def on_ready():
    global store_message_id

    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)
    msg = await channel.send(embed=build_embed(), view=StoreView())

    store_message_id = msg.id
    auto_update.start()

# ===== LOOP =====
@tasks.loop(seconds=5)
async def auto_update():
    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)
    msg = await channel.fetch_message(store_message_id)

    await msg.edit(embed=build_embed(), view=StoreView())

# ===== RUN =====
bot.run(TOKEN)
