import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

KEY_DIR = os.path.join(os.path.expanduser("~"), ".secure_im")
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, "private_key.pem")

def generate_keys_if_not_exist():
    """
    如果私钥不存在，则生成并保存RSA密钥对。
    """
    if not os.path.exists(PRIVATE_KEY_PATH):
        print("未找到私钥。正在生成新密钥...")
        os.makedirs(KEY_DIR, exist_ok=True)
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # 保存私钥
        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        print(f"私钥已保存至 {PRIVATE_KEY_PATH}")

def load_private_key():
    """从文件加载私钥。"""
    if not os.path.exists(PRIVATE_KEY_PATH):
        raise FileNotFoundError("未找到私钥文件。请先注册。")
    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    return private_key

def get_public_key_pem():
    """加载私钥并返回PEM格式的公钥。"""
    private_key = load_private_key()
    public_key = private_key.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return public_key_pem.decode('utf-8')

def encrypt_with_public_key(public_key_pem, data):
    """使用PEM格式的公钥加密数据。"""
    public_key = serialization.load_pem_public_key(
        public_key_pem.encode('utf-8'),
        backend=default_backend()
    )
    encrypted_data = public_key.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(encrypted_data).decode('utf-8')

def decrypt_with_private_key(encrypted_data_b64):
    """使用用户的私钥解密数据。"""
    private_key = load_private_key()
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

def generate_aes_key():
    """生成一个随机的256位（32字节）AES密钥。"""
    return os.urandom(32)

def encrypt_with_aes(key, plaintext_bytes):
    """使用AES-GCM加密数据。返回base64编码的字符串。"""
    iv = os.urandom(12)  # GCM推荐的IV大小为12字节
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
    # 将IV和认证标签（GCM需要）附加到密文前
    return base64.b64encode(iv + encryptor.tag + ciphertext).decode('utf-8')

def decrypt_with_aes(key, encrypted_data_b64):
    """使用AES-GCM解密数据。需要base64编码的字符串。"""
    try:
        encrypted_data = base64.b64decode(encrypted_data_b64)
        iv = encrypted_data[:12]
        tag = encrypted_data[12:28] # GCM认证标签为16字节
        ciphertext = encrypted_data[28:]
        
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted_bytes = decryptor.update(ciphertext) + decryptor.finalize()
        return decrypted_bytes
    except Exception as e:
        print(f"AES解密失败: {e}")
        # 这可能是由于密钥错误（无效的标签）或数据损坏
        return None 