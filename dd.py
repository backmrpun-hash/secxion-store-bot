import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
from threading import Thread
import os
import json

# --- 1. SETTINGS ---
TOKEN = os.getenv('TOKEN')
DB_URL = 'https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/'
FB_CONF = os.getenv('FIREBASE_CONFIG')
ADMIN_LOG_ID = 1496076202509598720

# --- Firebase Init ---
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    ref = db.reference('/')
except Exception as e:
    print('Firebase Error:', e)

# --- 2. UI CLASSES ---

class TopupModal(disnake.ui.Modal):
    def __init__(self):
        components = [
            disnake.ui.TextInput(label='จำนวนเงิน', placeholder='เช่น 50', custom_id='amt'),
            disnake.ui.TextInput(label='เวลาที่โอน', placeholder='เช่น 11:21', custom_id='time')
        ]
        super().__init__(title='แจ้งเติมเงิน', custom_id='topup_modal_fixed', components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        amt = inter.text_values['amt']
        time = inter.text_values['time']
        channel = inter.bot.get_channel(ADMIN_LOG_ID)

        if not channel:
            return await inter.response.send_message('❌ ไม่พบห้องแอดมิน!', ephemeral=True)

        emb = disnake.Embed(title='💰 แจ้งโอนเงิน', color=0xffff00)
        emb.add_field(name='ผู้แจ้ง', value=inter.author.mention)
        emb.add_field(name='ยอดเงิน', value=amt)
        emb.add_field(name='เวลา', value=time)

        await channel.send(embed=emb, view=AdminApproveView(inter.author.id, amt))
        await inter.response.send_message('✅ ส่งข้อมูลสำเร็จ', ephemeral=True)


class AdminApproveView(disnake.ui.View):
    def __init__(self, user_id, amount):
        super().__init__(timeout=None)
        self.user_id = str(user_id)
        self.amount = float(amount)

    @disnake.ui.button(label='✅ อนุมัติ', style=disnake.ButtonStyle.green, custom_id='adm_app')
    async def approve(self, button, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.administrator:
            return await inter.response.send_message('Admin Only!', ephemeral=True)

        curr = ref.child('users/' + self.user_id + '/balance').get() or 0
        ref.child('users/' + self.user_id).update({'balance': curr + self.amount})

        await inter.response.send_message('✅ เติมเงินสำเร็จ')
        self.stop()


class MainStoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.create_menu()

    def create_menu(self):
        stocks_data = ref.child('stocks').get() or {}
        options = []

        for cat_name, items in stocks_data.items():
            if not isinstance(items, dict):
                continue
            real_items = [k for k in items.keys() if k != '_init']
            if real_items:
                options.append(disnake.SelectOption(label=cat_name.upper(), value=cat_name))

        if not options:
            options = [disnake.SelectOption(label='ไม่มีสินค้า', value='none')]

        select = disnake.ui.Select(
            placeholder='🛒 เลือกสินค้า',
            custom_id='shop_select',
            options=options
        )
        select.callback = self.shop_callback

        self.clear_items()
        self.add_item(disnake.ui.Button(label='💎 เติมเงิน', style=disnake.ButtonStyle.green, custom_id='btn_topup'))
        self.add_item(select)

    async def interaction_check(self, inter: disnake.MessageInteraction):
        # กดปุ่มเติมเงิน
        if inter.data.get("custom_id") == "btn_topup":
            await inter.response.send_modal(TopupModal())
            return False
        return True

    async def shop_callback(self, inter: disnake.MessageInteraction):
        itype = inter.values[0]

        if itype == 'none':
            return await inter.response.send_message('❌ ของหมด', ephemeral=True)

        price = 50
        user_path = 'users/' + str(inter.author.id)
        udata = ref.child(user_path).get() or {}
        bal = udata.get('balance', 0)

        stocks = ref.child('stocks/' + itype).get() or {}
        real_items = {k: v for k, v in stocks.items() if k != '_init'}

        if not real_items:
            return await inter.response.send_message('❌ ของหมด!', ephemeral=True)

        if bal < price:
            return await inter.response.send_message('❌ เงินไม่พอ!', ephemeral=True)

        iid = list(real_items.keys())[0]
        detail = str(real_items[iid])

        # หักเงิน + ลบสินค้า
        ref.child(user_path).update({'balance': bal - price})
        ref.child('stocks/' + itype + '/' + iid).delete()

        # ✅ FIX ตรงนี้ (ตัวปัญหาเดิม)
        try:
            code_block = f"```\n{detail}\n```"

            emb = disnake.Embed(title='📦 ซื้อสินค้าสำเร็จ', color=0x00ff00)
            emb.add_field(name='สินค้า', value=code_block, inline=False)

            await inter.author.send(embed=emb)
            msg = '✅ ส่งของเข้า DM เรียบร้อย'
        except:
            msg = '⚠️ ทัก DM ไม่ได้! ของคือ: ' + detail

        await inter.response.send_message(msg, ephemeral=True)

        self.create_menu()
        await inter.edit_original_message(view=self)


# --- 3. BOT CORE ---
bot = commands.Bot(command_prefix='!', intents=disnake.Intents.all())


@bot.event
async def on_ready():
    bot.add_view(MainStoreView())
    print('🚀 ONLINE')


@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send(
        embed=disnake.Embed(title='🏪 STORE', color=0x2b2d31),
        view=MainStoreView()
    )


# --- 4. RUN ---
if __name__ == '__main__':
    from server import run_web
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

    bot.run(TOKEN)
