import threading

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

# 全局单例
online_users = OnlineUsers() 