#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import send_email_notification

# Test the email function directly
print("=== TESTING APP EMAIL FUNCTION ===")

test_email = "ogmoscosoj@gmail.com"
test_subject = "Test from App Function"
test_message = "This is a test email from the app function"
test_data = {
    'id_secuencial': '2025-0001',
    'numero_oficio': 'TEST-001',
    'gad_parroquial': 'Test Parroquia',
    'canton': 'Test Canton',
    'detalle': 'Test details'
}

print(f"Sending test email to: {test_email}")
send_email_notification(test_email, test_subject, test_message, test_data)
print("Email function called - check console output above")