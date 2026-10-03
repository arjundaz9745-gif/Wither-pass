from selenium.webdriver.common.by import By
from PIL import Image
import requests
from io import BytesIO

def download_captcha(driver) -> BytesIO:
    try:

        captcha_img = driver.find_element(By.XPATH, '//img[contains(@src, "GetHIPData")]')
        src = captcha_img.get_attribute("src")


        response = requests.get(src)
        img = Image.open(BytesIO(response.content))


        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        print("🧩 CAPTCHA downloaded successfully.")
        return buf

    except Exception as e:
        print(f"❌ Failed to download CAPTCHA:  ")
        return None
