import discord
from discord.ext import commands
import requests
import os

# --- CONFIGURATION ---
TOKEN = 'MTUwMTkxNDk4NzkwNjcyODAyNw.G9rzIs.occokpqZsqShLWiF2X7b2VuGJmYnLCl-JBfrmI'
FIREBASE_URL = "https://keyyss-6ec39-default-rtdb.asia-southeast1.firebasedatabase.app/keys"
CHANNEL_ID = 1501870139602108536
ID_FILE = "message_id.txt" # ไฟล์สำหรับจำว่าส่งข้อความไปที่ ID ไหนแล้ว

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- UI ส่วนการกรอกคีย์ (Modal) ---
class ResetKeyModal(discord.ui.Modal, title='Reset License HWID'):
    license_key = discord.ui.TextInput(
        label='License Key',
        placeholder='BFS-XXXX-XXXX-XXXX',
        required=True,
        min_length=15
    )

    async def on_submit(self, interaction: discord.Interaction):
        key = self.license_key.value.strip()
        target_url = f"{FIREBASE_URL}/{key}.json"

        try:
            response = requests.get(target_url)
            data = response.json()

            if data is None:
                return await interaction.response.send_message(f"❌ ไม่พบคีย์ `{key}` ในระบบ", ephemeral=True)

            if data.get('status') == "unused":
                return await interaction.response.send_message(f"ℹ️ คีย์ `{key}` ยังไม่ได้ถูกใช้งาน", ephemeral=True)

            # รีเซ็ตค่าใน Firebase
            update_data = {"status": "unused", "hwid": ""}
            requests.patch(target_url, json=update_data)

            embed = discord.Embed(title="✅ Reset Successful", color=discord.Color.green())
            embed.description = f"คีย์ `{key}` ถูกล้าง HWID เรียบร้อยแล้ว\nคุณสามารถนำไปรันในเครื่องใหม่ได้ทันที"
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"🆘 Error: {str(e)}", ephemeral=True)

# --- UI ส่วนของปุ่ม (View) ---
class ResetKeyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Reset HWID (กดเพื่อรีเซ็ตคีย์)', style=discord.ButtonStyle.primary, custom_id='reset_btn_persistent')
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ResetKeyModal())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ ไม่พบ Channel ID ที่กำหนด!")
        return

    # สร้าง Embed
    embed = discord.Embed(
        title="🔑 ระบบจัดการ License Key",
        description="หากคุณต้องการเปลี่ยนเครื่อง หรือ HWID ไม่ตรง\nท่านสามารถรีเซ็ตได้ด้วยตนเองที่นี่",
        color=discord.Color.blue()
    )
    embed.add_field(name="สถานะเซิร์ฟเวอร์", value="🟢 Online", inline=True)
    embed.add_field(name="วิธีใช้งาน", value="กดปุ่มด้านล่างแล้วกรอก Key ของคุณ", inline=False)
    embed.set_footer(text="ระบบจะทำการล้างข้อมูล HWID ทันทีหลังกดยืนยัน")

    view = ResetKeyView()

    # ตรวจสอบว่าเคยส่งข้อความไปหรือยัง
    msg_id = None
    if os.path.exists(ID_FILE):
        with open(ID_FILE, "r") as f:
            msg_id = f.read().strip()

    if msg_id:
        try:
            # พยายามแก้ไขข้อความเดิม
            old_msg = await channel.fetch_message(int(msg_id))
            await old_msg.edit(embed=embed, view=view)
            print("✅ อัปเดต Embed เดิมเรียบร้อยแล้ว")
        except:
            # ถ้าข้อความเดิมถูกลบไปแล้ว ให้ส่งใหม่
            new_msg = await channel.send(embed=embed, view=view)
            with open(ID_FILE, "w") as f:
                f.write(str(new_msg.id))
            print("⚠️ ไม่พบข้อความเดิม จึงส่งอันใหม่แทน")
    else:
        # ส่งครั้งแรก
        new_msg = await channel.send(embed=embed, view=view)
        with open(ID_FILE, "w") as f:
            f.write(str(new_msg.id))
        print("🆕 ส่ง Embed ครั้งแรกเรียบร้อยแล้ว")

    # ลงทะเบียนปุ่มให้ทำงานได้ตลอดเวลาแม้รันใหม่
    bot.add_view(ResetKeyView())

bot.run(TOKEN)
