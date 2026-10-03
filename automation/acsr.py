import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from automation.captcha import download_captcha
from tempmail import generate_temp_mail_account
import time
from automation.driver import create_driver


def submit_acsr_form(account_info: dict):
    email = account_info['email']
    name = account_info['name']
    dob = account_info['dob']
    region = account_info['region']
    skype_id = account_info['skype_id']
    skype_email = account_info['skype_email']
    gamertag = account_info['gamertag']

    tempmail, temp_pass, token = generate_temp_mail_account()
    print(f"📩 Generated Temp Mail: {tempmail}")

    driver = create_driver()
    wait = WebDriverWait(driver, 20)

    try:
        driver.get("https://account.live.com/acsr")
        time.sleep(2)

        email_input = wait.until(
            EC.presence_of_element_located((By.ID, "AccountNameInput")))
        email_input.clear()
        email_input.send_keys(email)
        print("✉️ Entered Microsoft email.")

        tempmail_input = wait.until(
            EC.presence_of_element_located((By.ID, "iCMailInput")))
        tempmail_input.clear()
        tempmail_input.send_keys(tempmail)
        print("📨 Entered tempmail.")

        captcha_image = download_captcha(driver)
        print("🧩 CAPTCHA ready.")

        return captcha_image, driver, token, tempmail

    except Exception as e:
        print(f"❌ ACSR automation error: {e}")
        driver.quit()
        return None, None, None, None
