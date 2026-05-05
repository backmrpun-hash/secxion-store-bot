import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. SETUP ระบบพื้นฐาน ---
TOKEN = os.getenv("TOKEN")
DB_URL = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
FB_CONF = os.getenv("FIREBASE_CONFIG")

# เชื่อมต่อ Firebase แบบเช็คสถานะ
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    ref = db.reference('/')
    print("✅ DATABASE CONNECTED")
except Exception as e:
    print(f"❌ DATABASE ERROR: {e}")

# --- 2. CLASS ร้านค้า (กันปุ่มหาย) ---
class Shop(disnake.ui.View):
    def __init__(self):
        # timeout=None สำคัญมาก เพื่อไม่ให้ปุ่มหมดอายุหลังบอทรันไปนานๆ
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="🛒 เลือกสินค้าที่นี่",
        custom_id="secxion_store_v1", # ID ต้องห้ามซ้ำกับของเก่า
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺")
        ]
    )
    async def select_callback(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        item_type = select.values[0]
        user_id = str(inter.author.id)
        
        # ราคาและข้อมูล
        prices = {"netflix": 50, "youtube": 30}
        price = prices.get(item_type, 999)
        
        # ดึงข้อมูลจาก Firebase
        user_data = ref.child('users').child(user_id).get()
        balance = user_data.get('balance', 0) if user_data else 0
        stocks = ref.child('stocks').child(item_type).get()

        if not stocks:
            return await inter.response.send_message("❌ สินค้าหมดชั่วคราว!", ephemeral=True)
        
        if balance < price:
            return await inter.response.send_message(f"❌ เงินไม่พอ! คุณมี {balance} บาท", ephemeral=True)

        # จ่ายเงินและส่งของ
        item_id = list(stocks.keys())[0]
        item_detail = str(stocks[item_id])

        ref.child('users').child(user_id).update({'balance': balance - price})
        ref.child('stocks').child(item_type).child(item_id).delete()

        # ส่งของแบบข้อความธรรมดา (กัน Syntax Error)
        success_text = f"✅ ซื้อสำเร็จ!\nรายละเอียด: {item_detail}\nคงเหลือ: {balance - price} บาท"
        await inter.response.send_message(success_text, ephemeral=True)

# --- 3. บอทหลัก ---
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    # ลงทะเบียน View เพื่อให้ปุ่มทำงานได้ตลอดเวลาแม้รีสตาร์ทบอท
    bot.add_view(Shop())
    print(f"🚀 {bot.user} พร้อมใช้งานแล้ว!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    # คำสั่งสร้างหน้าร้าน
    embed = disnake.Embed(
        title="🏪 SECXION STORE",
        description="กรุณาเลือกสินค้าจากเมนูด้านล่าง",
        color=0x2b2d31
    )
    await ctx.send(embed=embed, view=Shop())

bot.run(TOKEN)
