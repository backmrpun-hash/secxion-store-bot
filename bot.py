import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. ตั้งค่า Firebase ---
database_url = "[https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/](https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/)"
firebase_config_raw = os.getenv("FIREBASE_CONFIG")

if firebase_config_raw:
    # อ่านจาก Railway Variable
    cred = credentials.Certificate(json.loads(firebase_config_raw))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {'databaseURL': database_url})
else:
    # กรณีรันในคอม (ถ้ามีไฟล์)
    cred = credentials.Certificate("serviceAccountKey.json")

ref = db.reference('/')

# --- 2. ฟังก์ชันจัดการข้อมูล ---
def get_user_balance(user_id):
    data = ref.child('users').child(str(user_id)).get()
    return data.get('balance', 0) if data else 0

# --- 3. ระบบร้านค้า (Persistent View) ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="🛒 เลือกสินค้าที่ต้องการซื้อ",
        custom_id="secxion:buy_v2",
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬", description="ราคา 50 บาท"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺", description="ราคา 30 บาท")
        ]
    )
    async def buy_callback(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        item_type = select.values[0]
        user_id = str(inter.author.id)
        
        # ตั้งราคา (สามารถดึงจาก Firebase ได้ในอนาคต)
        prices = {"netflix": 50, "youtube": 30}
        price = prices.get(item_type, 999)
        
        user_bal = get_user_balance(user_id)
        stocks = ref.child(f'stocks/{item_type}').get()
        
        if not stocks:
            return await inter.response.send_message("❌ สินค้าหมดชั่วคราว!", ephemeral=True)
        
        if user_bal < price:
            return await inter.response.send_message(f"❌ เงินไม่พอ! (มี {user_bal} บาท ขาดอีก {price - user_bal} บาท)", ephemeral=True)

        # ดึงสินค้าชิ้นแรก
        item_id = list(stocks.keys())[0]
        item_detail = stocks[item_id]

        # หักเงินและลบของออกจากฐานข้อมูล
        ref.child(f'users/{user_id}').update({'balance': user_bal - price})
        ref.child(f'stocks/{item_type}/{item_id}').delete()

        # แก้ไขจุดที่ Syntax Error แล้ว (ปิดเครื่องหมายคำพูดและ Code block ให้ครบ)
        embed = disnake.Embed(title="✅ สั่งซื้อสำเร็จ!", color=0x2ecc71)
        embed.add_field(name="📦 สินค้าที่ได้รับ", value=f"```\n{item_detail}\n```", inline=False)
        embed.set_footer(text=f"หักเงิน {price} บาท | ยอดเงินคงเหลือ {user_bal - price} บาท")
        
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion:bal_v2", emoji="💎")
    async def check_bal(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        bal = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินของคุณ: **{bal}** บาท", ephemeral=True)

# --- 4. ปุ่มอนุมัติสลิปสำหรับแอดมิน ---
class ConfirmPayment(disnake.ui.View):
    def __init__(self, customer_id):
        super().__init__(timeout=None)
        self.customer_id = customer_id

    @disnake.ui.button(label="อนุมัติยอดเงิน", style=disnake.ButtonStyle.success)
    async def confirm(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.administrator:
            return await inter.response.send_message("❌ เฉพาะแอดมินเท่านั้น", ephemeral=True)
        
        # ส่ง Modal ให้แอดมินกรอกยอดเงิน
        await inter.response.send_modal(
            title="ระบุจำนวนเงินที่ได้รับ",
            custom_id="modal_topup",
            components=[disnake.ui.TextInput(label="จำนวนเงิน", custom_id="amt", placeholder="เช่น 100")]
        )

# --- 5. ตัวบอทหลัก ---
class SECXION_STORE(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"✅ บอท {self.user} ออนไลน์พร้อมระบบ Firebase")

    async def on_message(self, message):
        if message.author.bot: return
        
        # ระบบตรวจสลิป (ส่งรูป = แจ้งเติมเงิน)
        if message.attachments:
            for attach in message.attachments:
                if any(attach.filename.lower().endswith(e) for e in ['.png', '.jpg', '.jpeg']):
                    embed = disnake.Embed(title="🔔 แจ้งโอนเงิน", description=f"ลูกค้า: {message.author.mention}", color=0xf1c40f)
                    embed.set_image(url=attach.url)
                    # ปุ่มจะผูก ID ลูกค้าไว้
                    await message.reply(embed=embed, view=ConfirmPayment(message.author.id))
        
        await self.process_commands(message)

    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id == "modal_topup":
            amount = float(inter.text_values["amt"])
            # ดึง ID ลูกค้าจาก Embed description
            customer_id = inter.message.embeds[0].description.split(":")[1].strip("<@! >")
            
            curr = get_user_balance(customer_id)
            ref.child(f'users/{customer_id}').update({'balance': curr + amount})
            await inter.response.send_message(f"✅ เติมเงินให้ <@{customer_id}> {amount} บาทสำเร็จ!")

bot = SECXION_STORE()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🏪 **SECXION STORE**", view=ShopView())

bot.run(os.getenv("TOKEN"))
