import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# --- ตั้งค่า Firebase ---
database_url = "https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/"
firebase_config_raw = os.getenv("FIREBASE_CONFIG")

if firebase_config_raw:
    cred = credentials.Certificate(json.loads(firebase_config_raw))
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {'databaseURL': database_url})
else:
    cred = credentials.Certificate("serviceAccountKey.json")

ref = db.reference('/')

def get_user_balance(user_id):
    data = ref.child('users').child(str(user_id)).get()
    return data.get('balance', 0) if data else 0

# --- ระบบ UI ร้านค้า ---
class ShopView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="[ เลือกหมวดหมู่สินค้า ]",
        custom_id="secxion_v1:select_cat",
        options=[
            disnake.SelectOption(label="Netflix Premium", value="netflix", emoji="🎬"),
            disnake.SelectOption(label="YouTube Premium", value="youtube", emoji="📺")
        ]
    )
    async def select_callback(self, select: disnake.ui.Select, inter: disnake.MessageInteraction):
        item_type = select.values[0]
        stock_data = ref.child('stocks').child(item_type).get()
        count = len(stock_data) if stock_data else 0
        await inter.response.send_message(f"📦 สินค้า {item_type.upper()} คงเหลือ {count} ชิ้น", ephemeral=True)

    @disnake.ui.button(label="เติมเงิน", style=disnake.ButtonStyle.primary, custom_id="secxion_v1:topup")
    async def topup_callback(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        await inter.response.send_message("💰 กรุณาส่งสลิปโอนเงินเพื่อให้แอดมินตรวจสอบครับ", ephemeral=True)

    @disnake.ui.button(label="เช็คยอดเงิน", style=disnake.ButtonStyle.secondary, custom_id="secxion_v1:bal")
    async def check_bal_callback(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        # แก้ไขตรงนี้: ใช้ inter.author.id ให้ถูกตำแหน่ง
        balance = get_user_balance(inter.author.id)
        await inter.response.send_message(f"💎 ยอดเงินของคุณ: **{balance}** บาท", ephemeral=True)

class SECXION_BOT(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=disnake.Intents.all())

    async def on_ready(self):
        self.add_view(ShopView())
        print(f"✅ บอท {self.user} พร้อมทำงานแล้ว!")

bot = SECXION_BOT()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("🏪 **SECXION STORE**", view=ShopView())

bot.run(os.getenv("TOKEN"))
