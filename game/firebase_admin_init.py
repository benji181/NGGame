import firebase_admin
from firebase_admin import credentials, firestore
from django.conf import settings

def initialize_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_ADMIN_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    return firestore.client()
