#!/usr/bin/env python3
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def test_sync_email():
    """Test email synchronously"""
    try:
        print("=== TESTING SYNC EMAIL ===")
        
        to_email = "ogmoscosoj@gmail.com"
        subject = "Test Sync Email - CONAGOPARE"
        
        # Try SendGrid SMTP first
        smtp_configs = [
            {
                'name': 'SendGrid',
                'server': 'smtp.sendgrid.net',
                'port': 587,
                'username': 'apikey',
                'password': os.getenv('SMTP_PASSWORD', ''),
                'from_email': 'ticsconagopare@gmail.com'
            },
            {
                'name': 'Gmail',
                'server': 'smtp.gmail.com',
                'port': 587,
                'username': os.getenv('GMAIL_SMTP_USERNAME', ''),
                'password': os.getenv('GMAIL_SMTP_PASSWORD', ''),
                'from_email': os.getenv('GMAIL_SMTP_USERNAME', '')
            }
        ]
        
        html_body = """
        <html>
        <body>
            <h2>Test Email - Sistema CONAGOPARE</h2>
            <p>Este es un email de prueba síncrono.</p>
            <p>Si recibes este mensaje, el sistema funciona correctamente.</p>
        </body>
        </html>
        """
        
        for config in smtp_configs:
            if not config['username'] or not config['password']:
                print(f"[EMAIL] Skipping {config['name']} - no credentials")
                continue
                
            try:
                print(f"[EMAIL] Trying {config['name']}...")
                print(f"[EMAIL] Server: {config['server']}:{config['port']}")
                print(f"[EMAIL] Username: {config['username']}")
                print(f"[EMAIL] From: {config['from_email']}")
                
                msg = MIMEMultipart()
                msg['From'] = config['from_email']
                msg['To'] = to_email
                msg['Subject'] = subject
                msg.attach(MIMEText(html_body, 'html'))
                
                server = smtplib.SMTP(config['server'], config['port'])
                server.starttls()
                server.login(config['username'], config['password'])
                server.sendmail(config['from_email'], to_email, msg.as_string())
                server.quit()
                
                print(f"[EMAIL SUCCESS] Email sent via {config['name']}")
                return True
                
            except Exception as e:
                print(f"[EMAIL ERROR] {config['name']} failed: {e}")
                continue
        
        print("[EMAIL ERROR] All methods failed")
        return False
        
    except Exception as e:
        print(f"[EMAIL ERROR] General error: {e}")
        return False

if __name__ == "__main__":
    test_sync_email()