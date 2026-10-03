from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
import platform


def create_driver(headless=False):

    options = Options()

    if headless:
        options.add_argument("--headless=new")
    else:
        options.add_argument("--start-minimized")

    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--incognito")
    # Comprehensive WebAuthn/Security Key blocking to prevent Windows Security pop-ups
    options.add_argument("--disable-webauthn")

    # Combine all WebAuthn-related features to disable in a single flag
    webauthn_features = [
        "WebAuthentication", "WebAuthn", "WebAuthenticationAPI",
        "WebAuthenticationSecurityKey", "WebAuthenticationUI"
    ]

    # Additional Windows-specific features to prevent security key prompts
    if platform.system().lower() == 'windows':
        webauthn_features.extend([
            "WindowsHello", "WindowsHelloForSecurityKeys",
            "WebAuthenticationWindowsHello"
        ])
        options.add_argument("--disable-webauthn-uvpa")

    options.add_argument(f"--disable-features={','.join(webauthn_features)}")

    # Chrome preferences to disable WebAuthn at the preference level
    prefs = {
        "credentials_enable_autosignin": False,
        "credentials_enable_service": False,
        "webauthn.enable_win_native_api": False,
        "webauthn.enable_usb": False,
        "webauthn.enable_platform_authenticators": False,
        "webauthn.virtual_authenticators_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)

    system = platform.system().lower()
    if system == 'linux':
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    else:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"

    options.add_argument(f"user-agent={user_agent}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    chrome_paths = [
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser", "/usr/bin/chromium",
        "/opt/google/chrome/chrome", "/snap/bin/chromium"
    ]

    for chrome_path in chrome_paths:
        if os.path.exists(chrome_path):
            options.binary_location = chrome_path
            print(f"🔍 Found Chrome at: {chrome_path}")
            break

    try:

        driver = webdriver.Chrome(service=Service(
            ChromeDriverManager().install()),
                                  options=options)
        print("✅ ChromeDriver initialized successfully")
    except Exception as e:
        print(f"❌ ChromeDriver initialization failed: {e}")

        try:

            driver = webdriver.Chrome(options=options)
            print("✅ ChromeDriver initialized with system driver")
        except Exception as e2:
            print(f"❌ System ChromeDriver also failed: {e2}")
            raise e2

    try:
        driver.execute_cdp_cmd(
            'Page.addScriptToEvaluateOnNewDocument', {
                'source':
                '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.navigator.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Block WebAuthn/Security Key APIs to prevent Windows Security pop-ups
                    if (navigator.credentials) {
                        const originalCreate = navigator.credentials.create;
                        navigator.credentials.create = function(options) {
                            if (options && options.publicKey) {
                                console.warn('[Blocked] WebAuthn create() call prevented');
                                return Promise.reject(new DOMException('WebAuthn is disabled', 'NotAllowedError'));
                            }
                            return originalCreate.apply(this, arguments);
                        };
                        
                        const originalGet = navigator.credentials.get;
                        navigator.credentials.get = function(options) {
                            if (options && options.publicKey) {
                                console.warn('[Blocked] WebAuthn get() call prevented');
                                return Promise.reject(new DOMException('WebAuthn is disabled', 'NotAllowedError'));
                            }
                            return originalGet.apply(this, arguments);
                        };
                    }
                    
                    // Block PublicKeyCredential if it exists
                    if (window.PublicKeyCredential) {
                        window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable = function() {
                            return Promise.resolve(false);
                        };
                        window.PublicKeyCredential.isConditionalMediationAvailable = function() {
                            return Promise.resolve(false);
                        };
                    }
                '''
            })
    except Exception as e:
        print(f"⚠️  Could not set anti-detection measures: {e}")

    return driver
