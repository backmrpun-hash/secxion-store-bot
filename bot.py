import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
from threading import Thread
import os
import json

# ===== SETTINGS =====
TOKEN = os.getenv("TOKEN")
DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
FB_CONF = os.getenv("FIREBASE_CONFIG")

ADMIN_LOG_ID = 1496076202509598720
SETUP_CHANNEL_ID = 1501239836516946061

# ===== FIREBASE =====
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})
    ref = db.reference("/")
except Exception as e:
    print("Firebase Error:", e)
    ref = None

# ===== SAFE CODEBLOCK =====
def codeblock(text):
    return f"```\n{text}\n```"

# ===== EMBED BUILDER (REALTIME) =====
def build_store_embed(user_id):
    user = ref.child(f"users/{user_id}").get() if ref else {}
    bal = user.get("balance", 0)

    stocks = ref.child("stocks").get() if ref else {}
    stocks = stocks or {}

    stock_text = ""
    for cat, items in stocks.items():
        if isinstance(items, dict):
            count = len([k for k in items if k != "_init"])
            stock_text += f"{cat} : {count} ชิ้น\n"

    if not stock_text:
        stock_text = "ไม่มีสินค้า"

    emb = disnake.Embed(
        title="🏪 STORE PANEL",
        description="ระบบร้านค้าอัตโนมัติ",
        color=0x2b2d31
    )

    emb.add_field(name="💰 ยอดเงิน", value=codeblock(str(bal)))
    emb.add_field(name="📦 สต็อก", value=codeblock(stock_text), inline=False)

    return emb

# ===== UI =====
class StoreView(disnake.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
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

        select = disnake.ui.Select(
            placeholder="🛒 เลือกสินค้า",
            options=options
        )
        select.callback = self.buy_item

        self.clear_items()
        self.add_item(disnake.ui.Button(label="💎 เติมเงิน", custom_id="topup"))
        self.add_item(disnake.ui.Button(label="🔄 รีเฟรช", custom_id="refresh"))
        self.add_item(select)

    async def interaction_check(self, inter):
        if inter.channel.id != SETUP_CHANNEL_ID:
            await inter.response.send_message("ใช้ได้เฉพาะห้องที่กำหนด", ephemeral=True)
            return False

        if inter.data.get("custom_id") == "topup":
            await inter.response.send_modal(TopupModal())
            return False

        if inter.data.get("custom_id") == "refresh":
            emb = build_store_embed(inter.author.id)
            await inter.response.edit_message(embed=emb, view=StoreView(inter.author.id))
            return False

        return True

    async def buy_item(self, inter: disnake.MessageInteraction):
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

        emb = build_store_embed(inter.author.id)
        await inter.response.edit_message(embed=emb, view=StoreView(inter.author.id))
        await inter.followup.send(msg, ephemeral=True)

# ===== TOPUP =====
class TopupModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(label="จำนวนเงิน", custom_id="amt"),
            disnake.ui.TextInput(label="เวลา", custom_id="time")
        ]
        super().__init__(title="แจ้งเติมเงิน", components=components)

    async def callback(self, inter):
        amt = inter.text_values["amt"]
        time = inter.text_values["time"]

        ch = inter.bot.get_channel(ADMIN_LOG_ID)

        emb = disnake.Embed(title="💰 แจ้งเติมเงิน", color=0xffff00)
        emb.add_field(name="ผู้ใช้", value=inter.author.mention)
        emb.add_field(name="จำนวน", value=amt)
        emb.add_field(name="เวลา", value=time)

        await ch.send(embed=emb)
        await inter.response.send_message("แจ้งแล้ว รอแอดมิน", ephemeral=True)

# ===== BOT =====
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

@bot.command()
async def setup(ctx):
    if ctx.channel.id != SETUP_CHANNEL_ID:
        return await ctx.send("ใช้คำสั่งนี้ในห้องที่กำหนดเท่านั้น")

    emb = build_store_embed(ctx.author.id)
    await ctx.send(embed=emb, view=StoreView(ctx.author.id))

@bot.event
async def on_ready():
    print("ONLINE")

# ===== RUN =====
if __name__ == "__main__":
    from server import run_web
    Thread(target=run_web, daemon=True).start()
    bot.run(TOKEN)
