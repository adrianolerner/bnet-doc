from slowapi import Limiter
from slowapi.util import get_remote_address

# Define the central limiter instance, keyed by the user's remote IP address
limiter = Limiter(key_func=get_remote_address)
