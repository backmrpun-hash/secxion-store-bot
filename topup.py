import random
import string
import disnake
from firebase import ref
from config import PROMPTPAY_ID


def gen_ref():
    return "TPX" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def create_topup(amount: int, user_id: str):
    ref_code = gen_ref()

    ref.child(f"pending/{ref_code}").set({
        "user": user_id,
        "amount": amount,
        "status": "pending"
    })

    qr = f"https://promptpay.io/{PROMPTPAY_ID}/{amount}.png"

    emb = disnake.Embed(
        title="💳 เติมเงิน (Manual Confirm)",
        description=f"""
💰 จำนวน: {amount} บาท  
🔖 รหัสอ้างอิง: `{ref_code}`  

👉 หลังโอนให้พิมพ์:
`!confirm {ref_code}`
        """,
        color=0x00ff00
    )

    emb.set_image(url=qr)
    return emb, ref_code
