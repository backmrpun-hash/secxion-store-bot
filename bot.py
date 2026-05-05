import disnake
from disnake.ext import commands
import sqlite3
import os

# --- 1. ระบบฐานข้อมูล (SQLite) ---
def init_db():
    conn = sqlite3.connect('secxion_data.db')
    c = conn.cursor()
    # เก็บเงินผู้ใช้
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)''')
    # เก็บสต็อกสินค้า (แยกตามประเภท)
    c.execute('''CREATE TABLE IF NOT EXISTS stocks (id INTEGER PRIMARY KEY AUTOINCREMENT, item_type TEXT, info TEXT)''')
    conn.commit()
    conn.close()

init_db()

def db_query(query, params=(), fetchone=False):
    conn = sqlite3.connect('secxion_data.db')
    c = conn.cursor()
    c.execute(query, params)
    res = c.fetchone() if fetchone else c.fetchall()
    conn.commit()
    conn.close()
    return res

# --- 2. ระบบ UI หน้าร้าน (Persistent View) ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # สำคัญ: เพื่อให้ปุ่มทำงานได้ตลอดไป

    @disnake.ui.select(
        placeholder="[ เลือกหมวดหมู่สินค้าที่นี่ ]",
        custom_id="secxion:select",
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬", description="ราคา 50 บาท"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺", description="ราคา 30 บาท")
        ]
    )
    async def select_item(self, inter: disnake.MessageInteraction, select):
        item_type = select.values[0]
        # เช็คสต็อกจริงจาก DB
        stock_data = db_query("SELECT COUNT(*) FROM stocks WHERE item_type = ?", (item_type,), fetchone=True)
        count = stock_data[0] if stock_data else 0
        
        embed = disnake.Embed(title=f"📦 รายการสินค้า: {item_type.upper()}", color=0x2b2d31)
        embed.add_field(name="คงเหลือ", value=f"` {count} ` ชิ้น", inline=True)
        embed.set_footer(text="กดปุ่มด้านล่างเพื่อยืนยันการซื้อ")

        # สร้างปุ่มซื้อชั่วคราว (Ephemeral)
        buy_view = disnake.ui.View()
        buy_btn = disnake.ui.Button(label="ยืนยันการซื้อ", style=disnake.ButtonStyle.success, custom_id=f"buy:{item_type}")
        
        # Logic การกดซื้อ (ตัวอย่าง)
        async def buy_callback(interaction):
            # ตรวจสอบเงินและหักสต็อกที่นี่
            await interaction.response.send_message("กำลังตรวจสอบรายการ...", ephemeral=True)

        buy_btn.callback = buy_callback
        buy_view.add_item(buy_btn)
        
        await inter.response.send_message(embed=embed, view=buy_view, ephemeral=True)

    @disnake.ui.button(label="เติมเงินเข้าบัญชี", style=disnake.ButtonStyle.primary, custom_id="secxion:topup", emoji="💰")
    async def topup(self, inter: disnake.MessageInteraction, button):
        await inter.response.send_message("📌 กรุณาส่งสลิปโอนเงินเข้ามาในช่องแชทได้เลย ระบบจะตรวจสอบอัตโนมัติ", ephemeral=True)

    @disnake.ui.button(label="เช็คยอดเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion:balance", emoji="💎")
    async def check_bal(self, inter: disnake.MessageInteraction, button):
        user_bal = db_query("SELECT balance FROM users WHERE user_id = ?", (inter.author.id,), fetchone=True)
        balance = user_bal[0] if user_bal else 0
        await inter.response.send_message(f"💎 ยอดเงินปัจจุบันของคุณคือ: **{balance}** บาท", ephemeral=True)

# --- 3. ตัวบอทหลัก ---
class SecxionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView()) # ลงทะเบียน View ให้ทำงานตลอดเวลา
        print(f"✅ บอท {self.user} ออนไลน์แล้ว! (SECXION STORE)")

bot = SecxionBot()

# --- 4. ระบบหลังบ้าน (แอดมินเท่านั้น) ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """คำสั่งตั้งค่าหน้าร้านครั้งแรก"""
    embed = disnake.Embed(title="SECXION STORE", color=0x2b2d31)
    embed.description = (
        "**ระบบซื้อขายสินค้าอัตโนมัติ 24 ชม.**\n"
        "⁃ รองรับการเติมเงินผ่านธนาคาร และ Wallet\n"
        "⁃ สินค้าจัดส่งทันทีผ่านทางข้อความส่วนตัว (DM)"
    )
    embed.set_image(url="https://media.discordapp.net/attachments/your_image_path.png") # ใส่รูป Banner ร้านคุณ
    await ctx.send(embed=embed, view=ShopView())
    await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def addstock(ctx, type: str, *, content: str):
    """วิธีใช้: !addstock netflix email:pass"""
    db_query("INSERT INTO stocks (item_type, info) VALUES (?, ?)", (type, content))
    await ctx.send(f"✅ เพิ่มของลงสต็อก `{type}` สำเร็จ!", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def setmoney(ctx, member: disnake.Member, amount: float):
    """วิธีใช้: !setmoney @user 100"""
    db_query("INSERT OR REPLACE INTO users (user_id, balance) VALUES (?, ?)", (member.id, amount))
    await ctx.send(f"✅ ปรับยอดเงินของ {member.mention} เป็น {amount} บาท")

# ดึง Token จาก Railway Environment Variable
token = os.getenv("TOKEN")
bot.run(token)
