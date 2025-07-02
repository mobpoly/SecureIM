import threading
import time


class OnlineUsers:
    def __init__(self):
        self._users = {}
        self._lock = threading.Lock()

    def get_socket(self, username):
        with self._lock:
            user_info = self._users.get(username)
            return user_info['socket'] if user_info else None

    def get_user_info(self, username):
        with self._lock:
            return self._users.get(username)

    def get_all_usernames(self):
        with self._lock:
            return list(self._users.keys())

    def add_user(self, username, client_socket, address):
        with self._lock:
            self._users[username] = {'socket': client_socket, 'ip': address[0], 'port': address[1]}

    def remove_user(self, username):
        with self._lock:
            if username in self._users:
                del self._users[username]


class EmailVerificationCodes:
    def __init__(self):
        self._codes = {}  # email -> {"code": "123456", "timestamp": time.time()}
        self._lock = threading.Lock()

    def store_code(self, email, code):
        with self._lock:
            self._codes[email] = {"code": code, "timestamp": time.time()}

    def verify_code(self, email, code):
        with self._lock:
            if email not in self._codes:
                return False
            stored = self._codes[email]
            # 验证码5分钟内有效
            if time.time() - stored["timestamp"] > 300:
                del self._codes[email]
                return False
            if stored["code"] == code:
                del self._codes[email]  # 验证成功后删除
                return True
            return False

# 全局单例
online_users = OnlineUsers()
verification_codes = EmailVerificationCodes()