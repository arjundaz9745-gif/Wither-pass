"""
API Client
Communicates with Flask server for authentication
"""

import requests
import json
from typing import Tuple

class APIClient:
    def __init__(self, base_url: str = "http://212.132.120.102:14307"):
        self.base_url = base_url

    def check_authorization(self, user_id: str) -> Tuple[bool, str]:
        """
        Check if user is authorized

        Returns:
            (authorized: bool, message: str)
        """
        try:
            response = requests.post(
                f"{self.base_url}/check_auth",
                json={"user_id": user_id},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("authorized"):
                    return True, "User is authorized"
                else:
                    return False, "User is not authorized"
            else:
                return False, f"Server error: {response.status_code}"

        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to authentication server. Make sure the Discord bot is running."
        except requests.exceptions.Timeout:
            return False, "Connection timeout. Server is not responding."
        except Exception as e:
            return False, f"Error: {str(e)}"

    def request_otp(self, user_id: str) -> Tuple[bool, str]:
        """
        Request OTP to be sent via Discord DM

        Returns:
            (success: bool, message: str)
        """
        try:
            response = requests.post(
                f"{self.base_url}/request_otp",
                json={"user_id": user_id},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                return True, data.get("message", "OTP sent to your Discord DM")
            elif response.status_code == 403:
                return False, "User is not authorized"
            else:
                data = response.json()
                return False, data.get("error", "Failed to request OTP")

        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to authentication server"
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def verify_otp(self, user_id: str, otp: str) -> Tuple[bool, str]:
        """
        Verify OTP

        Returns:
            (success: bool, message: str)
        """
        try:
            response = requests.post(
                f"{self.base_url}/verify_otp",
                json={"user_id": user_id, "otp": otp},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("success", False), data.get("message", "")
            else:
                data = response.json()
                return False, data.get("error", "Failed to verify OTP")

        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to authentication server"
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def health_check(self) -> bool:
        """Check if server is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False

if __name__ == "__main__":
    # Test the API client
    client = APIClient()

    print("Testing API Client...")
    print(f"Server health: {client.health_check()}")
