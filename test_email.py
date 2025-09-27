#!/usr/bin/env python3
"""
Script de prueba para SendGrid Web API
"""
import os
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Cargar variables de entorno
load_dotenv()

def test_sendgrid():
    try:
        print("🧪 Probando SendGrid Web API...")
        
        # Verificar configuración
        api_key = os.getenv('SENDGRID_API_KEY')
        from_email = os.getenv('FROM_EMAIL')
        
        if not api_key:
            print("❌ ERROR: SENDGRID_API_KEY no encontrada en .env")
            return False
            
        if not from_email:
            print("❌ ERROR: FROM_EMAIL no encontrada en .env")
            return False
            
        print(f"✅ API Key: {api_key[:10]}...")
        print(f"✅ From Email: {from_email}")
        
        # Crear email de prueba
        to_email = input("📧 Ingresa tu email para la prueba: ").strip()
        
        if not to_email or '@' not in to_email:
            print("❌ Email inválido")
            return False
        
        html_content = """
        <html>
        <body>
            <h2>🧪 Prueba SendGrid - CONAGOPARE</h2>
            <p>Este es un email de prueba del sistema.</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <h4>✅ Sistema funcionando correctamente</h4>
                <p><strong>Fecha:</strong> {}</p>
                <p><strong>Estado:</strong> Prueba exitosa</p>
            </div>
            <hr>
            <p><small>Sistema automático CONAGOPARE - Prueba</small></p>
        </body>
        </html>
        """.format(os.popen('date /t').read().strip())
        
        # Crear mensaje
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject='🧪 Prueba SendGrid - CONAGOPARE',
            html_content=html_content
        )
        
        # Enviar
        print("📤 Enviando email...")
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        
        print(f"✅ Email enviado exitosamente!")
        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Headers: {response.headers}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_sendgrid()
    if success:
        print("\n🎉 ¡Prueba completada exitosamente!")
        print("📧 Revisa tu bandeja de entrada (y spam)")
    else:
        print("\n💥 Prueba falló. Revisa la configuración.")