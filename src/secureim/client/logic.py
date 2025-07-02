import os
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from .networking import Networking
from .utils import crypto, steganography

SERVER_HOST = '10.21.236.83'
SERVER_PORT = 12345
P2P_PORT = 54321

class ClientLogic(QObject):
    # Signals for UI updates
    login_success_signal = pyqtSignal()
    login_failed_signal = pyqtSignal(str)
    registration_success_signal = pyqtSignal()
    registration_failed_signal = pyqtSignal(str)
    connection_failed_signal = pyqtSignal()
    # 在 ClientLogic 类的信号定义部分增加：
    verification_code_sent_signal = pyqtSignal(str)  # 验证码发送结果消息
    
    generic_response_signal = pyqtSignal(dict)
    online_friends_updated_signal = pyqtSignal(list)
    friend_status_updated_signal = pyqtSignal(dict)
    friend_removed_signal = pyqtSignal()

    incoming_message_signal = pyqtSignal(dict)
    incoming_stego_signal = pyqtSignal(dict)
    incoming_file_signal = pyqtSignal(dict)
    
    p2p_status_updated_signal = pyqtSignal(str, str)

    user_info_received_signal = pyqtSignal(dict)  # 新增信号：用户信息接收
    starred_friends_changed = pyqtSignal(dict)  # 新增信号：特别关注好友变化

    def __init__(self, parent=None):
        super().__init__(parent)
        self._username = None
        self._session_keys = {}  # friend_username -> aes_key
        self._chat_modes = {}    # friend_username -> 'cs' or 'p2p'
        self._p2p_addresses = {} # friend_username -> (ip, port)
        self._friends_data = {}  # friend_username -> friend_data_dict
        self._pending_messages = {} # friend_username -> [payload, ...]
        self._p2p_handshake_timers = {} # friend_username -> QTimer

        self.network = Networking(SERVER_HOST, SERVER_PORT, P2P_PORT)
        self.network.server_message_received_signal.connect(self.handle_server_message)
        self.network.p2p_message_received_signal.connect(self.handle_p2p_message)
        self.network.connection_failed_signal.connect(self.connection_failed_signal.emit)

        self._user_email = ""
        self._user_ip = ""
        # 连接特别关注信号
        self.starred_friends_changed.connect(self._handle_starred_friends_change)  # 新增连接

        if self.network.connect_to_server():
            self.network.setup_p2p_listener()

    def handle_server_message(self, data):
        msg_type = data.get("type")
        payload = data.get("payload", {})
        
        # Dispatch based on type
        if msg_type == "response":
            self._handle_server_response(data)
        elif msg_type == "all_friends_list":
            self._friends_data = {f['username']: f for f in payload}
            self.online_friends_updated_signal.emit(payload)
        elif msg_type == "public_key_response":
            self._handle_public_key_response(payload)
        elif msg_type == "receive_session_key":
            self._handle_receive_session_key(payload)
        elif msg_type == "receive_message":
            self._handle_receive_message(payload)
        elif msg_type == "friend_status_update":
            username = payload.get("username")
            if username in self._friends_data:
                self._friends_data[username].update(payload)
            else:
                self._friends_data[username] = payload
            self.friend_status_updated_signal.emit(payload)
        elif msg_type == "p2p_connection_info":
            self._handle_p2p_info(payload)
        elif msg_type == "p2p_connection_offer":
            self._handle_p2p_offer(payload)
        elif msg_type == "friend_removed":
            self.friend_removed_signal.emit()
        elif msg_type == "user_info":
            self._handle_user_info(payload)

    def _handle_user_info(self, payload):
        self._user_email = payload.get("email", "")
        self._user_ip = payload.get("ip", "")
        self.user_info_received_signal.emit({
            "email": self._user_email,
            "ip": self._user_ip
        })

    def request_user_info(self):
        request = {"type": "get_user_info"}
        self.network.send_request(request)

    def _handle_starred_friends_change(self, data):
        username = data.get("username")
        starred = data.get("starred")
        action = "add_star" if starred else "remove_star"

        request = {
            "type": "star_friend",
            "payload": {
                "friend_username": username,
                "action": action
            }
        }
        self.network.send_request(request)

    def handle_p2p_message(self, message):
        data = message.get("data", {})
        addr = message.get("addr")
        msg_type = data.get("type")
        payload = data.get("payload", {})
        sender = payload.get("from")

        if msg_type == "p2p_handshake":
            step = payload.get("step")
            if step == "offer":
                print(f"收到了来自 {sender} 的P2P连接请求")
                response = {"type": "p2p_handshake", "payload": {"from": self._username, "step": "ack"}}
                self.network.send_request(response, is_p2p=True, recipient_addr=addr)
            
            elif step == "ack":
                print(f"收到了来自 {sender} 的P2P连接确认")
                if sender in self._p2p_handshake_timers:
                    self._p2p_handshake_timers[sender].stop()
                    del self._p2p_handshake_timers[sender]
                
                self._chat_modes[sender] = 'p2p'
                self._p2p_addresses[sender] = addr
                self.p2p_status_updated_signal.emit(sender, 'p2p')
                
                response = {"type": "p2p_handshake", "payload": {"from": self._username, "step": "confirm"}}
                self.network.send_request(response, is_p2p=True, recipient_addr=addr)
                self.initiate_key_exchange(sender)

            elif step == "confirm":
                print(f"与 {sender} 的P2P连接已最终确认")
                self._chat_modes[sender] = 'p2p'
                self._p2p_addresses[sender] = addr
                self.p2p_status_updated_signal.emit(sender, 'p2p')
        
        elif self._chat_modes.get(sender) == 'p2p':
            if msg_type == "receive_message":
                self._handle_receive_message(payload)
            elif msg_type == "receive_session_key":
                self._handle_receive_session_key(payload)
        else:
            print(f"忽略了来自 {sender} 的非P2P模式下的消息，类型为'{msg_type}'")

    # --- Specific Message Handlers ---

    def _handle_server_response(self, data):
        action = data.get("action")
        if action == "register":
            if data.get("status") == "success":
                self.registration_success_signal.emit()
            else:
                self.registration_failed_signal.emit(data.get("message"))
        # 在 _handle_server_response 方法中增加处理：
        elif action == "request_verification_code":
            message = data.get("message", "")
            self.verification_code_sent_signal.emit(message)
        elif action == "login":
            if data.get("status") == "success":
                self.login_success_signal.emit()
            else:
                self.login_failed_signal.emit(data.get("message"))
        elif action == "request_p2p" and data.get("status") == "error":
            # Extract username from message like "User 'X' is not online."
            try:
                username = data.get("message").split("'")[1]
                self.p2p_status_updated_signal.emit(username, 'cs')
            except IndexError:
                pass
        else:
            self.generic_response_signal.emit(data)

    def _handle_public_key_response(self, payload):
        friend_username = payload.get("username")
        public_key_pem = payload.get("public_key")
        if friend_username and public_key_pem:
            aes_key = crypto.generate_aes_key()
            self._session_keys[friend_username] = aes_key

            print(f"---BEGIN {friend_username} PUBLIC KEY---")
            print(public_key_pem)
            print(f"---END {friend_username} PUBLIC KEY---")
            print(f"---BEGIN GENERATED SESSION KEY for {friend_username}---")
            print(aes_key.hex())
            print(f"---END GENERATED SESSION KEY for {friend_username}---")

            encrypted_key = crypto.encrypt_with_public_key(public_key_pem, aes_key)
            
            mode = self._chat_modes.get(friend_username, 'cs')
            if mode == 'p2p':
                request = {"type": "receive_session_key", "payload": {"from": self._username, "key": encrypted_key}}
                self.network.send_request(request, is_p2p=True, recipient_addr=self._p2p_addresses.get(friend_username))
            else:
                request = {"type": "relay_session_key", "payload": {"to": friend_username, "key": encrypted_key}}
                self.network.send_request(request)
            print(f"Initiated key exchange with {friend_username} via {'P2P' if mode == 'p2p' else 'C/S'}.")

    def _handle_receive_session_key(self, payload):
        sender = payload.get("from")
        encrypted_key_b64 = payload.get("key")
        if sender and encrypted_key_b64:
            aes_key = crypto.decrypt_with_private_key(encrypted_key_b64)
            if aes_key:
                self._session_keys[sender] = aes_key
                print(f"---BEGIN RECEIVED SESSION KEY from {sender}---")
                print(aes_key.hex())
                print(f"---END RECEIVED SESSION KEY from {sender}---")
                print(f"Secure session established with {sender}.")
                if sender in self._pending_messages:
                    for cached_payload in self._pending_messages.pop(sender):
                        self._process_decrypted_message(sender, aes_key, cached_payload)
            else:
                print(f"Failed to decrypt session key from {sender}.")

    def _handle_receive_message(self, payload):
        sender = payload.get("from")
        aes_key = self._session_keys.get(sender)
        if not aes_key:
            self._pending_messages.setdefault(sender, []).append(payload)
            print(f"Message from {sender} cached, waiting for session key.")
            return
        self._process_decrypted_message(sender, aes_key, payload)

    def _process_decrypted_message(self, sender, aes_key, payload):
        content_b64 = payload.get("content")
        decrypted_content = crypto.decrypt_with_aes(aes_key, content_b64)
        if not decrypted_content:
            print(f"Failed to decrypt message from {sender}. It might be corrupted or the key is wrong.")
            return

        if payload.get("is_stego", False):
            hidden_text = steganography.extract_text_from_image(decrypted_content)
            if hidden_text:
                self.incoming_stego_signal.emit({"from": sender, "image_bytes": decrypted_content, "hidden_text": hidden_text})
            else:
                print(f"Received stego image from {sender}, but failed to extract text.")
        elif payload.get("is_file", False):
            filename = payload.get("filename", "unknown_file")
            self.incoming_file_signal.emit({"from": sender, "filename": filename, "file_bytes": decrypted_content})
        else:
            self.incoming_message_signal.emit({"from": sender, "content": decrypted_content.decode('utf-8')})

    def _handle_p2p_info(self, payload):
        # Server response with target's address
        username = payload.get("username")
        ip = payload.get("ip")
        port = payload.get("port")
        if all([username, ip, port]):
            self._p2p_addresses[username] = (ip, port)
            print(f"Got P2P address for {username}: {ip}:{port}")
            # You can now initiate a P2P key exchange or send a P2P message
            self.set_mode_for_friend(username, "p2p")

    def _handle_p2p_offer(self, payload):
        # Offer from another client to connect P2P
        username = payload.get("from")
        ip = payload.get("ip")
        port = payload.get("port")
        if all([username, ip, port]):
            self._p2p_addresses[username] = (ip, port)
            print(f"Received P2P offer from {username} at {ip}:{port}")

    def _p2p_handshake_timeout(self, friend_username):
        print(f"与 {friend_username} 的P2P连接请求超时。")
        if friend_username in self._p2p_handshake_timers:
            self._p2p_handshake_timers[friend_username].stop()
            del self._p2p_handshake_timers[friend_username]
        
        self._chat_modes[friend_username] = 'cs'
        self.p2p_status_updated_signal.emit(friend_username, 'p2p_fail')

    # --- User-Triggered Actions ---

    # 修改现有的 register 方法：
    def register(self, username, password, email, verification_code):  # 修改：增加验证码参数
        crypto.generate_keys_if_not_exist()
        public_key = crypto.get_public_key_pem()
        request = {
            "type": "register",
            "payload": {
                "username": username,
                "password": password,
                "email": email,
                "public_key": public_key,
                "verification_code": verification_code  # 新增
            }
        }
        self.network.send_request(request)

    def login(self, username, password):
        self._username = username
        request = {"type": "login", "payload": {"username": username, "password": password}}
        self.network.send_request(request)

    def initiate_key_exchange(self, friend_username):
        if self.has_session_key(friend_username): return
        friend_data = self._friends_data.get(friend_username)
        if not friend_data or friend_data.get("status") != "online":
            print(f"Cannot initiate key exchange: {friend_username} is offline.")
            return
        request = {"type": "get_public_key", "payload": {"username": friend_username}}
        self.network.send_request(request)

    def send_encrypted_message(self, recipient, message):
        aes_key = self._session_keys.get(recipient)
        if not aes_key:
            print(f"No session key for {recipient}. Cannot send message.")
            return
        encrypted_content = crypto.encrypt_with_aes(aes_key, message.encode('utf-8'))
        self._send_payload(recipient, {"content": encrypted_content})

    def send_steganography_image(self, recipient, image_path, hidden_text):
        aes_key = self._session_keys.get(recipient)
        if not aes_key:
            print(f"No session key for {recipient}. Cannot send image.")
            return
        
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        stego_bytes = steganography.embed_text_in_image(image_bytes, hidden_text)
        if not stego_bytes:
            print("Steganography failed.")
            return

        encrypted_content = crypto.encrypt_with_aes(aes_key, stego_bytes)
        self._send_payload(recipient, {"content": encrypted_content, "is_stego": True})

    def send_file(self, recipient, file_path):
        aes_key = self._session_keys.get(recipient)
        if not aes_key:
            print(f"No session key for {recipient}. Cannot send file.")
            return

        with open(file_path, 'rb') as f:
            file_bytes = f.read()
        
        encrypted_content = crypto.encrypt_with_aes(aes_key, file_bytes)
        filename = os.path.basename(file_path)
        self._send_payload(recipient, {"content": encrypted_content, "is_file": True, "filename": filename})

    def _send_payload(self, recipient, payload):
        mode = self._chat_modes.get(recipient, 'cs')
        payload['from'] = self._username
        
        request_type = "receive_message" # This is the type for the final recipient
        
        if mode == 'p2p':
            # In P2P mode, send directly
            addr = self._p2p_addresses.get(recipient)
            if addr:
                request = {"type": request_type, "payload": payload}
                self.network.send_request(request, is_p2p=True, recipient_addr=addr)
            else:
                print(f"无法在P2P模式下发送给 {recipient}，缺少地址。")
        else:
            # In C/S mode, relay through server
            payload['to'] = recipient
            request = {"type": "relay_message", "payload": payload}
            self.network.send_request(request)

    def set_mode_for_friend(self, friend_username, mode):
        if self._chat_modes.get(friend_username) == mode and mode == 'p2p':
            print("已经处于P2P模式。")
            return
        
        if mode == 'cs':
            self._chat_modes[friend_username] = 'cs'
            self.p2p_status_updated_signal.emit(friend_username, 'cs')
            return

        if self._p2p_handshake_timers.get(friend_username):
            print(f"与 {friend_username} 的P2P握手已在进行中。")
            return

        friend_data = self._friends_data.get(friend_username)
        if not friend_data or friend_data.get('status') != 'online' or not friend_data.get('ip'):
            print(f"无法向 {friend_username} 发起P2P连接：用户离线或地址未知。")
            self.p2p_status_updated_signal.emit(friend_username, 'p2p_fail')
            return

        self.p2p_status_updated_signal.emit(friend_username, 'p2p_connecting')
        
        request = {"type": "p2p_handshake", "payload": {"from": self._username, "step": "offer"}}
        self.network.send_request(request, is_p2p=True, recipient_addr=(friend_data["ip"], P2P_PORT))

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._p2p_handshake_timeout(friend_username))
        timer.start(5000)
        self._p2p_handshake_timers[friend_username] = timer

    def request_friends(self):
        self.network.send_request({"type": "get_friends"})

    def add_friend(self, friend_username):
        self.network.send_request({"type": "add_friend", "payload": {"friend_username": friend_username}})

    def delete_friend(self, friend_username):
        self.network.send_request({"type": "delete_friend", "payload": {"friend_username": friend_username}})
    
    def has_session_key(self, friend_username):
        return friend_username in self._session_keys

    def disconnect(self):
        self.network.disconnect()

        # 在类的末尾增加新方法：

    def request_verification_code(self, email):
        """请求邮箱验证码"""
        request = {"type": "request_verification_code", "payload": {"email": email}}
        self.network.send_request(request)