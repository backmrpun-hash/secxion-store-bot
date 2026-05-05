import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
FB_CONF = os.getenv("FIREBASE_CONFIG")
ADMIN_LOG_CHANNEL = 123456789012345678  # เปลี่ยนเป็น ID ห้องแอดมินของคุณ

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    ref = db.reference('/')
except Exception as e:
    print(f"Error: {e}")

# --- FUNCTIONS ---
def update_bal(uid, amt):
    curr = ref.child(f'users/{uid}/balance').get() or 0
    ref.child(f'users/{uid}').update({'balance': curr + amt})

# --- UI: ระบบเติมเงิน ---
class TopupModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(label="จำนวนเงิน", placeholder="เช่น 50", custom_id="amount"),
            disnake.ui.TextInput(label="เวลาที่โอน", placeholder="เช่น 12:30", custom_id="time")
        ]
        super().__init__(title="แจ้งเติมเงิน", custom_id="topup_modal", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        amt = inter.text_values["amount"]
        time = inter.text_values["time"]
        
        # ส่งข้อมูลเข้าห้องแอดมิน
        channel = inter.bot.get_channel(ADMIN_LOG_CHANNEL)
        embed = disnake.Embed(title="💰 รายงานการแจ้งโอน", color=0xffff00)
        embed.add_field(name="ผู้แจ้ง", value=f"{inter.author.mention} ({inter.author.id})")
        embed.add_field(name="จำนวนเงิน", value=amt)
        embed.add_field(name="เวลา", value=time)
        
        view = AdminApproveView(inter.author.id, float(amt))
        await channel.send(embed=embed, view=view)
        await inter.response.send_message("✅ ส่งเรื่องให้แอดมินตรวจสอบแล้ว กรุณารอสักครู่", ephemeral=True)

class AdminApproveView(disnake.ui.View):
    def __init__(self, user_id, amount):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.amount = amount

    @disnake.ui.button(label="อนุมัติ", style=disnake.ButtonStyle.green)
    async def approve(self, button, inter):
        update_bal(self.user_id, self.amount)
        await inter.response.send_message(f"✅ อนุมัติเงิน {self.amount} บาท ให้ <@{self.user_id}> แล้ว")
        self.stop()

# --- UI: ร้านค้าหลัก ---
class MainStoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="💰 เติมเงิน", style=disnake.ButtonStyle.green, custom_id="topup_btn")
    async def topup(self, button, inter):
        await inter.response.send_modal(TopupModal())

    @disnake.ui.button(label="🛒 ซื้อสินค้า", style=disnake.ButtonStyle.blurple, custom_id="shop_btn")
    async def shop(self, button, inter):
        # ใส่โค้ดเลือกสินค้าที่เคยทำไว้ที่นี่
        await inter.response.send_message("กำลังเปิดระบบร้านค้า...", ephemeral=True)

# --- BOT SETUP ---
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    bot.add_view(MainStoreView())
    print(f"Logged in as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🏪 **SECXION STORE**\nคลิกปุ่มด้านล่างเพื่อทำรายการ", view=MainStoreView())

# --- RUN BOT ---
from threading import Thread
from server import run_web # เรียกใช้ไฟล์เว็บหลังบ้าน

Thread(target=run_web).start() # รันเว็บแยก thread
bot.run(TOKEN)
