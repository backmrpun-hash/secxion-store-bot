import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. SETTINGS (ตั้งค่าตรงนี้) ---
TOKEN = os.getenv("TOKEN")
DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
FB_CONF = os.getenv("FIREBASE_CONFIG")
ADMIN_LOG_ID = 1496076202509598720 # <<< เปลี่ยนเป็น ID ห้องแอดมินของมึง

# เชื่อมต่อ Firebase
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    ref = db.reference('/')
except Exception as e:
    print(f"Firebase Error: {e}")

# --- 2. MODAL & ADMIN SYSTEM ---
class TopupModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(label="จำนวนเงิน", placeholder="เช่น 50", custom_id="amt"),
            disnake.ui.TextInput(label="เวลาที่โอน", placeholder="เช่น 11:21", custom_id="time")
        ]
        super().__init__(title="แจ้งเติมเงิน (SECXION)", custom_id="topup_modal_fixed", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        amt = inter.text_values["amt"]
        time = inter.text_values["time"]
        
        channel = inter.bot.get_channel(ADMIN_LOG_ID)
        if not channel:
            return await inter.response.send_message("❌ ไม่พบห้องแอดมิน!", ephemeral=True)

        emb = disnake.Embed(title="💰 แจ้งโอนเงิน", color=0xffff00)
        emb.add_field(name="ผู้แจ้ง", value=f"{inter.author.mention}\nID: {inter.author.id}")
        emb.add_field(name="ยอดเงิน", value=f"{amt} บาท")
        emb.add_field(name="เวลา", value=time)
        
        view = AdminApproveView(inter.author.id, amt)
        await channel.send(embed=emb, view=view)
        await inter.response.send_message("✅ ส่งข้อมูลให้แอดมินแล้ว กรุณารอตรวจสอบ", ephemeral=True)

class AdminApproveView(disnake.ui.View):
    def __init__(self, user_id, amount):
        super().__init__(timeout=None)
        self.user_id = str(user_id)
        self.amount = float(amount)

    @disnake.ui.button(label="✅ อนุมัติ", style=disnake.ButtonStyle.green, custom_id="adm_app")
    async def approve(self, button, inter):
        if not inter.author.guild_permissions.administrator:
            return await inter.response.send_message("มึงไม่ใช่แอดมิน!", ephemeral=True)
            
        curr = ref.child(f'users/{self.user_id}/balance').get() or 0
        ref.child(f'users/{self.user_id}').update({'balance': curr + self.amount})
        
        await inter.response.send_message(f"✅ เติมเงินให้ <@{self.user_id}> สำเร็จ!")
        self.stop()

# --- 3. SHOP SYSTEM ---
class MainStoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="💎 เติมเงิน", style=disnake.ButtonStyle.green, custom_id="btn_topup")
    async def topup_click(self, button, inter):
        await inter.response.send_modal(TopupModal())

    @disnake.ui.select(
        placeholder="🛒 เลือกซื้อสินค้า",
        custom_id="shop_select",
        options=[
            disnake.SelectOption(label="Netflix", value="netflix", description="50 บาท"),
            disnake.SelectOption(label="YouTube", value="youtube", description="30 บาท")
        ]
    )
    async def shop_callback(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        itype = select.values[0]
        price = {"netflix": 50, "youtube": 30}.get(itype, 999)
        
        udata = ref.child(f'users/{inter.author.id}').get()
        bal = udata.get('balance', 0) if udata else 0
        stocks = ref.child(f'stocks/{itype}').get()

        if not stocks or bal < price:
            return await inter.response.send_message("❌ เงินไม่พอหรือของหมด!", ephemeral=True)

        iid = list(stocks.keys())[0]
        detail = str(stocks[iid])

        ref.child(f'users/{inter.author.id}').update({'balance': bal - price})
        ref.child(f'stocks/{itype}/{iid}').delete()

        # ป้องกัน Error ด้วยการใช้ String ธรรมดา
        res_msg = "✅ ซื้อสำเร็จ!\nของคือ: " + detail
        await inter.response.send_message(res_msg, ephemeral=True)

# --- 4. BOT CORE ---
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    # บรรทัดนี้สำคัญที่สุด เพื่อให้ปุ่มไม่พังเวลาบอทรีสตาร์ท
    bot.add_view(MainStoreView())
    print(f"🚀 {bot.user} ONLINE!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    emb = disnake.Embed(title="🏪 SECXION STORE", description="เลือกบริการด้านล่างนี้", color=0x2b2d31)
    await ctx.send(embed=emb, view=MainStoreView())

bot.run(TOKEN)
