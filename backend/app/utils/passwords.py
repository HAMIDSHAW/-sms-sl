"""Server side password rules, used everywhere a password is set by a person."""

MIN_LENGTH = 8
MAX_LENGTH = 128  # bcrypt only reads the first 72 bytes; this also stops huge inputs being hashed

_COMMON = {
    "password", "password1", "password12", "password123", "password123!", "passw0rd", "p@ssw0rd",
    "12345678", "123456789", "1234567890", "qwertyui", "qwerty123", "iloveyou", "admin123", "welcome1",
    "welcome123", "letmein1", "abc12345", "11111111", "00000000", "changeme", "changeme123",
}


def validate_password(password, email=None):
    """Return an error message, or None when the password is acceptable."""
    if not isinstance(password, str):
        return "Password is required"
    if len(password) < MIN_LENGTH:
        return f"Password must be at least {MIN_LENGTH} characters"
    if len(password) > MAX_LENGTH:
        return f"Password must be at most {MAX_LENGTH} characters"
    lowered = password.lower()
    if lowered in _COMMON:
        return "That password is too common. Choose something harder to guess"
    if email and lowered in (email.lower(), email.split("@")[0].lower()):
        return "Password must not be the same as your email"
    if len(set(password)) < 4:
        return "Password is too repetitive"
    return None
