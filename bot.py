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
    # อ่านค่าจาก Railway Variables
    cred_dict = json.loads(firebase_config_raw)
    cred = credentials.Certificate(cred_dict)
else:
    # สำหรับการรันในคอมพิวเตอร์ส่วนตัว
    cred = credentials.Certificate("serviceAccountKey.json")

# ป้องกันการ Initialize ซ้ำซ้อน
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {'databaseURL': database_url})

ref = db.reference('/')

# --- 2. ฟังก์ชันจัดการข้อมูล (Firebase) ---
def get_user_balance(user_id):
    data = ref.child('users').child(str(user_id)).get()
    return data.get('balance', 0) if data else 0

# --- 3. ระบบร้านค้า (Persistent View) ---
class ShopView(disnake.ui.View):
    def __init__(self):
        # ตั้งค่า timeout=None เพื่อให้ปุ่มทำงานได้ตลอดไปแม้บอทรีสตาร์ท
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="[ เลือกหมวดหมู่สินค้า ]",
        custom_id="secxion:category_select", # ID คงที่เพื่อป้องกัน Interaction Failed
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬", description="ราคา 50 บาท"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺", description="ราคา 30 บาท")
        ]
    )
    async def select_callback(self, inter: disnake.MessageInteraction, select):
        item_type = select.values[0]
        # ดึงสต็อกจริงจาก Firebase มาแสดงผล
        stock_data = ref.child('stocks').child(item_type).get()
        count = len(stock_data) if stock_data else 0
        
        embed = disnake.Embed(title=f"📦 รายการ: {item_type.upper()}", color=0x2b2d31)
        embed.add_field(name="📦 คงเหลือ", value=f"` {count} ` ชิ้น", inline=True)
        embed.set_footer(text="ระบบตรวจสอบสต็อกแบบ Real-time")
        
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เติมเงิน (ส่งสลิป)", style=disnake.ButtonStyle.primary, custom_id="secxion:topup_btn", emoji="💰")
    async def topup(self, inter: disnake.MessageInteraction, button):
        embed = disnake.Embed(
            title="💰 แจ้งโอนเงิน",
            description="กรุณาโอนเงินตามยอดที่ต้องการและ**ส่งรูปสลิป**ในห้องนี้\nจากนั้นรอแอดมินยืนยันยอดเงินครับ",
            color=disnake.Color.green()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คยอดเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion:bal_btn", emoji="💎")
    async def check_bal(self, inter: disnake.MessageInteraction, button):
        balance = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินปัจจุบัน: **{balance}** บาท", ephemeral=True)

# --- 4. ตัวบอทและการรันระบบ ---
class SecxionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        # ลงทะเบียน View เดิมให้บอทจำได้
        self.add_view(ShopView())
        print(f"✅ SECXION STORE เชื่อมต่อ Firebase สำเร็จ!")

bot = SecxionBot()

# --- 5. คำสั่งหลังบ้านสำหรับแอดมิน ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """วางหน้าร้านค้าใหม่"""
    embed = disnake.Embed(title="SECXION STORE", description="ระบบซื้อขายอัตโนมัติ 24 ชม.", color=0x2b2d31)
    embed.set_image(url="https://media.discordapp.net/attachments/your_banner.png")
    await ctx.send(embed=embed, view=ShopView())
    await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def addstock(ctx, type: str, *, content: str):
    """เพิ่มของ: !addstock netflix user:pass"""
    ref.child('stocks').child(type).push().set(content)
    await ctx.send(f"✅ เพิ่มสินค้าลง `{type}` เรียบร้อยแล้ว!")

@bot.command()
@commands.has_permissions(administrator=True)
async def addmoney(ctx, member: disnake.Member, amount: float):
    """เติมเงินให้ลูกค้า: !addmoney @user 100"""
    current = get_user_balance(member.id)
    ref.child('users').child(str(member.id)).update({'balance': current + amount})
    await ctx.send(f"✅ เติมเงินให้ {member.mention} จำนวน {amount} บาทสำเร็จ!")

bot.run(os.getenv("TOKEN"))
