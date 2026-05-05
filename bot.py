import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. SETUP FIREBASE ---
FIREBASE_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
firebase_config_raw = os.getenv("FIREBASE_CONFIG")

try:
    if firebase_config_raw:
        cred = credentials.Certificate(json.loads(firebase_config_raw))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        ref = db.reference('/')
except Exception as e:
    print(f"Firebase Error: {e}")

def get_user_balance(user_id):
    try:
        data = ref.child('users').child(str(user_id)).get()
        return data.get('balance', 0) if data else 0
    except: return 0

# --- 2. SHOP SYSTEM ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="🛒 เลือกสินค้า",
        custom_id="secxion_shop_vFinal",
        options=[
            disnake.SelectOption(label="Netflix", value="netflix"),
            disnake.SelectOption(label="YouTube", value="youtube")
        ]
    )
    async def buy_callback(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        item_type = select.values[0]
        user_id = str(inter.author.id)
        
        # ตั้งค่าราคา
        prices = {"netflix": 50, "youtube": 30}
        price = prices.get(item_type, 999)
        
        balance = get_user_balance(user_id)
        stocks = ref.child(f'stocks/{item_type}').get()
        
        if not stocks or balance < price:
            return await inter.response.send_message("❌ สินค้าหมดหรือเงินไม่พอ", ephemeral=True)

        # ดึงของชิ้นแรก
        item_id = list(stocks.keys())[0]
        item_detail = str(stocks[item_id])

        # อัปเดต Database
        ref.child(f'users/{user_id}').update({'balance': balance - price})
        ref.child(f'stocks/{item_type}/{item_id}').delete()

        # --- แก้ปัญหา SyntaxError ถาวร: ใช้ Format แบบปลอดภัยที่สุด ---
        # ไม่ใช้ f-string, ไม่ใช้เครื่องหมายบวกซ้อนกัน
        msg_template = "```\n{}\n
```"
        success_msg = msg_template.format(item_detail)
        
        emb = disnake.Embed(title="✅ ซื้อสินค้าสำเร็จ", description=success_msg, color=0x00ff00)
        await inter.response.send_message(embed=emb, ephemeral=True)

    @disnake.ui.button(label="เช็คเงิน", style=disnake.ButtonStyle.gray, custom_id="check_bal_vFinal")
    async def bal_btn(self, button, inter):
        bal = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินปัจจุบัน: {bal} บาท", ephemeral=True)

# --- 3. ADMIN & BOT SETUP ---
class AdminView(disnake.ui.View):
    def __init__(self, cust_id):
        super().__init__(timeout=None)
        self.cust_id = cust_id

    @disnake.ui.button(label="อนุมัติเงิน", style=disnake.ButtonStyle.green)
    async def approve(self, button, inter):
        if not inter.author.guild_permissions.administrator: return
        await inter.response.send_modal(
            title="เติมเงิน",
            custom_id="modal_topup",
            components=[disnake.ui.TextInput(label="จำนวนเงิน", custom_id="amt")]
        )

class SecxionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print("✅ BOT READY")

    async def on_message(self, message):
        if message.author.bot: return
        if message.attachments:
            emb = disnake.Embed(title="ตรวจสอบสลิป", description=f"ID:({message.author.id})", color=0xffff00)
            emb.set_image(url=message.attachments[0].url)
            await message.reply(embed=emb, view=AdminView(message.author.id))
        await self.process_commands(message)

    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id == "modal_topup":
            amount = float(inter.text_values["amt"])
            # ดึง ID ลูกค้าจาก Description
            raw_id = inter.message.embeds[0].description.split("(")[1].replace(")", "")
            old_bal = get_user_balance(raw_id)
            ref.child(f'users/{raw_id}').update({'balance': old_bal + amount})
            await inter.response.send_message(f"✅ เติมเงินให้ {raw_id} แล้ว {amount} บาท")

bot = SecxionBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🏪 **SECXION STORE**", view=ShopView())

bot.run(os.getenv("TOKEN"))
