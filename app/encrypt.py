from cryptography.fernet import Fernet

class Encryptor:
    
    def __init__(self, key_file="key.key"):
        self.key = self.load_key(key_file)

    def load_key(self, key_file):
        with open(key_file, "rb") as key_file:
            key = key_file.read()
        return key

    def en(self, message):
        f = Fernet(self.key)
        encrypted_message = f.encrypt(message.encode())
        return encrypted_message

    def de(self, encrypted_message):
        f = Fernet(self.key)
        decrypted_message = f.decrypt(encrypted_message).decode()
        return decrypted_message
