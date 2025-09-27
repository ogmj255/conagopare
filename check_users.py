#!/usr/bin/env python3
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

# Connect to MongoDB
mongo_uri = os.getenv('MONGODB_URI', 'mongodb+srv://ogmoscosoj:KcB4gSO579gBCSzY@conagoparedb.vwmlbqg.mongodb.net/?retryWrites=true&w=majority&appName=conagoparedb')
client = MongoClient(mongo_uri)
db = client['conagoparedb']
users = db['users_db']

print("=== USUARIOS EN LA BASE DE DATOS ===")
for user in users.find():
    print(f"Username: {user['username']}")
    print(f"Role: {user['role']}")
    print(f"Email: {user.get('email', 'NO EMAIL CONFIGURADO')}")
    print(f"Nombre: {user.get('nombre', 'Sin nombre')} {user.get('apellido', 'Sin apellido')}")
    print("-" * 40)

print("\n=== USUARIOS SIN EMAIL ===")
users_without_email = list(users.find({'$or': [{'email': {'$exists': False}}, {'email': ''}]}))
print(f"Total usuarios sin email: {len(users_without_email)}")
for user in users_without_email:
    print(f"- {user['username']} ({user['role']})")