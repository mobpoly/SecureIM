import os
import time
import uuid

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from .networking import Networking
from .utils import crypto, steganography

SERVER_HOST = '10.21.242.252'
SERVER_PORT = 12345
P2P_PORT = 54321

class ClientLogic(QObject):
    # Signals for UI updates
    login_success_signal = pyqtSignal(str)
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
    logout_success_signal = pyqtSignal()
    p2p_status_updated_signal = pyqtSignal(str, str)
    session_terminated_signal = pyqtSignal(str, str)  # 重新添加会话终止信号

    user_info_received_signal = pyqtSignal(dict)  # 新增信号：用户信息接收
    starred_friends_changed = pyqtSignal(dict)  # 新增信号：特别关注好友变化
    mode_sync_request_signal = pyqtSignal(str, str)


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
        self._mode_sync_pending = {}
        self._pending_mode_requests = {}
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
            self._handle_friend_status_update(payload)
        elif msg_type == "p2p_connection_info":
            self._handle_p2p_info(payload)
        elif msg_type == "p2p_connection_offer":
            self._handle_p2p_offer(payload)
        elif msg_type == "friend_removed":
            self.friend_removed_signal.emit()
        elif msg_type == "user_info":
            self._handle_user_info(payload)
        elif msg_type == "logout_response":
            # 服务器确认退出登录
            pass
        elif msg_type == "mode_change_request":
            self._handle_mode_change_request(payload)
        elif msg_type == "mode_change_response":
            self._handle_mode_change_response(payload)
        elif msg_type == "mode_change_notification":
            self._handle_mode_change_notification(payload)

    def _handle_mode_change_request(self, payload):
        """处理来自其他用户的模式切换请求"""
        from_username = payload.get("from_username")
        requested_mode = payload.get("requested_mode")
        request_id = payload.get("request_id")

        if from_username and requested_mode:
            self._pending_mode_requests = getattr(self, '_pending_mode_requests', {})
            self._pending_mode_requests[from_username] = request_id
            # 通知UI显示模式切换请求
            self.mode_sync_request_signal.emit(from_username, requested_mode)

    def _handle_mode_change_response(self, payload):
        """处理模式切换请求的响应"""
        from_username = payload.get("from_username")  # Updated field name
        accepted = payload.get("accepted")
        requested_mode = payload.get("requested_mode")

        if from_username in self._mode_sync_pending:
            if accepted:
                # 对方同意，开始实际的模式切换
                if requested_mode == 'p2p':
                    self._initiate_p2p_connection(from_username)
                else:
                    self._switch_to_cs_mode(from_username)
            else:
                # 对方拒绝，取消切换
                self.p2p_status_updated_signal.emit(from_username, 'p2p_fail')

            del self._mode_sync_pending[from_username]

    def _handle_mode_change_notification(self, payload):
        """处理模式切换完成通知"""
        from_username = payload.get("from_username")  # Updated field name
        new_mode = payload.get("new_mode")

        if from_username and new_mode:
            # 同步更新本地模式状态
            self._chat_modes[from_username] = new_mode
            self.p2p_status_updated_signal.emit(from_username, new_mode)

            print(f"[DEBUG] 收到模式切换通知: {from_username} -> {new_mode}")

    def _handle_user_info(self, payload):
        print(f"[DEBUG] 处理用户信息响应: {payload}")
        self._user_email = payload.get("email", "")
        self._user_ip = payload.get("ip", "")
        self.user_info_received_signal.emit({
            "email": self._user_email,
            "ip": self._user_ip
        })

    def request_user_info(self):
        print("[DEBUG] 正在请求用户信息...")
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
        """改进的P2P消息处理"""
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

                # 设置P2P模式
                self._chat_modes[sender] = 'p2p'
                self._p2p_addresses[sender] = addr

                # 通知双方模式切换成功
                self.p2p_status_updated_signal.emit(sender, 'p2p')
                self._notify_mode_change(sender, 'p2p')

                # 发送确认
                response = {"type": "p2p_handshake", "payload": {"from": self._username, "step": "confirm"}}
                self.network.send_request(response, is_p2p=True, recipient_addr=addr)

                # 启动密钥交换
                self.initiate_key_exchange(sender)

            elif step == "confirm":
                print(f"与 {sender} 的P2P连接已最终确认")

                # 设置P2P模式并通知
                self._chat_modes[sender] = 'p2p'
                self._p2p_addresses[sender] = addr


        # 处理其他P2P消息...
        elif self._chat_modes.get(sender) == 'p2p':
            if msg_type == "receive_message":
                self._handle_receive_message(payload)
            elif msg_type == "receive_session_key":
                self._handle_receive_session_key(payload)

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
                server_username = data.get("username")
                if server_username:
                    self._username = server_username

                user_info = data.get("user_info", {})
                print(f"[DEBUG] 登录响应数据: {data}")
                if user_info:
                    self._user_email = user_info.get("email", "")
                    self._user_ip = user_info.get("ip", "")
                    print(f"[DEBUG] 从登录响应获取用户信息: 邮箱={self._user_email}, IP={self._user_ip}")

                    # 先发送用户信息信号
                    self.user_info_received_signal.emit({
                        "email": self._user_email,
                        "ip": self._user_ip
                    })
                else:
                    print("[WARNING] 登录响应中没有用户信息，将发送额外请求")
                    # 如果没有用户信息，立即请求
                    QTimer.singleShot(0, self.request_user_info)

                # 然后再发送登录成功信号
                self.login_success_signal.emit(self._username)
            else:
                self.login_failed_signal.emit(data.get("message", "未知错误"))
        elif action == "get_user_info":  # 保留这个，以防需要手动刷新用户信息
            print(f"[DEBUG] 处理用户信息响应: {data}")
            if data.get("status") == "success":
                payload = data.get("payload", {})
                self._handle_user_info(payload)
            else:
                print(f"[DEBUG] 获取用户信息失败: {data.get('message')}")
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
        timestamp = payload.get("timestamp", time.time())

        # 获取当前聊天模式
        current_mode = self._chat_modes.get(sender, 'cs')

        decrypted_content = crypto.decrypt_with_aes(aes_key, content_b64)
        if not decrypted_content:
            print(f"Failed to decrypt message from {sender}. It might be corrupted or the key is wrong.")
            return

        if payload.get("is_stego", False):
            hidden_text = steganography.extract_text_from_image(decrypted_content)
            if hidden_text:
                self.incoming_stego_signal.emit({
                    "from": sender,
                    "image_bytes": decrypted_content,
                    "hidden_text": hidden_text,
                    "timestamp": timestamp,
                    "mode": current_mode  # 添加模式信息
                })
            else:
                print(f"Received stego image from {sender}, but failed to extract text.")
        elif payload.get("is_file", False):
            filename = payload.get("filename", "unknown_file")
            self.incoming_file_signal.emit({
                "from": sender,
                "filename": filename,
                "file_bytes": decrypted_content,
                "timestamp": timestamp,
                "mode": current_mode  # 添加模式信息
            })
        else:
            self.incoming_message_signal.emit({
                "from": sender,
                "content": decrypted_content.decode('utf-8'),
                "mode": current_mode,
                "timestamp": timestamp
            })

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

    def _handle_friend_status_update(self, payload):
        username = payload.get("username")
        status = payload.get("status")

        if not username:
            return

        # Update friend data cache
        if username in self._friends_data:
            self._friends_data[username].update(payload)
        else:
            self._friends_data[username] = payload

        # Notify UI to update friend list (e.g., icon color)
        self.friend_status_updated_signal.emit(payload)

        # --- SESSION MANAGEMENT LOGIC ---
        if status == "offline":
            # 1. If in P2P mode, switch back to C/S
            if self._chat_modes.get(username) == 'p2p':
                self._chat_modes[username] = 'cs'
                print(f"Switched back to C/S mode for {username} as they went offline.")
                self.p2p_status_updated_signal.emit(username, 'cs')

            # 2. Terminate session if it exists
            if username in self._session_keys:
                del self._session_keys[username]
                print(f"Session with {username} terminated as they went offline.")
                message = "对方已下线，会话已结束。重新上线后需要再次协商密钥。"
                self.session_terminated_signal.emit(username, message)

    def logout(self):
        """处理退出登录"""
        if self._username:
            # 发送退出登录请求到服务器
            request = {"type": "logout"}
            self.network.send_request(request)

        # 清理本地状态
        self._username = None
        self._session_keys = {}
        self._chat_modes = {}
        self._p2p_addresses = {}
        self._friends_data = {}
        self._pending_messages = {}



        # 通知UI
        self.logout_success_signal.emit()

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
        if not self.network._socket:  # 检查是否已连接服务器
            self.connection_failed_signal.emit()
            return
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

        # 添加时间戳
        timestamp = time.time()

        encrypted_content = crypto.encrypt_with_aes(aes_key, message.encode('utf-8'))
        self._send_payload(recipient, {
            "content": encrypted_content,
            "timestamp": timestamp  # 添加时间戳
        })

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

        # 只发送一次，包含所有必要信息
        self._send_payload(recipient, {
            "content": encrypted_content,
            "is_stego": True,
            "timestamp": time.time()
        })

    def send_file(self, recipient, file_path):
        aes_key = self._session_keys.get(recipient)
        if not aes_key:
            print(f"No session key for {recipient}. Cannot send file.")
            return

        with open(file_path, 'rb') as f:
            file_bytes = f.read()

        encrypted_content = crypto.encrypt_with_aes(aes_key, file_bytes)
        filename = os.path.basename(file_path)

        # 只发送一次，包含所有必要信息
        self._send_payload(recipient, {
            "content": encrypted_content,
            "is_file": True,
            "filename": filename,
            "timestamp": time.time()
        })

    def _send_payload(self, recipient, payload):
        """改进的消息发送方法"""
        mode = self._chat_modes.get(recipient, 'cs')
        payload['from'] = self._username

        request_type = "receive_message"

        if mode == 'p2p':
            # P2P模式发送
            addr = self._p2p_addresses.get(recipient)
            if addr:
                request = {"type": request_type, "payload": payload}
                success = self.network.send_request(request, is_p2p=True, recipient_addr=addr)

                # 如果P2P发送失败，可以尝试重试一次
                if not success:
                    print(f"P2P发送失败，尝试重试一次: {recipient}")
                    success = self.network.send_request(request, is_p2p=True, recipient_addr=addr)

                    # 只有在重试也失败时才切换到C/S模式
                    if not success:
                        print(f"P2P重试也失败，回退到C/S模式: {recipient}")
                        self._switch_to_cs_mode(recipient)
                        self._send_via_server(recipient, payload)
            else:
                print(f"无法在P2P模式下发送给 {recipient}，缺少地址，回退到C/S模式")
                self._switch_to_cs_mode(recipient)
                self._send_via_server(recipient, payload)
        else:
            # C/S模式发送
            self._send_via_server(recipient, payload)

    def _send_via_server(self, recipient, payload):
        """通过服务器发送消息"""
        payload['to'] = recipient
        request = {"type": "relay_message", "payload": payload}
        self.network.send_request(request)

    def set_mode_for_friend(self, friend_username, mode):
        current_mode = self._chat_modes.get(friend_username, 'cs')
        # 如果已经是目标模式，直接返回
        if current_mode == mode:
            print(f"已经处于 {mode} 模式")
            return
        


        friend_data = self._friends_data.get(friend_username)
        if not friend_data or friend_data.get('status') != 'online' or not friend_data.get('ip'):
            print(f"无法向 {friend_username} 发起连接：用户离线或地址未知。")
            self.p2p_status_updated_signal.emit(friend_username, 'p2p_fail')
            return

        if mode == 'cs':
            # 切换到C/S模式比较简单，直接切换并通知对方
            self._switch_to_cs_mode(friend_username)
            self._notify_mode_change(friend_username, 'cs')
        else:
            # 切换到P2P模式需要征得对方同意
            self._request_mode_change(friend_username, mode)

    def _request_mode_change(self, friend_username, requested_mode):
        """请求模式切换"""
        self._mode_sync_pending[friend_username] = requested_mode
        request_id = str(uuid.uuid4())

        request = {
            "type": "mode_change_request",
            "payload": {
                "target_username": friend_username,
                "requested_mode": requested_mode,
                "request_id": request_id
            }
        }
        self.network.send_request(request)

        # 显示连接中状态
        self.p2p_status_updated_signal.emit(friend_username, 'p2p_connecting')

    def respond_to_mode_change_request(self, from_user, requested_mode, approved):
        """响应模式切换请求"""
        request_id = self._pending_mode_requests.get(from_user, str(uuid.uuid4()))
        request = {
            "type": "mode_change_response",
            "payload": {
                "target_username": from_user,  # Changed from "to_user"
                "request_id": request_id,      # Added request_id
                "accepted": approved,          # Changed from "approved"
                "requested_mode": requested_mode
            }
        }
        self.network.send_request(request)

        if approved and requested_mode == 'p2p':
            # 如果同意P2P连接，准备接受连接
            self._prepare_for_p2p_connection(from_user)

    def _initiate_p2p_connection(self, friend_username):
        """发起P2P连接（在对方同意后）"""
        friend_data = self._friends_data.get(friend_username)
        if not friend_data:
            return

        # 发送P2P握手
        request = {"type": "p2p_handshake", "payload": {"from": self._username, "step": "offer"}}
        self.network.send_request(request, is_p2p=True,
                                  recipient_addr=(friend_data["ip"], P2P_PORT))

        # 设置超时
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._p2p_handshake_timeout(friend_username))
        timer.start(10000)  # 10秒超时
        self._p2p_handshake_timers[friend_username] = timer

    def _prepare_for_p2p_connection(self, friend_username):
        """准备接受P2P连接"""
        # 设置状态为等待P2P连接
        self.p2p_status_updated_signal.emit(friend_username, 'p2p_connecting')

    def _switch_to_cs_mode(self, friend_username):
        """切换到C/S模式"""
        self._chat_modes[friend_username] = 'cs'
        self.p2p_status_updated_signal.emit(friend_username, 'cs')

        # 清理P2P相关状态
        if friend_username in self._p2p_addresses:
            del self._p2p_addresses[friend_username]

    def _notify_mode_change(self, friend_username, new_mode):
        """通知对方模式已切换"""
        request = {
            "type": "mode_change_notification",
            "payload": {
                "target_username": friend_username,
                "new_mode": new_mode
            }
        }
        self.network.send_request(request)

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