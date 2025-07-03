import base64
import os
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


# 从文件加载AI的私钥
def load_ai_private_key():
    # 假设私钥文件在项目根目录的data文件夹下
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'ai_private_key.pem')
    with open(key_path, 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    return private_key


def decrypt_with_ai_private_key(encrypted_data_b64):
    private_key = load_ai_private_key()
    encrypted_data = base64.b64decode(encrypted_data_b64)
    decrypted_data = private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted_data


def encrypt_with_aes(key, plaintext_bytes):
    iv = os.urandom(12)  # GCM推荐的IV大小为12字节
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
    return base64.b64encode(iv + encryptor.tag + ciphertext).decode('utf-8')


def decrypt_with_aes(key, encrypted_data_b64):
    try:
        encrypted_data = base64.b64decode(encrypted_data_b64)
        iv = encrypted_data[:12]
        tag = encrypted_data[12:28]  # GCM认证标签为16字节
        ciphertext = encrypted_data[28:]

        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()

        decrypted_bytes = decryptor.update(ciphertext) + decryptor.finalize()
        return decrypted_bytes
    except Exception as e:
        print(f"AES解密失败: {e}")
        return None