import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json
import datetime

# --- 1. ตั้งค่า Firebase ---
firebase_config_raw = os.getenv("FIREBASE_CONFIG")
# แก้บรรทัดนี้ใน bot.py ให้ตรงกับของคุณ
database_url = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"

if firebase_config_raw:
    cred_dict = json.loads(firebase_config_raw)
    cred = credentials.Certificate(cred_dict)
else:
    cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred, {'databaseURL': database_url})
ref = db.reference('/')

# --- 2. ฟังก์ชันจัดการข้อมูล ---
def get_user_balance(user_id):
    data = ref.child('users').child(str(user_id)).get()
    return data.get('balance', 0) if data else 0

# --- 3. ระบบร้านค้าและเติมเงิน (UI) ---
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
        stock_data = ref.child('stocks').child(item_type).get()
        count = len(stock_data) if stock_data else 0
        embed = disnake.Embed(title=f"📦 รายการ: {item_type.upper()}", color=0x2b2d31)
        embed.add_field(name="📦 คงเหลือ", value=f"` {count} ` ชิ้น", inline=True)
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เติมเงิน (ส่งสลิป)", style=disnake.ButtonStyle.primary, custom_id="secxion:topup", emoji="💰")
    async def topup(self, inter: disnake.MessageInteraction, button):
        embed = disnake.Embed(
            title="💰 วิธีการเติมเงิน",
            description="1. โอนเงินมาที่ [เลขบัญชี/วอลเล็ต ของคุณ]\n2. **ส่งรูปสลิป** เข้ามาในห้องนี้ได้เลย\n3. รอแอดมินตรวจสอบยอดเงิน",
            color=disnake.Color.green()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

    @disnake.ui.button(label="เช็คยอดเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion:bal", emoji="💎")
    async def check_bal(self, inter: disnake.MessageInteraction, button):
        balance = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินของคุณ: **{balance}** บาท", ephemeral=True)

# --- 4. ปุ่มยืนยันยอดเงินสำหรับแอดมิน ---
class AdminConfirmView(disnake.ui.View):
    def __init__(self, user_id, amount):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.amount = amount

    @disnake.ui.button(label="อนุมัติเงิน", style=disnake.ButtonStyle.success)
    async def confirm(self, inter: disnake.MessageInteraction, button):
        current_bal = get_user_balance(self.user_id)
        ref.child('users').child(str(self.user_id)).update({'balance': current_bal + self.amount})
        await inter.response.send_message(f"✅ เติมเงินให้ <@{self.user_id}> จำนวน {self.amount} บาท เรียบร้อย!", ephemeral=False)
        self.stop()

class SECXION_STORE(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"✅ {self.user} Online (Firebase: SECXION STORE Connected)")

    async def on_message(self, message):
        if message.author.bot: return
        # ตรวจจับสลิปในห้องที่กำหนด (เปลี่ยน ID ห้องตรงนี้)
        if message.attachments:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg']):
                    # ส่งให้แอดมินตรวจสอบ (ในที่นี้คือส่งกลับไปให้แอดมินกดในห้องนั้น หรือห้อง Log)
                    embed = disnake.Embed(title="🔔 มีการแจ้งโอนเงินใหม่", color=disnake.Color.gold())
                    embed.add_field(name="จากคุณ", value=message.author.mention)
                    embed.set_image(url=attachment.url)
                    await message.reply("⏳ ได้รับสลิปแล้ว! รอแอดมินตรวจสอบสักครู่ครับ", delete_after=10)
                    # ส่วนนี้แอดมินมาพิมพ์ !confirm_topup @user ยอดเงิน ต่อไป
        await self.process_commands(message)

bot = SECXION_STORE()

# --- 5. คำสั่งแอดมิน ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = disnake.Embed(title="SECXION STORE", description="ระบบร้านค้า & แจ้งโอนเงินอัตโนมัติ", color=0x2b2d31)
    await ctx.send(embed=embed, view=ShopView())

@bot.command()
@commands.has_permissions(administrator=True)
async def addmoney(ctx, member: disnake.Member, amount: float):
    """แอดมินกดยืนยันยอดเงินจากสลิป: !addmoney @user 100"""
    current = get_user_balance(member.id)
    ref.child('users').child(str(member.id)).update({'balance': current + amount})
    await ctx.send(f"✅ เติมเงินให้ {member.mention} จำนวน {amount} บาทสำเร็จ!")

bot.run(os.getenv("TOKEN"))
