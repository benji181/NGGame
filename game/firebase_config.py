import os
import json
import firebase_admin
from firebase_admin import credentials, auth, firestore, db
from django.conf import settings


# Initialize Firebase Admin SDK
def initialize_firebase():
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # If FIREBASE_ADMIN_CREDENTIALS is a JSON string
        try:
            cred_dict = json.loads(settings.FIREBASE_ADMIN_CREDENTIALS)
            cred = credentials.Certificate(cred_dict)
        except json.JSONDecodeError:
            # If it's a path to a JSON file
            cred = credentials.Certificate(settings.FIREBASE_ADMIN_CREDENTIALS)

        firebase_admin.initialize_app(cred, {
            'databaseURL': settings.FIREBASE_CONFIG['databaseURL']
        })

    return {
        'db': firestore.client(),
        'rtdb': db,
        'auth': auth
    }


# Get Firebase services
def get_firebase_services():
    try:
        firebase_admin.get_app()
    except ValueError:
        return initialize_firebase()

    return {
        'db': firestore.client(),
        'rtdb': db,
        'auth': auth
    }


# Verify Firebase ID token
def verify_firebase_token(id_token):
    try:
        firebase_services = get_firebase_services()
        decoded_token = firebase_services['auth'].verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        print(f"Error verifying token: {e}")
        return None