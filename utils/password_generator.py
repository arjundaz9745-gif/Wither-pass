"""
Password Generator
Generates NVCore###### format passwords
"""

import random

def generate_shulker_password() -> str:
    """
    Generate a password in format: NVCore######
    Where ###### is 4 random digits

    Returns:
        str: Generated password (e.g., "NVCore1234")
    """
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"WardenGen{random_numbers}"


def generate_custom_password(prefix: str = "WardenGen",
                             length: int = 6) -> str:
    """
    Generate a custom password with specified prefix and number length

    Args:
        prefix: Password prefix (default: "NVCore")
        length: Number of random digits (default: 4)

    Returns:
        str: Generated password
    """
    random_numbers = ''.join(
        [str(random.randint(0, 9)) for _ in range(length)])
    return f"{prefix}{random_numbers}"


if __name__ == "__main__":
    # Test password generation
    for i in range(5):
        print(f"Password {i+1}: {generate_shulker_password()}")
