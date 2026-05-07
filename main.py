import discord
from discord.ext import commands
import requests
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
# ดึง Token จาก Environment (Railway Settings)
TOKEN = os.getenv('DISCORD_TOKEN')
# ลิงก์ Firebase ของคุณ
FIREBASE_URL = "https://keyyss-6ec39-default-rtdb.asia-southeast1.firebasedatabase.app"
CHANNEL_ID = 1501870139602108536

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
        target_url = f"{FIREBASE_URL}/keys/{key}.json"

        try:
            response = requests.get(target_url)
            data = response.json()

            if data is None:
                return await interaction.response.send_message(f"❌ ไม่พบคีย์ `{key}` ในระบบ", ephemeral=True)

            if data.get('status') == "unused":
                return await interaction.response.send_message(f"ℹ️ คีย์ `{key}` ยังไม่ถูกใช้งาน", ephemeral=True)

            # รีเซ็ตค่าใน Firebase
            update_data = {"status": "unused", "hwid": ""}
            requests.patch(target_url, json=update_data)

            embed = discord.Embed(title="✅ Reset Successful", color=discord.Color.green())
            embed.description = f"คีย์ `{key}` ถูกล้าง HWID เรียบร้อยแล้ว\nสามารถนำไปรันในเครื่องใหม่ได้ทันที"
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"🆘 Error: {str(e)}", ephemeral=True)

# --- UI ส่วนของปุ่ม (View) ---
class ResetKeyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Reset HWID (กดเพื่อรีเซ็ตคีย์)', style=discord.ButtonStyle.primary, custom_id='reset_btn_railway_final')
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ResetKeyModal())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ ไม่พบ Channel ID!")
        return

    embed = discord.Embed(
        title="🔑 ระบบจัดการ License Key",
        description="หากเปลี่ยนเครื่อง หรือ HWID ไม่ตรง\nท่านสามารถรีเซ็ตได้ด้วยตนเองที่นี่",
        color=discord.Color.blue()
    )
    embed.add_field(name="Server Status", value="🟢 Online (Railway)", inline=True)
    embed.add_field(name="วิธีใช้งาน", value="กดปุ่มด้านล่างแล้วกรอก Key ของคุณ", inline=False)
    embed.set_footer(text="ระบบจะล้างข้อมูล HWID ทันทีหลังกดยืนยัน")

    view = ResetKeyView()

    # ดึง Message ID จาก Firebase มาเช็คเพื่อ Update แทนการส่งซ้ำ
    config_url = f"{FIREBASE_URL}/bot_config.json"
    try:
        config_data = requests.get(config_url).json()
        msg_id = config_data.get('message_id') if config_data else None
        
        if msg_id:
            try:
                old_msg = await channel.fetch_message(int(msg_id))
                await old_msg.edit(embed=embed, view=view)
            except:
                new_msg = await channel.send(embed=embed, view=view)
                requests.patch(config_url, json={"message_id": str(new_msg.id)})
        else:
            new_msg = await channel.send(embed=embed, view=view)
            requests.patch(config_url, json={"message_id": str(new_msg.id)})
    except Exception as e:
        print(f"⚠️ Firebase Config Error: {e}")

    bot.add_view(ResetKeyView())

bot.run(TOKEN)
