import disnake
from disnake.ext import commands, tasks
import firebase_admin
from firebase_admin import credentials, db
import requests, json, os

# 🔥 เพิ่ม import ที่ขาด
from PIL import Image
from io import BytesIO
import pytesseract
import re

TOKEN = os.getenv("TOKEN")
FB_CONF = os.getenv("FIREBASE_CONFIG")

DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
SETUP_CHANNEL_ID = 1501239836516946061

PROMPTPAY_ID = "0655292340"

bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

cred = credentials.Certificate(json.loads(FB_CONF))
firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})
ref = db.reference("/")

store_message_id = None

# ===== VERIFY (OCR) =====
def verify_slip_image(image_url):
    try:
        img_data = requests.get(image_url, timeout=10).content
        img = Image.open(BytesIO(img_data))

        text = pytesseract.image_to_string(img, lang="tha+eng")

        print("OCR RESULT:", text)

        return text

    except Exception as e:
        print("OCR ERROR:", e)
        return None


# ===== STORE =====
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
    emb.add_field(name="📦 สินค้า", value=f"```{text}```", inline=False)
    return emb


class StoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.load()

    def load(self):
        stocks = ref.child("stocks").get() or {}
        options = []

        for cat, data in stocks.items():
            if data.get("items"):
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
        description=f"{amount} บาท\nส่งสลิปหลังโอน",
        color=0x00ff00
    )
    emb.set_image(url=qr)

    await ctx.send(embed=emb)


# ===== AUTO TOPUP =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        for att in message.attachments:

            if not att.content_type:
                continue

            if "image" not in att.content_type:
                continue

            await message.reply("⏳ กำลังตรวจสลิป...")

            slip_text = verify_slip_image(att.url)

            if not slip_text:
                return await message.reply("❌ ตรวจไม่ผ่าน")

            # 🔍 หาเลขจาก OCR
            amount_match = re.findall(r"\d+", slip_text)

            if not amount_match:
                return await message.reply("❌ ไม่เจอจำนวนเงิน")

            amount = int(amount_match[0])

            if amount <= 0:
                return await message.reply("❌ จำนวนเงินผิดปกติ")

            # กันโกง (สร้าง ref code ใหม่)
            ref_code = f"{message.id}_{amount}"

            if ref.child(f"transactions/{ref_code}").get():
                return await message.reply("❌ สลิปซ้ำ")

            user_id = str(message.author.id)
            bal = ref.child(f"users/{user_id}/balance").get() or 0

            ref.child(f"users/{user_id}").update({
                "balance": bal + amount
            })

            ref.child(f"transactions/{ref_code}").set({
                "amount": amount,
                "user": user_id
            })

            await message.reply(f"✅ เติมเงิน +{amount}")

    await bot.process_commands(message)


# ===== READY =====
@bot.event
async def on_ready():
    global store_message_id

    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)
    msg = await channel.send(embed=build_embed(), view=StoreView())

    store_message_id = msg.id
    auto_update.start()


@tasks.loop(seconds=5)
async def auto_update():
    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)
    msg = await channel.fetch_message(store_message_id)

    await msg.edit(embed=build_embed(), view=StoreView())


bot.run(TOKEN)
