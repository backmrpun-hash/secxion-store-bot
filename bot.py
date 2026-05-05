import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. การตั้งค่าฐานข้อมูล Firebase ---
# ดึงค่าจาก Environment Variable ที่ชื่อ FIREBASE_CONFIG ใน Railway
firebase_config_raw = os.getenv("FIREBASE_CONFIG")
database_url = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"

if firebase_config_raw:
    # กรณีรันบน Railway
    cred_dict = json.loads(firebase_config_raw)
    cred = credentials.Certificate(cred_dict)
else:
    # กรณีรันในคอมตัวเอง (ต้องมีไฟล์อยู่ในโฟลเดอร์)
    cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred, {
    'databaseURL': database_url
})

ref = db.reference('/')

# --- 2. ฟังก์ชันจัดการข้อมูล (Firebase Logic) ---
def get_user_balance(user_id):
    data = ref.child('users').child(str(user_id)).get()
    return data.get('balance', 0) if data else 0

def add_stock_item(item_type, content):
    ref.child('stocks').child(item_type).push().set(content)

# --- 3. ระบบหน้ากากร้านค้า (Persistent View) ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="[ เลือกหมวดหมู่สินค้า ]",
        custom_id="secxion:select",
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺")
        ]
    )
    async def select_callback(self, inter: disnake.MessageInteraction, select):
        item_type = select.values[0]
        # ดึงสต็อกจริงจาก Firebase
        stock_data = ref.child('stocks').child(item_type).get()
        count = len(stock_data) if stock_data else 0
        
        embed = disnake.Embed(title=f"📦 รายการ: {item_type.upper()}", color=0x2b2d31)
        embed.add_field(name="📦 คงเหลือ", value=f"` {count} ` ชิ้น", inline=True)
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คยอดเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion:bal", emoji="💎")
    async def check_bal(self, inter: disnake.MessageInteraction, button):
        balance = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินของคุณ: **{balance}** บาท", ephemeral=True)

class SECXION_STORE(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"✅ {self.user} Online (Firebase: SECXION STORE Connected)")

bot = SECXION_STORE()

# --- 4. ระบบหลังบ้าน (แอดมินใช้คำสั่งใน Discord) ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """วางหน้าร้านค้า"""
    embed = disnake.Embed(title="SECXION STORE", description="ระบบร้านค้าอัตโนมัติเชื่อมต่อ Firebase", color=0x2b2d31)
    embed.set_footer(text="ฐานข้อมูล Real-time | ข้อมูลไม่มีวันหาย")
    await ctx.send(embed=embed, view=ShopView())

@bot.command()
@commands.has_permissions(administrator=True)
async def addstock(ctx, type: str, *, content: str):
    """เพิ่มของลงสต็อก: !addstock netflix id:pass"""
    add_stock_item(type, content)
    await ctx.send(f"✅ เพิ่มของลงสต็อก `{type}` เรียบร้อยแล้ว!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setmoney(ctx, member: disnake.Member, amount: float):
    """ปรับเงินลูกค้า: !setmoney @user 500"""
    ref.child('users').child(str(member.id)).update({'balance': amount})
    await ctx.send(f"✅ ปรับเงินให้ {member.mention} เป็น {amount} บาท")

bot.run(os.getenv("TOKEN"))
