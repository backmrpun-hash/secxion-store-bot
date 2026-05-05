import disnake
from disnake.ext import commands, tasks
import firebase_admin
from firebase_admin import credentials, db
import os, json

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
FB_CONF = os.getenv("FIREBASE_CONFIG")

SETUP_CHANNEL_ID = 1501239836516946061

store_message_id = None

# ===== FIREBASE =====
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})
    ref = db.reference("/")
except Exception as e:
    print("Firebase Error:", e)
    ref = None

# ===== SAFE =====
def codeblock(text):
    return f"```\n{text}\n```"

# ===== EMBED =====
def build_store_embed():
    stocks = ref.child("stocks").get() or {}

    text = ""
    for cat, items in stocks.items():
        if isinstance(items, dict):
            count = len([k for k in items if k != "_init"])
            text += f"{cat} : {count} ชิ้น\n"

    if not text:
        text = "ไม่มีสินค้า"

    emb = disnake.Embed(
        title="🏪 STORE AUTO",
        description="อัปเดทอัตโนมัติ | เติมเงินพิมพ์: topup <จำนวน>",
        color=0x2b2d31
    )
    emb.add_field(name="📦 สต็อก", value=codeblock(text), inline=False)
    return emb

# ===== VIEW =====
class StoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.load_menu()

    def load_menu(self):
        stocks = ref.child("stocks").get() or {}
        options = []

        for cat, items in stocks.items():
            if isinstance(items, dict):
                real = [k for k in items if k != "_init"]
                if real:
                    options.append(disnake.SelectOption(label=cat, value=cat))

        if not options:
            options = [disnake.SelectOption(label="ไม่มีสินค้า", value="none")]

        select = disnake.ui.Select(placeholder="🛒 เลือกสินค้า", options=options)
        select.callback = self.buy_item

        self.clear_items()
        self.add_item(select)

    async def buy_item(self, inter: disnake.MessageInteraction):
        if inter.channel.id != SETUP_CHANNEL_ID:
            return await inter.response.send_message("ใช้ได้เฉพาะห้องร้าน", ephemeral=True)

        cat = inter.values[0]
        if cat == "none":
            return await inter.response.send_message("ของหมด", ephemeral=True)

        user_path = f"users/{inter.author.id}"
        user = ref.child(user_path).get() or {}
        bal = user.get("balance", 0)
        price = 50

        if bal < price:
            return await inter.response.send_message("เงินไม่พอ", ephemeral=True)

        items = ref.child(f"stocks/{cat}").get() or {}
        real_items = {k: v for k, v in items.items() if k != "_init"}

        if not real_items:
            return await inter.response.send_message("ของหมด", ephemeral=True)

        key = list(real_items.keys())[0]
        detail = str(real_items[key])

        ref.child(user_path).update({"balance": bal - price})
        ref.child(f"stocks/{cat}/{key}").delete()

        try:
            await inter.author.send(
                embed=disnake.Embed(
                    title="📦 สินค้า",
                    description=codeblock(detail),
                    color=0x00ff00
                )
            )
            msg = "✅ ส่ง DM แล้ว"
        except:
            msg = f"⚠️ DM ไม่ได้\n{detail}"

        await inter.response.send_message(msg, ephemeral=True)

# ===== AUTO TOPUP (ง่าย) =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # พิมพ์: topup 100
    if message.content.startswith("topup"):
        try:
            amount = int(message.content.split()[1])
        except:
            return await message.reply("ใช้แบบ: topup 50")

        user_path = f"users/{message.author.id}"
        bal = ref.child(user_path + "/balance").get() or 0

        ref.child(user_path).update({
            "balance": bal + amount
        })

        await message.reply(f"เติมเงินสำเร็จ +{amount} บาท 💰")

    await bot.process_commands(message)

# ===== BOT =====
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    global store_message_id
    print("ONLINE")

    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)

    # หา message เก่า
    async for msg in channel.history(limit=20):
        if msg.author == bot.user:
            store_message_id = msg.id
            break

    emb = build_store_embed()
    view = StoreView()

    if store_message_id:
        try:
            msg = await channel.fetch_message(store_message_id)
            await msg.edit(embed=emb, view=view)
        except:
            msg = await channel.send(embed=emb, view=view)
            store_message_id = msg.id
    else:
        msg = await channel.send(embed=emb, view=view)
        store_message_id = msg.id

    auto_update.start()

# ===== LOOP =====
@tasks.loop(seconds=5)
async def auto_update():
    try:
        channel = await bot.fetch_channel(SETUP_CHANNEL_ID)
        msg = await channel.fetch_message(store_message_id)

        await msg.edit(embed=build_store_embed(), view=StoreView())
    except Exception as e:
        print("Update Error:", e)

# ===== RUN =====
bot.run(TOKEN)
