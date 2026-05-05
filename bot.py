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

# ===== FIREBASE =====
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})
    ref = db.reference("/")
except Exception as e:
    print("Firebase Error:", e)
    ref = None

# ===== SAFE CODE BLOCK FUNCTION (กันพังทั้งไฟล์) =====
def codeblock(text):
    return f"```\n{text}\n```"

# ===== UI =====
class TopupModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(label="จำนวนเงิน", custom_id="amt"),
            disnake.ui.TextInput(label="เวลา", custom_id="time")
        ]
        super().__init__(title="แจ้งเติมเงิน", custom_id="topup_modal", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        amt = inter.text_values["amt"]
        time = inter.text_values["time"]

        channel = inter.bot.get_channel(ADMIN_LOG_ID)
        if not channel:
            return await inter.response.send_message("ไม่พบห้องแอดมิน", ephemeral=True)

        emb = disnake.Embed(title="แจ้งโอนเงิน", color=0xffff00)
        emb.add_field(name="ผู้ใช้", value=inter.author.mention)
        emb.add_field(name="จำนวน", value=amt)
        emb.add_field(name="เวลา", value=time)

        await channel.send(embed=emb, view=AdminApproveView(inter.author.id, amt))
        await inter.response.send_message("แจ้งแล้ว", ephemeral=True)

class AdminApproveView(disnake.ui.View):
    def __init__(self, user_id, amount):
        super().__init__(timeout=None)
        self.user_id = str(user_id)
        self.amount = float(amount)

    @disnake.ui.button(label="อนุมัติ", style=disnake.ButtonStyle.green)
    async def approve(self, button, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.administrator:
            return await inter.response.send_message("Admin only", ephemeral=True)

        bal = ref.child(f"users/{self.user_id}/balance").get() or 0
        ref.child(f"users/{self.user_id}").update({
            "balance": bal + self.amount
        })

        await inter.response.send_message("เติมเงินสำเร็จ")
        self.stop()

class MainStoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.load_menu()

    def load_menu(self):
        stocks = ref.child("stocks").get() if ref else {}
        stocks = stocks or {}

        options = []
        for cat, items in stocks.items():
            if isinstance(items, dict):
                real = [k for k in items if k != "_init"]
                if real:
                    options.append(disnake.SelectOption(label=cat, value=cat))

        if not options:
            options = [disnake.SelectOption(label="ไม่มีสินค้า", value="none")]

        select = disnake.ui.Select(
            placeholder="เลือกสินค้า",
            options=options
        )
        select.callback = self.buy_item

        self.clear_items()
        self.add_item(disnake.ui.Button(label="เติมเงิน", custom_id="topup_btn"))
        self.add_item(select)

    async def interaction_check(self, inter):
        if inter.data.get("custom_id") == "topup_btn":
            await inter.response.send_modal(TopupModal())
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

        # หักเงิน + ลบสินค้า
        ref.child(user_path).update({"balance": bal - price})
        ref.child(f"stocks/{cat}/{key}").delete()

        try:
            emb = disnake.Embed(title="ซื้อสำเร็จ", color=0x00ff00)
            emb.add_field(name="สินค้า", value=codeblock(detail), inline=False)

            await inter.author.send(embed=emb)
            msg = "ส่ง DM แล้ว"
        except:
            msg = f"DM ไม่ได้ ของคือ: {detail}"

        await inter.response.send_message(msg, ephemeral=True)

        self.load_menu()
        await inter.edit_original_message(view=self)

# ===== BOT =====
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    bot.add_view(MainStoreView())
    print("ONLINE")

@bot.command()
async def setup(ctx):
    await ctx.send("ร้านค้า", view=MainStoreView())

# ===== RUN =====
if __name__ == "__main__":
    from server import run_web
    Thread(target=run_web, daemon=True).start()
    bot.run(TOKEN)
