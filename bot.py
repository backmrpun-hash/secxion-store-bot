import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. ตั้งค่า Firebase (ล้าง URL ให้สะอาดที่สุด) ---
FIREBASE_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
firebase_config_raw = os.getenv("FIREBASE_CONFIG")

try:
    if firebase_config_raw:
        # ใช้ Config จาก Environment Variable (Railway)
        cred_dict = json.loads(firebase_config_raw)
        cred = credentials.Certificate(cred_dict)
    else:
        # ใช้ไฟล์ local สำหรับทดสอบ
        cred = credentials.Certificate("serviceAccountKey.json")

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_URL
        })
    
    # เชื่อมต่อ Database Reference
    ref = db.reference('/')
    print("✅ Firebase Connected Successfully!")
except Exception as e:
    print(f"❌ Firebase Error: {e}")

# --- 2. ฟังก์ชันดึงยอดเงิน ---
def get_user_balance(user_id):
    try:
        data = ref.child('users').child(str(user_id)).get()
        return data.get('balance', 0) if data else 0
    except:
        return 0

# --- 3. UI ระบบร้านค้า ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="🛒 เลือกสินค้าที่ต้องการซื้อ",
        custom_id="secxion_shop:select_v3",
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬", description="50 บาท"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺", description="30 บาท")
        ]
    )
    async def buy_item(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        item_type = select.values[0]
        user_id = str(inter.author.id)
        
        prices = {"netflix": 50, "youtube": 30}
        price = prices.get(item_type, 999)
        
        bal = get_user_balance(user_id)
        stocks = ref.child(f'stocks/{item_type}').get()
        
        if not stocks:
            return await inter.response.send_message("❌ สินค้าในสต็อกหมด!", ephemeral=True)
        if bal < price:
            return await inter.response.send_message(f"❌ เงินไม่พอ (มี {bal} บาท)", ephemeral=True)

        # จ่ายเงินและดึงของ
        item_id = list(stocks.keys())[0]
        item_detail = stocks[item_id]
        
        ref.child(f'users/{user_id}').update({'balance': bal - price})
        ref.child(f'stocks/{item_type}/{item_id}').delete()

        embed = disnake.Embed(title="✅ ซื้อสินค้าสำเร็จ", color=0x00ff00)
        embed.add_field(name="📦 รายละเอียดสินค้า", value=f"```\n{item_detail}\n
```", inline=False)
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คยอดเงิน", style=disnake.ButtonStyle.gray, custom_id="secxion_shop:bal_v3")
    async def check_bal(self, button, inter):
        bal = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินคงเหลือ: **{bal}** บาท", ephemeral=True)

# --- 4. ระบบยืนยันสลิป (Admin) ---
class AdminConfirmView(disnake.ui.View):
    def __init__(self, customer_id):
        super().__init__(timeout=None)
        self.customer_id = customer_id

    @disnake.ui.button(label="อนุมัติเงิน", style=disnake.ButtonStyle.green)
    async def approve(self, button, inter):
        if not inter.author.guild_permissions.administrator:
            return await inter.response.send_message("❌ สำหรับแอดมินเท่านั้น", ephemeral=True)
        
        await inter.response.send_modal(
            title="ระบุจำนวนเงิน",
            custom_id="modal_add_money",
            components=[disnake.ui.TextInput(label="บาท", custom_id="amount_val")]
        )

# --- 5. ตัวบอท ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"Logged in as {self.user}")

    async def on_message(self, message):
        if message.author.bot: return
        # ตรวจสอบสลิป (ถ้าส่งรูปมา)
        if message.attachments:
            embed = disnake.Embed(title="ตรวจสอบสลิป", description=f"จาก: {message.author.mention}", color=0xffff00)
            embed.set_image(url=message.attachments[0].url)
            await message.reply(embed=embed, view=AdminConfirmView(message.author.id))
        await self.process_commands(message)

    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id == "modal_add_money":
            amt = float(inter.text_values["amount_val"])
            # ดึง ID ลูกค้าจาก Embed ที่ปุ่มนั้นอยู่
            cust_id = inter.message.embeds[0].description.split(":")[1].strip("<@! >")
            
            old_bal = get_user_balance(cust_id)
            ref.child(f'users/{cust_id}').update({'balance': old_bal + amt})
            await inter.response.send_message(f"✅ เติมเงินให้ <@{cust_id}> จำนวน {amt} บาทแล้ว")

bot = MyBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🏪 **SECXION STORE**", view=ShopView())

bot.run(os.getenv("TOKEN"))
