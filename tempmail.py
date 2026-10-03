import requests
import random
import string
import time
import re

BASE_URL = "https://api.mail.tm"

def random_name(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def get_domains():
    r = requests.get(f"{BASE_URL}/domains")
    return r.json()['hydra:member'][0]['domain']

def register_account(email, password):
    payload = {"address": email, "password": password}
    r = requests.post(f"{BASE_URL}/accounts", json=payload)
    return r.status_code in [201, 422]

def get_token(email, password):
    payload = {"address": email, "password": password}
    r = requests.post(f"{BASE_URL}/token", json=payload)
    return r.json()['token']

def get_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/messages", headers=headers)
    return r.json().get('hydra:member', [])

def read_message(token, message_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/messages/{message_id}", headers=headers)
    return r.json()

def generate_temp_mail_account():
    username = random_name()
    password = random_name(12)
    domain = get_domains()
    email = f"{username}@{domain}"
    register_account(email, password)
    token = get_token(email, password)
    return email, password, token

def wait_for_emails(token, expected_count=2, timeout=60, interval=5):
    attempts = timeout // interval
    for _ in range(attempts):
        inbox = get_messages(token)
        if len(inbox) >= expected_count:
            return inbox[:expected_count]
        time.sleep(interval)
    return get_messages(token)

def extract_otp(text):
    match = re.search(r'\b\d{6}\b', text)
    return match.group(0) if match else None

def get_otp_from_first_email(token):
    emails = wait_for_emails(token, expected_count=1)

    if not emails:
        print("❌ No email received.")
        return None

    msg = read_message(token, emails[0]['id'])
    otp = extract_otp(msg['text'])

    if otp:
        print("🔐 Extracted OTP:", otp)
    else:
        print("❌ OTP not found in email.")

    return otp

def print_second_email(token, emails):
    if len(emails) < 2:
        print("❌ Less than 2 emails available.")
        return

    msg = read_message(token, emails[1]['id'])
    print("\n📧 Full Email Content (2nd Email):\n")
    print(msg['text'])

def extract_specific_link(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "Click this link to reset your password:" in line:
            # check the next non-empty line - this code may be outdated please change as per your requirements.
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line.startswith("http"):
                    return next_line
    return None
