import os
import json
import firebase_admin
from firebase_admin import credentials

firebase_json = os.getenv("FIREBASE_CREDENTIALS")

if firebase_json:
    cred = credentials.Certificate(json.loads(firebase_json))
    firebase_admin.initialize_app(cred)
else:
    print("⚠️ Firebase credentials not found. Please check environment variable setup.")
