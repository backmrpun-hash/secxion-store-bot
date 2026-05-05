import disnake
from firebase import ref


def build_embed():
    stocks = ref.child("stocks").get() or {}

    text = ""
    for cat, data in stocks.items():
        price = data.get("price", 0)
        items = data.get("items", {})
        text += f"{cat} | {price} บาท | {len(items)} ชิ้น\n"

    if not text:
        text = "ไม่มีสินค้า"

    emb = disnake.Embed(
        title="🛒 STORE AUTO",
        description="ใช้ !topup <จำนวน>",
        color=0x2b2d31
    )
    emb.add_field(name="📦 สินค้า", value=f"```{text}```", inline=False)
    return emb


class StoreView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.reload()

    def reload(self):
        stocks = ref.child("stocks").get() or {}
        options = []

        for cat, data in stocks.items():
            if data.get("items"):
                options.append(disnake.SelectOption(label=cat, value=cat))

        if not options:
            options = [disnake.SelectOption(label="ไม่มีสินค้า", value="none")]

        select = disnake.ui.Select(options=options)
        select.callback = self.buy

        self.clear_items()
        self.add_item(select)

    async def buy(self, inter):
        cat = inter.values[0]
        user_id = str(inter.author.id)

        user = ref.child(f"users/{user_id}").get() or {}
        bal = user.get("balance", 0)

        price = ref.child(f"stocks/{cat}/price").get() or 0

        if bal < price:
            return await inter.response.send_message("เงินไม่พอ", ephemeral=True)

        items = ref.child(f"stocks/{cat}/items").get() or {}
        if not items:
            return await inter.response.send_message("ของหมด", ephemeral=True)

        key = list(items.keys())[0]
        data = items[key]

        ref.child(f"users/{user_id}").update({"balance": bal - price})
        ref.child(f"stocks/{cat}/items/{key}").delete()

        await inter.author.send(f"สินค้า:\n{data}")
        await inter.response.send_message("ซื้อสำเร็จ", ephemeral=True)
