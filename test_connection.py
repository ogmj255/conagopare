#!/usr/bin/env python3
"""
Script para probar la conexión a MongoDB
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def test_mongodb_connection():
    print("=== PRUEBA DE CONEXIÓN A MONGODB ===\n")
    
    # URI de MongoDB Atlas
    atlas_uri = os.getenv('MONGODB_URI', 'mongodb+srv://ogmoscosoj:KcB4gSO579gBCSzY@conagoparedb.vwmlbqg.mongodb.net/?retryWrites=true&w=majority&appName=conagoparedb')
    local_uri = os.getenv('MONGODB_LOCAL_URI', 'mongodb://localhost:27017/')
    
    print("1. Probando conexión a MongoDB Atlas...")
    try:
        client = MongoClient(
            atlas_uri,
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=15000,
            socketTimeoutMS=15000
        )
        client.admin.command('ping')
        print("✅ Conexión a MongoDB Atlas exitosa")
        
        # Probar acceso a la base de datos
        db = client['conagoparedb']
        collections = db.list_collection_names()
        print(f"✅ Colecciones encontradas: {collections}")
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error conectando a MongoDB Atlas: {e}")
        print(f"   Tipo de error: {type(e).__name__}")
    
    print("\n2. Probando conexión a MongoDB local...")
    try:
        client = MongoClient(local_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("✅ Conexión a MongoDB local exitosa")
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error conectando a MongoDB local: {e}")
        print(f"   Tipo de error: {type(e).__name__}")
    
    print("\n=== DIAGNÓSTICO ===")
    print("Posibles soluciones:")
    print("1. Verificar conexión a internet")
    print("2. Verificar que no haya firewall bloqueando la conexión")
    print("3. Instalar MongoDB localmente")
    print("4. Verificar las credenciales de MongoDB Atlas")
    print("5. Verificar que la IP esté en la whitelist de MongoDB Atlas")
    
    return False

if __name__ == "__main__":
    test_mongodb_connection()