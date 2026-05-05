import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. การตั้งค่า Firebase ---
database_url = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
firebase_config_raw = os.getenv("FIREBASE_CONFIG")

if firebase_config_raw:
    cred = credentials.Certificate(json.loads(firebase_config_raw))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {'databaseURL': database_url})
else:
    cred = credentials.Certificate("serviceAccountKey.json")

ref = db.reference('/')

# --- 2. ฟังก์ชันหลักในการจัดการเงินและสต็อก ---
def get_data(path):
    return ref.child(path).get()

def update_data(path, value):
    ref.child(path).update(value)

# --- 3. ระบบร้านค้า (Persistent View) ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="🛒 เลือกสินค้าที่ต้องการซื้อ",
        custom_id="secxion:buy_select",
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬", description="ราคา 50 บาท"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺", description="ราคา 30 บาท")
        ]
    )
    async def buy_callback(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        item_type = select.values[0]
        user_id = str(inter.author.id)
        
        # ดึงราคาจาก Firebase (ถ้าไม่มีให้ใช้ค่าเริ่มต้น)
        prices = {"netflix": 50, "youtube": 30}
        price = prices.get(item_type, 999)
        
        # ตรวจสอบเงินและสต็อก
        user_bal = get_data(f'users/{user_id}/balance') or 0
        stocks = get_data(f'stocks/{item_type}')
        
        if not stocks:
            return await inter.response.send_message("❌ สินค้าหมดชั่วคราว!", ephemeral=True)
        
        if user_bal < price:
            return await inter.response.send_message(f"❌ เงินไม่พอ! (ขาดอีก {price - user_bal} บาท)", ephemeral=True)

        # เริ่มกระบวนการซื้อ (ดึงของชิ้นแรกออกมา)
        item_id = list(stocks.keys())[0]
        item_detail = stocks[item_id]

        # หักเงินและลบสต็อก
        ref.child(f'users/{user_id}').update({'balance': user_bal - price})
        ref.child(f'stocks/{item_type}/{item_id}').delete()

        # ส่งสินค้าให้ลูกค้า
        embed = disnake.Embed(title="✅ สั่งซื้อสำเร็จ!", color=disnake.Color.green())
        embed.add_field(name="📦 สินค้าที่ได้รับ", value=f"```\n{item_detail}\n
```")
        await inter.response.send_message(embed=embed, ephemeral=True)
        
        # แจ้งเตือนในห้อง Log (ถ้ามี)
        print(f"User {user_id} bought {item_type}")

    @disnake.ui.button(label="เช็คเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion:bal")
    async def check_bal(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        bal = get_data(f'users/{inter.author.id}/balance') or 0
        await inter.response.send_message(f"💎 ยอดเงินของคุณ: **{bal}** บาท", ephemeral=True)

class SECXION_STORE(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"✅ บอทออนไลน์ & ระบบ Real-time พร้อมใช้งาน")

    async def on_message(self, message):
        if message.author.bot: return
        
        # ระบบตรวจสลิป (ส่งสลิป = แจ้งแอดมิน)
        if message.attachments:
            for attach in message.attachments:
                if any(attach.filename.lower().endswith(e) for e in ['.png', '.jpg', '.jpeg']):
                    log_channel = message.channel # หรือระบุ ID ห้องที่ให้แอดมินดู
                    embed = disnake.Embed(title="🔔 แจ้งโอนเงินใหม่", description=f"จาก: {message.author.mention}", color=disnake.Color.gold())
                    embed.set_image(url=attach.url)
                    await log_channel.send(embed=embed, view=ConfirmPayment(message.author.id))
                    await message.reply("⏳ สลิปถูกส่งให้แอดมินตรวจสอบแล้ว!")
        
        await self.process_commands(message)

# --- 4. ปุ่มยืนยันการโอนเงิน (สำหรับแอดมิน) ---
class ConfirmPayment(disnake.ui.View):
    def __init__(self, customer_id):
        super().__init__(timeout=None)
        self.customer_id = customer_id

    @disnake.ui.button(label="ยืนยันยอดเงิน", style=disnake.ButtonStyle.success)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        # แอดมินใส่จำนวนเงินผ่าน Modal หรือคำสั่งง่ายๆ
        await inter.response.send_modal(
            title="ระบุยอดเงิน",
            custom_id="modal_topup",
            components=[disnake.ui.TextInput(label="จำนวนเงิน", custom_id="amount")]
        )

    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        amount = float(inter.text_values["amount"])
        curr = get_data(f'users/{self.customer_id}/balance') or 0
        ref.child(f'users/{self.customer_id}').update({'balance': curr + amount})
        await inter.response.send_message(f"✅ เติมเงินให้ <@{self.customer_id}> {amount} บาทแล้ว!")

bot = SECXION_STORE()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🏪 **SECXION STORE** | ระบบอัตโนมัติ 24 ชม.", view=ShopView())

bot.run(os.getenv("TOKEN"))
