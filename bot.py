import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os

# --- 1. ตั้งค่า Firebase ---
# ตรวจสอบว่ามีไฟล์ serviceAccountKey.json ในโฟลเดอร์เดียวกับบอท
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'ใส่_Database_URL_ของคุณที่นี่' # หาได้จากหน้า Realtime Database ใน Firebase
})

ref = db.reference('/')

# --- 2. ฟังก์ชันจัดการข้อมูล ---
def get_bal(user_id):
    data = ref.child('users').child(str(user_id)).get()
    return data.get('balance', 0) if data else 0

def add_stock_item(item_type, content):
    ref.child('stocks').child(item_type).push().set(content)

# --- 3. ส่วนของร้านค้า (Persistent View) ---
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
        # นับสต็อกจริงจาก Firebase
        stock_data = ref.child('stocks').child(item_type).get()
        count = len(stock_data) if stock_data else 0
        
        embed = disnake.Embed(title=f"📦 รายการ: {item_type.upper()}", color=0x2b2d31)
        embed.add_field(name="📦 คงเหลือ", value=f"` {count} ` ชิ้น", inline=True)
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คยอดเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion:bal", emoji="💎")
    async def check_bal(self, inter: disnake.MessageInteraction, button):
        balance = get_bal(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินของคุณ: **{balance}** บาท", ephemeral=True)

class SECXION_STORE(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"✅ {self.user} Online (Firebase Database Connected)")

bot = SECXION_STORE()

# --- 4. ระบบหลังบ้าน (Backoffice) ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = disnake.Embed(title="SECXION STORE", description="ระบบร้านค้าอัตโนมัติเชื่อมต่อ Firebase", color=0x2b2d31)
    await ctx.send(embed=embed, view=ShopView())

@bot.command()
@commands.has_permissions(administrator=True)
async def addstock(ctx, type: str, *, content: str):
    add_stock_item(type, content)
    await ctx.send(f"✅ เพิ่มของลงสต็อก `{type}` ใน Firebase สำเร็จ!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setmoney(ctx, member: disnake.Member, amount: float):
    ref.child('users').child(str(member.id)).update({'balance': amount})
    await ctx.send(f"✅ ปรับเงินให้ {member.mention} เรียบร้อย")

bot.run(os.getenv("TOKEN"))
