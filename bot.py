import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
from threading import Thread
import os
import json

# --- 1. SETTINGS ---
TOKEN = os.getenv("TOKEN")
DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
FB_CONF = os.getenv("FIREBASE_CONFIG")
ADMIN_LOG_ID = 1496076202509598720 

# เชื่อมต่อ Firebase
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    ref = db.reference('/')
except Exception as e:
    print(f"Firebase Error: {e}")

# --- 2. UI CLASSES ---

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
    async def approve(self, button, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.administrator:
            return await inter.response.send_message("มึงไม่ใช่แอดมิน!", ephemeral=True)
            
        curr = ref.child(f'users/{self.user_id}/balance').get() or 0
        ref.child(f'users/{self.user_id}').update({'balance': curr + self.amount})
        
        await inter.response.send_message(f"✅ เติมเงินให้ <@{self.user_id}> สำเร็จ!")
        self.stop()

class MainStoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(disnake.ui.Button(label="💎 เติมเงิน", style=disnake.ButtonStyle.green, custom_id="btn_topup"))
        self.create_select()

    def create_select(self):
        # ดึงหมวดหมู่จาก Firebase มาสร้างตัวเลือกอัตโนมัติ
        stocks_data = ref.child('stocks').get() or {}
        options = []

        for cat_name, items in stocks_data.items():
            # กรองเอาเฉพาะหมวดหมู่ที่มีของจริงๆ (ไม่นับ _init)
            real_items = [k for k in items.keys() if k != '_init']
            count = len(real_items)
            
            if count > 0:
                # พยายามแยกราคาจากชื่อหมวดหมู่ (เช่น Netflix-50 จะได้ราคา 50)
                price_tag = "50" # ราคาเริ่มต้นถ้าไม่ได้ตั้งชื่อแบบมีขีด
                if "-" in cat_name:
                    price_tag = cat_name.split("-")[-1]

                options.append(disnake.SelectOption(
                    label=cat_name.upper(),
                    value=cat_name,
                    description=f"ราคา {price_tag} บาท | คงเหลือ {count} ชิ้น"
                ))

        if not options:
            options = [disnake.SelectOption(label="ขณะนี้ไม่มีสินค้า", value="none")]

        select = disnake.ui.Select(
            placeholder="🛒 เลือกสินค้าที่ต้องการซื้อ",
            custom_id="shop_select_dynamic",
            options=options
        )
        select.callback = self.shop_callback
        # ลบอันเก่าออกก่อนเพิ่มอันใหม่ (ถ้ามี)
        for item in self.children:
            if isinstance(item, disnake.ui.Select):
                self.remove_item(item)
        self.add_item(select)

    async def shop_callback(self, inter: disnake.MessageInteraction):
        itype = inter.values[0]
        if itype == "none":
            return await inter.response.send_message("❌ ของหมดแล้วไอ้ชาย!", ephemeral=True)

        # คำนวณราคาจากชื่อหมวดหมู่
        price = 50
        if "-" in itype:
            try: price = float(itype.split("-")[-1])
            except: price = 50

        udata = ref.child(f'users/{inter.author.id}').get()
        bal = udata.get('balance', 0) if udata else 0
        stocks = ref.child(f'stocks/{itype}').get() or {}
        
        # กรองเอาเฉพาะข้อมูลสินค้า
        real_items = {k: v for k, v in stocks.items() if k != '_init'}

        if not real_items:
            return await inter.response.send_message("❌ ของหมดกะทันหัน!", ephemeral=True)
        if bal < price:
            return await inter.response.send_message(f"❌ เงินไม่พอ! มึงมี {bal} บาท แต่ของราคา {price} บาท", ephemeral=True)

        # ดึงของชิ้นแรกและลบออก
        iid = list(real_items.keys())[0]
        detail = str(real_items[iid])

        ref.child(f'users/{inter.author.id}').update({'balance': bal - price})
        ref.child(f'stocks/{itype}/{iid}').delete()

        # --- ระบบส่งของเข้า DM ---
        try:
            dm_emb = disnake.Embed(title="🎁 รายการสั่งซื้อสำเร็จ", color=0x00ff00)
            dm_emb.add_field(name="สินค้า", value=f"**{itype.upper()}**", inline=False)
            # แบบที่ถูกต้อง
embed_dm.add_field(name="ข้อมูลสินค้า / ลิงก์ดาวน์โหลด", value=f"```\n{detail}\n```", inline=False)
            dm_emb.set_footer(text="SECXION STORE - ขอบคุณที่อุดหนุน")
            
            await inter.author.send(embed=dm_emb)
            msg = "✅ ซื้อสำเร็จ! เช็คของได้ที่แชทส่วนตัว (DM) เลย"
        except disnake.Forbidden:
            msg = f"⚠️ ซื้อสำเร็จ! แต่บอททักแชทมึงไม่ได้ (กรุณาเปิดรับข้อความจากคนแปลกหน้า)\n**ของคือ:** {detail}"

        await inter.response.send_message(msg, ephemeral=True)
        
        # อัปเดตเมนูใน Discord ทันที
        self.create_select()
        await inter.edit_original_message(view=self)

# --- 3. BOT CORE ---
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    bot.add_view(MainStoreView())
    print(f"🚀 {bot.user} ONLINE & DYNAMIC SYSTEM READY!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    emb = disnake.Embed(
        title="🏪 SECXION STORE", 
        description="ยินดีต้อนรับ! เลือกซื้อสินค้าหรือเติมเงินได้ที่ปุ่มด้านล่าง", 
        color=0x2b2d31
    )
    emb.set_image(url="https://i.pinimg.com/originals/f3/e4/f3/f3e4f3f3f3f3f3f3f3f3f3f3f3f3f3f3.gif") # ใส่รูปให้สวยๆ
    await ctx.send(embed=emb, view=MainStoreView())

# --- 4. RUNNING ---
if __name__ == "__main__":
    from server import run_web
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
    
    bot.run(TOKEN)
