import disnake
from disnake.ext import commands
import firebase_admin
from firebase_admin import credentials, db
from threading import Thread
import os
import json

# --- 1. CONFIGURATION ---
TOKEN = os.getenv('TOKEN')
DB_URL = 'https://bott-54e3e-default-rtdb.asia-southeast1.firebasedatabase.app/'
FB_CONF = os.getenv('FIREBASE_CONFIG')
ADMIN_LOG_ID = 1496076202509598720 

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(FB_CONF))
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
    ref = db.reference('/')
except Exception as e:
    print('Firebase Error:', e)

# --- 2. SHOP UI GENERATOR ---

def create_shop_embed():
    """สร้าง Embed หน้าร้านโดยดึงข้อมูลจากสต็อกจริง"""
    stocks_data = ref.child('stocks').get() or {}
    total_cats = 0
    total_items = 0
    list_text = ""

    for cat, items in stocks_data.items():
        if not isinstance(items, dict): continue
        # กรองเอาเฉพาะ key ที่ไม่ใช่ตัวหลอก (_init)
        real_keys = [k for k in items.keys() if k != '_init']
        count = len(real_keys)
        if count > 0:
            total_cats += 1
            total_items += count
            list_text += f"📂 **{cat.upper()}** | คงเหลือ `{count}`\n"

    if not list_text:
        list_text = "ขณะนี้ยังไม่มีสินค้าในสต็อก"

    emb = disnake.Embed(title='🏪 ABYSS SHOP - ระบบซื้อขายอัตโนมัติ', color=0x2b2d31)
    # ใช้เครื่องหมายคำพูดแบบบรรทัดเดียวเพื่อความปลอดภัย 100%
    stat_bar = "หมวดหมู่: " + str(total_cats) + " | สินค้าทั้งหมด: " + str(total_items)
    emb.description = "```\n" + stat_bar + "\n
```\n" + list_text
    emb.set_footer(text="อัปเดตสต็อกแบบ Realtime")
    return emb

# --- 3. UI CLASSES ---

class MainStoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.update_components()

    def update_components(self):
        self.clear_items()
        # ปุ่มพื้นฐาน
        self.add_item(disnake.ui.Button(label='💎 เติมเงิน', style=disnake.ButtonStyle.green, custom_id='topup_btn'))
        
        # สร้าง Dropdown ตามหมวดหมู่ที่มีของ
        stocks_data = ref.child('stocks').get() or {}
        opts = []
        for cat, items in stocks_data.items():
            if not isinstance(items, dict): continue
            if len([k for k in items.keys() if k != '_init']) > 0:
                opts.append(disnake.SelectOption(label=cat.upper(), value=cat))
        
        if opts:
            sel = disnake.ui.Select(placeholder='🛒 เลือกซื้อสินค้าที่นี่...', options=opts, custom_id='shop_sel')
            sel.callback = self.buy_callback
            self.add_item(sel)

    async def buy_callback(self, inter: disnake.MessageInteraction):
        cat_name = inter.values[0]
        user_id = str(inter.author.id)
        
        # เช็กเงินและของ
        user_ref = ref.child('users/' + user_id)
        user_data = user_ref.get() or {}
        balance = user_data.get('balance', 0)
        
        # (สมมติราคาคงที่ 50 หรือจะดึงจาก DB ก็ได้)
        price = 50 
        
        if balance < price:
            return await inter.response.send_message('❌ เงินมึงไม่พอ!', ephemeral=True)
            
        items = ref.child('stocks/' + cat_name).get() or {}
        real_items = {k: v for k, v in items.items() if k != '_init'}
        
        if not real_items:
            return await inter.response.send_message('❌ ของหมดแล้วมึง!', ephemeral=True)
            
        # ดึงของชิ้นแรกมาขาย
        item_id = list(real_items.keys())[0]
        detail = str(real_items[item_id])
        
        # ตัดเงิน / ลบของ
        user_ref.update({'balance': balance - price})
        ref.child('stocks/' + cat_name + '/' + item_id).delete()
        
        # ส่งของเข้า DM (แก้ Syntax Error ตรงนี้ให้ขาด)
        try:
            bt = chr(96) * 3
            nl = chr(10)
            code_block = bt + nl + detail + nl + bt
            
            dm_emb = disnake.Embed(title='✅ ซื้อสินค้าสำเร็จ', color=0x00ff00)
            dm_emb.add_field(name='ข้อมูลสินค้า', value=code_block)
            await inter.author.send(embed=dm_emb)
            res = '✅ ส่งสินค้าเข้า DM เรียบร้อย!'
        except:
            res = '⚠️ ทัก DM มึงไม่ได้! สินค้าคือ: ' + detail
            
        await inter.response.send_message(res, ephemeral=True)

# --- 4. REALTIME ENGINE ---

bot = commands.Bot(command_prefix='!', intents=disnake.Intents.all())

async def sync_shop_message():
    """ตามไปอัปเดตข้อความที่เคย Setup ไว้ในห้องต่างๆ"""
    config = ref.child('settings/shop_ui').get()
    if config:
        chan_id = config.get('channel_id')
        msg_id = config.get('message_id')
        channel = bot.get_channel(int(chan_id))
        if channel:
            try:
                msg = await channel.fetch_message(int(msg_id))
                await msg.edit(embed=create_shop_embed(), view=MainStoreView())
                print("🔄 [System] Shop UI Synced!")
            except:
                pass

@bot.event
async def on_ready():
    bot.add_view(MainStoreView())
    print('🚀 บอทออนไลน์และพร้อมอัปเดต Realtime!')

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """ติดตั้งหน้าร้านและบันทึก ID ไว้ใน Database เพื่อ Realtime Update"""
    msg = await ctx.send(embed=create_shop_embed(), view=MainStoreView())
    ref.child('settings/shop_ui').set({
        'channel_id': str(ctx.channel.id),
        'message_id': str(msg.id)
    })
    await ctx.message.delete()

# --- 5. FIREBASE LISTENER ---
def start_firebase_listener():
    """ดักจับการเปลี่ยนแปลงใน Firebase แล้วสั่งให้บอท Edit ข้อความ"""
    def on_change(event):
        bot.loop.create_task(sync_shop_message())
    
    # ดักจับที่ path stocks
    ref.child('stocks').listen(on_change)

if __name__ == '__main__':
    from server import run_web
    # รันเว็บ Server
    t1 = Thread(target=run_web)
    t1.daemon = True
    t1.start()
    
    # รัน Listener
    t2 = Thread(target=start_firebase_listener)
    t2.daemon = True
    t2.start()

    bot.run(TOKEN)
