import disnake
from disnake.ext import commands, tasks
import firebase_admin
from firebase_admin import credentials, db
import os, json, hashlib, time

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
FB_CONF = os.getenv("FIREBASE_CONFIG")

SETUP_CHANNEL_ID = 1501239836516946061
PROMPTPAY_ID = "0812345678"  # ใส่เบอร์/เลขบัตร

store_message_id = None

# ===== BOT (ต้องอยู่ก่อน event) =====
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

# ===== FIREBASE =====
cred = credentials.Certificate(json.loads(FB_CONF))
firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})
ref = db.reference("/")

# ===== UTILS =====
def codeblock(text):
    return f"```\n{text}\n```"

def gen_ref(user_id, amount):
    raw = f"{user_id}-{amount}-{time.time()}"
    return hashlib.md5(raw.encode()).hexdigest()[:10]

# ===== EMBED =====
def build_embed():
    stocks = ref.child("stocks").get() or {}
    text = ""

    for cat, items in stocks.items():
        if isinstance(items, dict):
            count = len([k for k in items if k != "_init"])
            text += f"{cat}: {count}\n"

    if not text:
        text = "ไม่มีสินค้า"

    emb = disnake.Embed(
        title="🛒 STORE AUTO",
        description="เติมเงิน: !topup <จำนวน>",
        color=0x2b2d31
    )
    emb.add_field(name="📦 สต็อก", value=codeblock(text), inline=False)
    return emb

# ===== VIEW =====
class StoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.load()

    def load(self):
        stocks = ref.child("stocks").get() or {}
        options = []

        for cat, items in stocks.items():
            if isinstance(items, dict):
                real = [k for k in items if k != "_init"]
                if real:
                    options.append(disnake.SelectOption(label=cat, value=cat))

        if not options:
            options = [disnake.SelectOption(label="ไม่มีสินค้า", value="none")]

        select = disnake.ui.Select(options=options)
        select.callback = self.buy

        self.clear_items()
        self.add_item(select)

    async def buy(self, inter):
        cat = inter.values[0]

        user_path = f"users/{inter.author.id}"
        user = ref.child(user_path).get() or {}
        bal = user.get("balance", 0)

        if bal < 50:
            return await inter.response.send_message("เงินไม่พอ", ephemeral=True)

        items = ref.child(f"stocks/{cat}").get() or {}
        real = {k: v for k, v in items.items() if k != "_init"}

        if not real:
            return await inter.response.send_message("ของหมด", ephemeral=True)

        key = list(real.keys())[0]
        data = real[key]

        ref.child(user_path).update({"balance": bal - 50})
        ref.child(f"stocks/{cat}/{key}").delete()

        await inter.author.send(f"สินค้า:\n{data}")
        await inter.response.send_message("ซื้อสำเร็จ", ephemeral=True)

# ===== TOPUP COMMAND =====
@bot.command()
async def topup(ctx, amount: int):
    ref_code = gen_ref(ctx.author.id, amount)

    ref.child("pending").child(ref_code).set({
        "user": ctx.author.id,
        "amount": amount,
        "used": False
    })

    qr_text = f"PromptPay: {PROMPTPAY_ID}\nAmount: {amount}\nRef: {ref_code}"

    await ctx.send(
        embed=disnake.Embed(
            title="💳 เติมเงิน",
            description=codeblock(qr_text),
            color=0x00ff00
        )
    )

# ===== SLIP UPLOAD =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # ตรวจสลิป (ง่าย)
    if message.attachments:
        for att in message.attachments:
            if "image" in att.content_type:
                # mock ตรวจ (ของจริงต้องใช้ API)
                ref_code = message.content.strip()

                data = ref.child(f"pending/{ref_code}").get()
                if not data:
                    return await message.reply("ref ผิด")

                if data["used"]:
                    return await message.reply("ใช้แล้ว")

                user_id = data["user"]
                amount = data["amount"]

                bal = ref.child(f"users/{user_id}/balance").get() or 0

                ref.child(f"users/{user_id}").update({
                    "balance": bal + amount
                })

                ref.child(f"pending/{ref_code}").update({"used": True})

                await message.reply(f"เติมเงินสำเร็จ +{amount}")
                return

    await bot.process_commands(message)

# ===== READY =====
@bot.event
async def on_ready():
    global store_message_id
    print("ONLINE")

    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)

    msg = await channel.send(embed=build_embed(), view=StoreView())
    store_message_id = msg.id

    auto_update.start()

# ===== AUTO UPDATE =====
@tasks.loop(seconds=5)
async def auto_update():
    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)
    msg = await channel.fetch_message(store_message_id)

    await msg.edit(embed=build_embed(), view=StoreView())

# ===== RUN =====
bot.run(TOKEN)
