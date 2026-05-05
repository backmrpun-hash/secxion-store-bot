import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. ตั้งค่า Firebase ---
FIREBASE_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
firebase_config_raw = os.getenv("FIREBASE_CONFIG")

try:
    if firebase_config_raw:
        cred = credentials.Certificate(json.loads(firebase_config_raw))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
    ref = db.reference('/')
    print("✅ Firebase Connected!")
except Exception as e:
    print(f"❌ Firebase Error: {e}")

# --- 2. ฟังก์ชันช่วย ---
def get_user_balance(user_id):
    try:
        data = ref.child('users').child(str(user_id)).get()
        return data.get('balance', 0) if data else 0
    except: return 0

# --- 3. ระบบร้านค้า ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="🛒 เลือกสินค้าที่ต้องการซื้อ",
        custom_id="secxion:shop_final",
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺")
        ]
    )
    async def buy_callback(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        item_type = select.values[0]
        user_id = str(inter.author.id)
        
        prices = {"netflix": 50, "youtube": 30}
        price = prices.get(item_type, 999)
        
        bal = get_user_balance(user_id)
        stocks = ref.child(f'stocks/{item_type}').get()
        
        if not stocks:
            return await inter.response.send_message("❌ สินค้าหมด!", ephemeral=True)
        if bal < price:
            return await inter.response.send_message(f"❌ เงินไม่พอ (คุณมี {bal} บาท)", ephemeral=True)

        # ดึงสินค้า
        item_id = list(stocks.keys())[0]
        item_detail = str(stocks[item_id])

        # หักเงินและลบของ
        ref.child(f'users/{user_id}').update({'balance': bal - price})
        ref.child(f'stocks/{item_type}/{item_id}').delete()

        # --- แก้ไขจุด Syntax Error แบบเด็ดขาด ---
        # แยกข้อความออกมาก่อน ไม่ต้องใส่ f-string ซ้อนใน add_field
        display_text = "```\n" + item_detail + "\n
```"
        
        embed = disnake.Embed(title="✅ ซื้อสินค้าสำเร็จ", color=0x00ff00)
        embed.add_field(name="📦 รายละเอียดสินค้า", value=display_text, inline=False)
        embed.set_footer(text=f"คงเหลือ {bal - price} บาท")
        
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คเงิน", style=disnake.ButtonStyle.gray, custom_id="secxion:bal_final")
    async def bal_btn(self, button, inter):
        bal = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงิน: **{bal}** บาท", ephemeral=True)

# --- 4. ระบบแอดมิน ---
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

# --- 5. บอทหลัก ---
class SecxionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"✅ {self.user} พร้อมรัน!")

    async def on_message(self, message):
        if message.author.bot: return
        if message.attachments:
            # ระบบตรวจสลิป
            emb = disnake.Embed(title="ยืนยันการโอน", description=f"ลูกค้า: {message.author.mention} ({message.author.id})", color=0xffff00)
            emb.set_image(url=message.attachments[0].url)
            await message.reply(embed=emb, view=AdminView(message.author.id))
        await self.process_commands(message)

    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id == "modal_topup":
            amount = float(inter.text_values["amt"])
            # ดึง ID จาก Embed
            raw_id = inter.message.embeds[0].description.split("(")[1].replace(")", "")
            
            old = get_user_balance(raw_id)
            ref.child(f'users/{raw_id}').update({'balance': old + amount})
            await inter.response.send_message(f"✅ เติมเงินให้ <@{raw_id}> {amount} บาทแล้ว")

bot = SecxionBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🏪 **SECXION STORE**", view=ShopView())

bot.run(os.getenv("TOKEN"))
