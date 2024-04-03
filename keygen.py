from cryptography.fernet import Fernet
import os

key_file="key.key"


if not os.path.exists(key_file):
    
    key = Fernet.generate_key()

    with open(key_file, "wb") as key_file:
         key_file.write(key)