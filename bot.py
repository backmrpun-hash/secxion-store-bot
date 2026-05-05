import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. ตั้งค่าการเชื่อมต่อ Firebase ---
database_url = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
firebase_config_raw = os.getenv("FIREBASE_CONFIG")

if firebase_config_raw:
    cred = credentials.Certificate(json.loads(firebase_config_raw))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {'databaseURL': database_url})
else:
    cred = credentials.Certificate("serviceAccountKey.json")

ref = db.reference('/')

# --- 2. ฟังก์ชันจัดการข้อมูล Firebase ---
def get_user_balance(user_id):
    data = ref.child('users').child(str(user_id)).get()
    return data.get('balance', 0) if data else 0

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
        
        # กำหนดราคา (สามารถย้ายไปตั้งใน Firebase ได้ในอนาคต)
        prices = {"netflix": 50, "youtube": 30}
        price = prices.get(item_type, 999)
        
        user_bal = get_user_balance(user_id)
        stocks = ref.child(f'stocks/{item_type}').get()
        
        if not stocks:
            return await inter.response.send_message("❌ สินค้าหมดชั่วคราว!", ephemeral=True)
        
        if user_bal < price:
            return await inter.response.send_message(f"❌ เงินไม่พอ! (คุณมี {user_bal} บาท สินค้าราคา {price} บาท)", ephemeral=True)

        # เริ่มกระบวนการซื้อ: ดึงสินค้าชิ้นแรกออกมา
        item_id = list(stocks.keys())[0]
        item_detail = stocks[item_id]

        # หักเงินและลบสินค้าออกจากสต็อก
        ref.child(f'users/{user_id}').update({'balance': user_bal - price})
        ref.child(f'stocks/{item_type}/{item_id}').delete()

        # แก้ไข Error: แสดงสินค้าให้ลูกค้า
        embed = disnake.Embed(title="✅ สั่งซื้อสำเร็จ!", color=disnake.Color.green())
        embed.add_field(name="📦 สินค้าที่ได้รับ", value=f"```\n{item_detail}\n
```", inline=False)
        embed.set_footer(text=f"หักเงิน {price} บาท | ยอดเงินคงเหลือ {user_bal - price} บาท")
        
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion:bal_btn", emoji="💎")
    async def check_bal(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        bal = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินของคุณ: **{bal}** บาท", ephemeral=True)

# --- 4. ปุ่มยืนยันการโอนเงินสำหรับแอดมิน ---
class ConfirmPaymentView(disnake.ui.View):
    def __init__(self, customer_id):
        super().__init__(timeout=None)
        self.customer_id = customer_id

    @disnake.ui.button(label="ยืนยันยอดเงิน (แอดมิน)", style=disnake.ButtonStyle.success)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.administrator:
            return await inter.response.send_message("❌ เฉพาะแอดมินเท่านั้น", ephemeral=True)
            
        await inter.response.send_modal(
            title="ระบุยอดเงินที่ได้รับ",
            custom_id="modal_topup",
            components=[
                disnake.ui.TextInput(label="จำนวนเงิน (บาท)", custom_id="amount_input", placeholder="เช่น 100")
            ]
        )

# --- 5. ตัวบอทหลัก ---
class SECXION_STORE(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"✅ บอท {self.user} เชื่อมต่อ Firebase เรียบร้อย!")

    async def on_message(self, message):
        if message.author.bot: return
        
        # ระบบตรวจสลิป: ถ้าส่งรูปในห้องแชท จะเด้งปุ่มให้แอดมินกดยืนยัน
        if message.attachments:
            for attach in message.attachments:
                if any(attach.filename.lower().endswith(e) for e in ['.png', '.jpg', '.jpeg']):
                    embed = disnake.Embed(title="🔔 พบการส่งสลิปโอนเงิน", description=f"ลูกค้า: {message.author.mention}", color=disnake.Color.gold())
                    embed.set_image(url=attach.url)
                    await message.reply(embed=embed, view=ConfirmPaymentView(message.author.id))
        
        await self.process_commands(message)

    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id == "modal_topup":
            amount = float(inter.text_values["amount_input"])
            # หา ID ลูกค้าจากข้อมูลที่เก็บไว้ (หรือดึงจาก Context)
            # ในที่นี้เพื่อความง่าย แอดมินเป็นคนกรอกเงินให้ลูกค้าที่ส่งสลิป
            customer_id = inter.message.embeds[0].description.split(":")[1].strip("<@! >")
            
            curr_bal = get_user_balance(customer_id)
            ref.child(f'users/{customer_id}').update({'balance': curr_bal + amount})
            
            await inter.response.send_message(f"✅ เติมเงินให้ <@{customer_id}> จำนวน {amount} บาทสำเร็จ!")

bot = SECXION_STORE()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = disnake.Embed(title="SECXION STORE", description="ระบบร้านค้าอัตโนมัติเชื่อมต่อ Firebase", color=0x2b2d31)
    await ctx.send(embed=embed, view=ShopView())

bot.run(os.getenv("TOKEN"))
