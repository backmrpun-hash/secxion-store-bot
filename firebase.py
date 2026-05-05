import firebase_admin
from firebase_admin import credentials, db
import json
from config import FB_CONF, DB_URL

cred = credentials.Certificate(json.loads(FB_CONF))
firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})

ref = db.reference("/")
