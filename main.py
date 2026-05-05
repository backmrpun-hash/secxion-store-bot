import disnake
from disnake.ext import commands, tasks

from config import TOKEN, SETUP_CHANNEL_ID
from firebase import ref
from store import build_embed, StoreView
from topup import create_topup

bot = commands.Bot(command_prefix="!", intents=disnake.Intents.all())

store_message_id = None


# ================= TOPUP =================
@bot.command()
async def topup(ctx, amount: int):
    emb, _ = create_topup(amount, str(ctx.author.id))
    await ctx.send(embed=emb)


# ================= CONFIRM =================
@bot.command()
async def confirm(ctx, ref_code: str):
    data = ref.child(f"pending/{ref_code}").get()

    if not data:
        return await ctx.send("❌ ไม่พบรหัสอ้างอิง")

    if data["status"] != "pending":
        return await ctx.send("❌ ถูกใช้ไปแล้ว")

    user_id = data["user"]
    amount = data["amount"]

    bal = ref.child(f"users/{user_id}/balance").get() or 0

    ref.child(f"users/{user_id}").update({
        "balance": bal + amount
    })

    ref.child(f"pending/{ref_code}").update({
        "status": "paid"
    })

    await ctx.send(f"✅ เติมเงินสำเร็จ +{amount}")


# ================= STORE =================
@bot.event
async def on_ready():
    global store_message_id

    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)
    msg = await channel.send(embed=build_embed(), view=StoreView())

    store_message_id = msg.id
    auto_update.start()


@tasks.loop(seconds=10)
async def auto_update():
    channel = await bot.fetch_channel(SETUP_CHANNEL_ID)
    msg = await channel.fetch_message(store_message_id)

    await msg.edit(embed=build_embed(), view=StoreView())


# ================= RUN =================
bot.run(TOKEN)
