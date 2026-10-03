from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import pycountry
from automation.driver import create_driver

all_countries = {country.name for country in pycountry.countries}

def clean_text(text):
    """Remove non-BMP characters that ChromeDriver doesn't support."""
    if not text:
        return ""
    return ''.join(c for c in str(text) if ord(c) <= 0xFFFF)

def scrape_account_info(email: str, password: str) -> dict:
    driver = create_driver()
    wait = WebDriverWait(driver, 20)

    try:

        driver.get("https://login.live.com")
        email_input = wait.until(EC.presence_of_element_located((By.ID, "usernameEntry")))
        email_input.send_keys(clean_text(email))
        email_input.send_keys(Keys.RETURN)
        time.sleep(2)

        password_input = None

        try:

            password_input = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.NAME, "passwd"))
            )
            print("✅ Password input appeared directly.")

        except TimeoutException:
            print("Password input not visible, checking for alternate buttons...")


            try:
                use_password_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Use your password')]"))
                )
                use_password_btn.click()
                print("➡️ Clicked 'Use your password'")
                password_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.NAME, "passwd"))
                )

            except TimeoutException:

                try:
                    other_ways_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Other ways to sign in')]"))
                    )
                    other_ways_btn.click()
                    print("➡️ Clicked 'Other ways to sign in'")
                    time.sleep(1)


                    use_password_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Use your password')]"))
                    )
                    use_password_btn.click()
                    print("➡️ Clicked 'Use your password' after 'Other ways'")
                    password_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.NAME, "passwd"))
                    )

                except TimeoutException:

                    try:
                        switch_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.ID, "idA_PWD_SwitchToCredPicker"))
                        )
                        switch_link.click()
                        print("➡️ Clicked 'Sign in another way'")
                        time.sleep(1)

                        use_password_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Use your password')]"))
                        )
                        use_password_btn.click()
                        print("➡️ Clicked 'Use your password' after legacy switch")
                        password_input = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.NAME, "passwd"))
                        )

                    except TimeoutException:
                        print("❌ Failed to reach password input.")
                        return {"email": email, "error": "Could not reach password input"}


        password_input.send_keys(clean_text(password))
        password_input.send_keys(Keys.RETURN)
        time.sleep(2)


        try:
            password_input = driver.find_element(By.ID, "passwordEntry")

            if password_input.is_displayed():
                print("❌ Password input still present — likely incorrect password.")
                return {"email": email, "error": "Incorrect password"}

        except:
            print("✅ Login successful. No password error detected.")


        try:
            if "Too Many Requests" in driver.page_source:
                print("⚠️ 'Too Many Requests' detected — retrying shortly...")
                retries = 0
                max_retries = 20
                while "Too Many Requests" in driver.page_source and retries < max_retries:
                    time.sleep(1)
                    driver.refresh()
                    retries += 1
                if "Too Many Requests" in driver.page_source:
                    print("🚫 Still blocked after multiple retries. Skipping account.")
                    return {"email": email, "error": "Too Many Requests even after retry"}
        except:
            print("✅ No rate limit detected. Proceeding normally.")


        try:
            security_next_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "iLandingViewAction"))
            )
            print("🔒 Security info change screen found. Clicking 'Next'...")
            security_next_btn.click()
            time.sleep(2)
        except:
            print("✅ No security prompt detected. Continuing...")


        try:
            stay_signed_in_yes = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
            )
            print("🔄 'Stay signed in?' prompt detected. Confirming...")
            stay_signed_in_yes.click()
            time.sleep(2)
        except:
            print("❌ Password input still present — likely incorrect password.")
            return {"email": email, "error": "Incorrect password"}


        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Close"]'))
            )
            print("🛡️ Security modal detected. Closing it...")
            close_button.click()
            time.sleep(1)
        except:
            print("✅ No security modal found. Navigating to profile...")


        print("🌐 Opening Microsoft profile page...")
        driver.get("https://account.microsoft.com/profile")
        time.sleep(2)
        driver.get("https://account.microsoft.com/profile")
        try:
            wait.until(EC.presence_of_element_located((By.ID, "profile.profile-page.personal-section.full-name")))
            time.sleep(0.5)
            name = driver.find_element(By.ID, "profile.profile-page.personal-section.full-name").text.strip()
            print(f"🔹 Captured name: {name}")
            spans = driver.find_elements(By.CSS_SELECTOR, 'span.fui-Text')
            dob = "DOB not found"
            region = "Region not found"

            for span in spans:
                text = span.text.strip()
                if "/" in text and len(text.split("/")) == 3:
                    parts = text.split(";")
                    for part in parts:
                        part = part.strip()
                        if "/" in part and len(part.split("/")) == 3:
                            dob = part
                            print(f"🔹 Cleaned DOB: {dob}")
                            break

                elif text in all_countries:
                    region = text
                    print(f"🔹 Captured region: {region}")
        except:
            print("❌ Could not get account info")
            return {"email": email, "error": "Couldn't get account info, Make sure account is not blocked"}


        driver.get("https://secure.skype.com/portal/profile")
        print("✅ Loaded Skype profile")
        time.sleep(3)

        try:
            skype_id = driver.find_element(By.CLASS_NAME, "username").text.strip()
            print(f"🔹Skype ID: {skype_id}")
        except:
            skype_id = "live:"

        try:
            skype_email = driver.find_element(By.ID, "email1").get_attribute("value").strip()
            print(f"🔹Skype email: {skype_email}")
        except:
            skype_email = email  # fallback

        driver.get("https://www.xbox.com/en-IN/play/user")
        time.sleep(5)

        gamertag = "Not found"

        try:
            try:
                sign_in_btn = driver.find_element(By.XPATH, '//a[contains(text(), "Sign in")]')
                sign_in_btn.click()
                print(f"🔹Clicked sign_in_btn")
                time.sleep(7)
            except:
                pass

            try:
                account_btn = WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH, '//span[@role="button"]'))
                )
                account_btn.click()
                print(f"🔹Clicked account_btn")
                WebDriverWait(driver, 15).until(EC.url_contains("/play/user/"))

            except:
                pass

            url = driver.current_url
            if "/play/user/" in url:
                gamertag = url.split("/play/user/")[-1]
                gamertag = gamertag.replace("%20", " ").replace("%25", "%")
                print(f"🔹gamertag: {gamertag}")
        except:
            gamertag = "Error"

        return {
            "email": email,
            "password": password,
            "name": name,
            "dob": dob,
            "region": region,
            "skype_id": skype_id,
            "skype_email": skype_email,
            "gamertag": gamertag
        }

    except:
        return {"error": "Could Not Login!"}
    finally:
        driver.quit()
