import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from tempmail import get_otp_from_first_email, wait_for_emails, read_message, extract_specific_link, get_messages
from datetime import datetime
from automation.captcha import download_captcha
import time
import os
import json

def clean_text(text):
    """Remove non-BMP characters that ChromeDriver doesn't support."""
    if not text:
        return ""
    return ''.join(c for c in str(text) if ord(c) <= 0xFFFF)

def get_month_name(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        month_name = date_obj.strftime("%B")
        day = str(date_obj.day)
        year = str(date_obj.year)
        return month_name, day, year
    except ValueError:
        return "May", "5", "1989"

def should_save_emails():
    """Check if email saving is enabled in config.json"""
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.json"
        )
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get("save_emails_to_file", False)
    except:
        return False



def continue_acsr_flow(driver, account_info, token, captcha_text):
    wait = WebDriverWait(driver, 20)

    try:

        captcha_value = clean_text(captcha_text)

        try:

            captcha_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//input[contains(@id, "SolutionElement")]'))
            )
            captcha_input.clear()
            captcha_input.send_keys(captcha_value)
            captcha_input.send_keys(Keys.RETURN)
            print("📨 CAPTCHA submitted. Waiting for OTP input field...")


            code_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "iOttText"))
            )
            print("✅ CAPTCHA accepted.")

        except Exception:
            print("❌ CAPTCHA failed or OTP input not found.")
            print("🔁 Waiting for new CAPTCHA to regenerate...\n")

            try:
                captcha_image = download_captcha(driver)
                print("🧩 New CAPTCHA downloaded.")
                with open(f"captcha_retry.png", "wb") as f:
                    f.write(captcha_image.read())

                return "CAPTCHA_RETRY_NEEDED"
            except Exception as e:
                print(f"❌ Failed to detect new CAPTCHA image: {e}")
                return "CAPTCHA_DOWNLOAD_FAILED"


        print("⌛ Waiting for OTP via tempmail...")
        otp = get_otp_from_first_email(token)
        if not otp:
            print("❌ OTP not received.")
            return "❌ OTP not received."

        print(f"📥 OTP received: {otp}")


        code_input = wait.until(EC.presence_of_element_located((By.ID, "iOttText")))
        code_input.clear()
        code_input.send_keys(clean_text(otp))
        code_input.send_keys(Keys.RETURN)
        print("🔐 OTP submitted.")
        time.sleep(2)

        # Step 5: Fill name
        print("🧾 Filling name...")
        name_cleaned = clean_text(account_info.get('name', 'User'))
        first, last = name_cleaned.split(maxsplit=1) if ' ' in name_cleaned else (name_cleaned, "Last")
        wait.until(EC.presence_of_element_located((By.ID, "FirstNameInput"))).send_keys(first)
        wait.until(EC.presence_of_element_located((By.ID, "LastNameInput"))).send_keys(last)

        month, day, year = get_month_name(account_info['dob'])

        if not all([month, day, year]):
            raise ValueError("❌ Invalid or missing DOB, aborting ACSR form.")


        day_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "BirthDate_dayInput"))
        )
        Select(day_element).select_by_visible_text(day)


        month_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "BirthDate_monthInput"))
        )
        Select(month_element).select_by_visible_text(month)


        year_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "BirthDate_yearInput"))
        )
        Select(year_element).select_by_visible_text(year)
        print(f"Parsed DOB: {month=}, {day=}, {year=}")
        print("✅ Dropdown Options Loaded:", [o.text for o in Select(month_element).options])

        print("📆 DOB filled.")


        wait.until(EC.presence_of_element_located((By.ID, "CountryInput"))).send_keys(clean_text(account_info['region']))
        print("🌍 Region filled.")
        time.sleep(1)


        first_name_input = driver.find_element(By.ID, "FirstNameInput")
        first_name_input.send_keys(Keys.RETURN)
        time.sleep(1)

        print("🔐 Entering old password...")
        previous_pass_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[data-nuid="PreviousPasswordInput"]'))
        )
        previous_pass_input.clear()
        previous_pass_input.send_keys(clean_text(account_info["password"]))
        print("✅ Old password entered.")
        time.sleep(2)


        skype_checkbox = driver.find_element(By.ID, "ProductOptionSkype")
        if not skype_checkbox.is_selected():
            skype_checkbox.click()
            print("☑️ Skype option selected.")


        xbox_checkbox = driver.find_element(By.ID, "ProductOptionXbox")
        if not xbox_checkbox.is_selected():
            xbox_checkbox.click()
            print("🎮 Xbox option selected.")

        # Skype info
        previous_pass_input.send_keys(Keys.RETURN)
        skype_name_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "SkypeNameInput"))
        )
        skype_name_input.clear()
        skype_name_input.send_keys(clean_text(account_info["skype_id"]))

        skype_email_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "SkypeAccountCreateEmailInput"))
        )
        skype_email_input.clear()
        skype_email_input.send_keys(clean_text(account_info["skype_email"]))
        print("🔑 Skype info filled.")
        time.sleep(2)
        skype_email_input.send_keys(Keys.RETURN)

        # Xbox product
        print("🎮 Selecting Xbox One...")
        xbox_radio = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "XboxOneOption"))
        )
        if not xbox_radio.is_selected():
            xbox_radio.click()
        xbox_radio.send_keys(Keys.ENTER)
        print("✅ Xbox One selected.")
        time.sleep(2)

        # Gamertag
        print("🎮 Entering Xbox Gamertag...")
        xbox_name_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "XboxGamertagInput"))
        )
        xbox_name_input.clear()
        xbox_name_input.send_keys(clean_text(account_info["gamertag"]))
        xbox_name_input.send_keys(Keys.RETURN)
        print("✅ Gamertag submitted.")
        
        # Check for error message after form submission
        time.sleep(1)
        try:
            error_msg = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), \"You've reached the limit for account recovery requests\")]"))
            )
            if error_msg.is_displayed():
                print("❌ Failed (too many requests today)")
                try:
                    driver.quit()
                except Exception:
                    pass
                return "❌ Failed (too many requests today)"
        except Exception:
            pass  # Error element not found, continue normally

        try:
            print("📬 Fetching password reset link from temp mail...")
            
            emails = None
            for i in range(20):
                print(f"📧 Checking for emails (attempt {i+1}/20)...")
                emails = get_messages(token)
                if len(emails) >= 2:
                    print(f"✅ Found {len(emails)} emails!")
                    break
                print(f"⏳ Only {len(emails)} email(s) found. Waiting 10 seconds before next check...")
                time.sleep(10)
            
            if len(emails) >= 2:
                # Write all emails to a .txt file (if enabled in config)
                if should_save_emails():
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        email_file = f"emails_{timestamp}.txt"
                        
                        with open(email_file, 'w', encoding='utf-8') as f:
                            f.write("=" * 80 + "\n")
                            f.write(f"EMAIL ARCHIVE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"Total Emails: {len(emails)}\n")
                            f.write("=" * 80 + "\n\n")
                            
                            for idx, email in enumerate(emails, 1):
                                f.write(f"\n{'=' * 80}\n")
                                f.write(f"EMAIL #{idx}\n")
                                f.write(f"{'=' * 80}\n")
                                
                                # Write email metadata
                                f.write(f"ID: {email.get('id', 'N/A')}\n")
                                f.write(f"From: {email.get('from', {}).get('address', 'N/A')}\n")
                                f.write(f"Subject: {email.get('subject', 'N/A')}\n")
                                f.write(f"Date: {email.get('createdAt', 'N/A')}\n")
                                
                                # Read full email content
                                try:
                                    full_email = read_message(token, email['id'])
                                    f.write(f"\n--- EMAIL CONTENT ---\n")
                                    f.write(f"Text:\n{full_email.get('text', 'N/A')}\n")
                                    if 'html' in full_email:
                                        f.write(f"\nHTML:\n{full_email.get('html', 'N/A')}\n")
                                except Exception as e:
                                    f.write(f"\nError reading email content: {e}\n")
                                
                                f.write(f"\n{'=' * 80}\n\n")
                        
                        print(f"📝 All emails saved to: {email_file}")
                    except Exception as e:
                        print(f"⚠️ Failed to save emails to file: {e}")
                
                email2 = read_message(token, emails[0]['id'])
                resetlink = extract_specific_link(email2['text'])
                try:
                    driver.quit()
                except Exception:
                    pass
                if resetlink:
                    print(f"🔗 Target Link: {resetlink}")
                    return resetlink
                else:
                    print("❌ Target reset link not found.")
                    return None
            else:
                try:
                    driver.quit()
                except Exception:
                    pass
                print("❌ No new email received after 200 seconds.")
                return None
        except Exception as e:
            print(f"❌ Failed to fetch or extract reset link: {e}")
            return None

    except Exception as e:
        print(f"❌ Error while continuing ACSR flow: {e}")
        return None
