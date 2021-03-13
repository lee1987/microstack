import string
import secrets

DEFAULT_PASSWORD_LENGTH = 32


def generate_password(length=DEFAULT_PASSWORD_LENGTH):
    return ''.join(secrets.choice(
        string.ascii_letters + string.digits) for i in range(length))
