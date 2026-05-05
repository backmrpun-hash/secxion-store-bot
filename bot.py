import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
import os
import json

# 1. SETUP
token = os.getenv("TOKEN")
db_url = "[https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/](https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/)"
conf = os.getenv("FIREBASE_CONFIG")

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(conf))
        firebase_admin.initialize_app(cred, {'databaseURL': db_url})
    ref = db.reference('/')
except:
    pass

# 2. SHOP
class Shop(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.select(
        placeholder="เลือกสินค้า",
        custom_id="s1",
        options=[
            disnake.SelectOption(label="Netflix", value="netflix"),
            disnake.SelectOption(label="YouTube", value="youtube")
        ]
    )
    async def s(self, sel, inter):
        itype = sel.values[0]
        uid = str(inter.author.id)
        
        # ดึงเงินและของ
        p = {"netflix": 50, "youtube": 30}.get(itype, 999)
        u_data = ref.child('users').child(uid).get()
        bal = u_data.get('balance', 0) if u_data else 0
        stock = ref.child('stocks').child(itype).get()

        if not stock or bal < p:
            return await inter.response.send_message("เงินไม่พอหรือของหมด", ephemeral=True)

        # จ่ายและส่งของ (ส่งเป็นข้อความธรรมดา ไม่ใช้ Code Block ป้องกัน Error)
        iid = list(stock.keys())[0]
        detail = str(stock[iid])
        
        ref.child('users').child(uid).update({'balance': bal - p})
        ref.child('stocks').child(itype).child(iid).delete()

        await inter.response.send_message(f"ซื้อสำเร็จ! ของของคุณคือ: {detail}", ephemeral=True)

# 3. MAIN
bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    bot.add_view(Shop())
    print("Online")

@bot.command()
async def setup(ctx):
    await ctx.send("🏪 STORE", view=Shop())

bot.run(token)
