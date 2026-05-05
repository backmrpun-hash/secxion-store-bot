import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. FIREBASE SETUP ---
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
        custom_id="shop_final_fix",
        options=[
            disnake.SelectOption(label="Netflix", value="netflix"),
            disnake.SelectOption(label="YouTube", value="youtube")
        ]
    )
    async def buy_callback(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        item_type = select.values[0]
        user_id = str(inter.author.id)
        
        # ราคา
        prices = {"netflix": 50, "youtube": 30}
        price = prices.get(item_type, 999)
        
        balance = get_user_balance(user_id)
        stocks = ref.child(f'stocks/{item_type}').get()
        
        if not stocks or balance < price:
            return await inter.response.send_message("❌ สินค้าหมดหรือเงินไม่พอ", ephemeral=True)

        item_id = list(stocks.keys())[0]
        item_detail = str(stocks[item_id])

        # อัปเดตข้อมูล
        ref.child(f'users/{user_id}').update({'balance': balance - price})
        ref.child(f'stocks/{item_type}/{item_id}').delete()

        # --- แก้ปัญหา SyntaxError: ใช้ .replace() เพื่อเลี่ยงการขึ้นบรรทัดใหม่ใน Code ---
        # วิธีนี้จะไม่มีเครื่องหมายคำพูดเปิดค้างไว้ให้ Python งง
        display_code = "CODE_START\nCONTENT\nCODE_END"
        display_code = display_code.replace("CODE_START", "```").replace("CODE_END", "
```").replace("CONTENT", item_detail)
        
        emb = disnake.Embed(title="✅ สำเร็จ", description=display_code, color=0x00ff00)
        await inter.response.send_message(embed=emb, ephemeral=True)

    @disnake.ui.button(label="เช็คเงิน", style=disnake.ButtonStyle.gray, custom_id="bal_final_fix")
    async def bal_btn(self, button, inter):
        bal = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 เงินคงเหลือ: {bal} บาท", ephemeral=True)

# --- 3. ADMIN & MODAL ---
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
            components=[disnake.ui.TextInput(label="จำนวน", custom_id="amt")]
        )

class SecxionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"BOT ONLINE: {self.user}")

    async def on_message(self, message):
        if message.author.bot: return
        if message.attachments:
            # ใช้ format แบบปลอดภัยป้องกัน ID หลุด
            desc = "ID: ({})".format(message.author.id)
            emb = disnake.Embed(title="สลิปใหม่", description=desc, color=0xffff00)
            emb.set_image(url=message.attachments[0].url)
            await message.reply(embed=emb, view=AdminView(message.author.id))
        await self.process_commands(message)

    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id == "modal_topup":
            amount = float(inter.text_values["amt"])
            # ดึง ID จากวงเล็บ
            raw_id = inter.message.embeds[0].description.split("(")[1].replace(")", "")
            old = get_user_balance(raw_id)
            ref.child(f'users/{raw_id}').update({'balance': old + amount})
            await inter.response.send_message(f"✅ เติมเงินให้ {raw_id} เรียบร้อย")

bot = SecxionBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🏪 **STORE**", view=ShopView())

bot.run(os.getenv("TOKEN"))
