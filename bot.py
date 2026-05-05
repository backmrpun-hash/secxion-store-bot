import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- 1. การตั้งค่า Firebase ---
database_url = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
firebase_config_raw = os.getenv("FIREBASE_CONFIG")

if firebase_config_raw:
    cred_dict = json.loads(firebase_config_raw)
    cred = credentials.Certificate(cred_dict)
else:
    # สำหรับรันในคอมตัวเอง (ถ้ามีไฟล์)
    cred = credentials.Certificate("serviceAccountKey.json")

# ตรวจสอบว่ายังไม่มีการ Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {'databaseURL': database_url})

ref = db.reference('/')

# --- 2. ฟังก์ชันฐานข้อมูล ---
def get_user_balance(user_id):
    data = ref.child('users').child(str(user_id)).get()
    return data.get('balance', 0) if data else 0

# --- 3. ระบบหน้ากากร้านค้า (ใช้ Custom ID แบบคงที่) ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # ห้ามหมดอายุ

    @disnake.ui.select(
        placeholder="[ เลือกหมวดหมู่สินค้า ]",
        custom_id="secxion_store:select_category", # ID ต้องห้ามเปลี่ยน
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺")
        ]
    )
    async def select_callback(self, inter: disnake.MessageInteraction, select):
        item_type = select.values[0]
        stock_data = ref.child('stocks').child(item_type).get()
        count = len(stock_data) if stock_data else 0
        
        embed = disnake.Embed(title=f"📦 รายการ: {item_type.upper()}", color=0x2b2d31)
        embed.add_field(name="📦 คงเหลือ", value=f"` {count} ` ชิ้น", inline=True)
        # ส่งข้อความแบบเห็นคนเดียวเพื่อลด Interaction Failed
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เติมเงิน", style=disnake.ButtonStyle.primary, custom_id="secxion_store:topup", emoji="💰")
    async def topup(self, inter: disnake.MessageInteraction, button):
        embed = disnake.Embed(
            title="💰 วิธีการเติมเงิน",
            description="โอนเงินผ่านบัญชีธนาคาร/วอลเล็ต แล้ว**ส่งรูปสลิป**ในห้องนี้\nรอแอดมินตรวจสอบสักครู่ครับ",
            color=disnake.Color.green()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คยอดเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion_store:balance", emoji="💎")
    async def check_bal(self, inter: disnake.MessageInteraction, button):
        balance = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินของคุณ: **{balance}** บาท", ephemeral=True)

# --- 4. ตัวบอทหลัก ---
class SecxionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        # สำคัญมาก: ลงทะเบียน View เพื่อให้ปุ่มเก่าทำงานได้หลังรีสตาร์ท
        self.add_view(ShopView())
        print(f"✅ บอทออนไลน์: {self.user} | Firebase Connected")

bot = SecxionBot()

# --- 5. คำสั่งจัดการสต็อกและเงิน ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """ใช้คำสั่งนี้เพื่อวางหน้าร้านใหม่"""
    embed = disnake.Embed(title="SECXION STORE", description="ระบบร้านค้าอัตโนมัติ (Firebase Real-time)", color=0x2b2d31)
    embed.set_footer(text="ข้อมูลเงินและสต็อกปลอดภัย 100%")
    await ctx.send(embed=embed, view=ShopView())
    await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def addstock(ctx, type: str, *, content: str):
    """วิธีใช้: !addstock netflix id:pass"""
    ref.child('stocks').child(type).push().set(content)
    await ctx.send(f"✅ เพิ่มของลงสต็อก `{type}` เรียบร้อย!")

@bot.command()
@commands.has_permissions(administrator=True)
async def addmoney(ctx, member: disnake.Member, amount: float):
    """ยืนยันยอดเงินจากสลิป: !addmoney @ชื่อลูกค้า 100"""
    current = get_user_balance(member.id)
    ref.child('users').child(str(member.id)).update({'balance': current + amount})
    await ctx.send(f"✅ เติมเงินให้ {member.mention} จำนวน {amount} บาทสำเร็จ!")

bot.run(os.getenv("TOKEN"))
