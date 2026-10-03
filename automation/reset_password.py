from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from automation.driver import create_driver
from automation.core import scrape_account_info
import time

def clean_text(text):
    """Remove non-BMP characters that ChromeDriver doesn't support."""
    if not text:
        return ""
    return ''.join(c for c in str(text) if ord(c) <= 0xFFFF)

def perform_password_reset(resetlink, email, new_password):
    print("🔁 Starting password reset flow...")

    driver = create_driver()
    wait = WebDriverWait(driver, 25)
    try:
        driver.get(resetlink)
        print("🔗 Opened reset link.")


        email_input = wait.until(EC.presence_of_element_located((By.ID, "AccountNameInput")))
        email_input.clear()
        email_input.send_keys(clean_text(email))
        email_input.send_keys(Keys.RETURN)
        print("📨 Email entered.")


        new_pass = wait.until(EC.presence_of_element_located((By.ID, "iPassword")))
        new_pass.clear()
        new_pass.send_keys(clean_text(new_password))

        new_pass_re = wait.until(EC.presence_of_element_located((By.ID, "iRetypePassword")))
        new_pass_re.clear()
        new_pass_re.send_keys(clean_text(new_password))
        print("🔑 New password filled.")
        time.sleep(1)
        new_pass_re.send_keys(Keys.RETURN)


        print("⏳ Waiting for confirmation...")

        time.sleep(5)

        try:
            driver.find_element(By.CSS_SELECTOR, 'input[data-nuid="PreviousPasswordInput"]')
            fallback_pass = "ShulkerCorePass!12"
            print(f"⚠️ Password was rejected — retrying with fallback password. : {fallback_pass}")


            pass_input = driver.find_element(By.ID, "iPassword")
            pass_input.clear()
            pass_input.send_keys(fallback_pass)

            retype_input = driver.find_element(By.ID, "iRetypePassword")
            retype_input.clear()
            retype_input.send_keys(fallback_pass)
            retype_input.send_keys(Keys.RETURN)


            return fallback_pass

        except:
            print("✅ Password accepted. No retry required.")
            return new_password


    except Exception as e:
        print("❌ Password reset may have failed.")
    finally:
        driver.quit()
