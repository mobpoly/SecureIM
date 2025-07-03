import sys
import time

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from .logic import ClientLogic
from .ui.login_window import LoginWindow
from .ui.main_window import MainWindow

class MainController:
    def __init__(self, app):
        self.app = app
        self.logic = ClientLogic()
        self.login_window = LoginWindow()
        self.main_window = None
        self.user_name = ""
        self.user_email = ""  # 存储用户邮箱
        self.user_ip = ""  # 存储用户IP

        self._connect_logic_signals()
        self._connect_login_window_signals()
        
        self.login_window.show()

    def _connect_logic_signals(self):
        self.logic.connection_failed_signal.connect(self.on_connection_failed)
        self.logic.login_success_signal.connect(self.on_login_success)
        self.logic.login_failed_signal.connect(self.login_window.show_error)
        self.logic.registration_success_signal.connect(lambda: self.login_window.show_info("注册成功！现在您可以登录了。"))
        self.logic.registration_failed_signal.connect(self.login_window.show_error)
        self.logic.online_friends_updated_signal.connect(self.update_friend_list)
        self.logic.friend_status_updated_signal.connect(self.update_friend_status)
        self.logic.incoming_message_signal.connect(self.display_incoming_message)
        self.logic.incoming_stego_signal.connect(self.display_incoming_stego)
        self.logic.incoming_file_signal.connect(self.display_incoming_file)
        self.logic.generic_response_signal.connect(self.display_generic_response)
        self.logic.p2p_status_updated_signal.connect(self.update_chat_mode_indicator)
        self.logic.friend_removed_signal.connect(self.on_friend_removed)
        # 在 _connect_logic_signals 方法中增加：
        self.logic.verification_code_sent_signal.connect(self.on_verification_code_sent)
        self.logic.user_info_received_signal.connect(self.handle_user_info)
        self.logic.starred_friends_changed.connect(self._handle_starred_friends)
        self.logic.logout_success_signal.connect(self.on_logout_success)
        self.logic.session_terminated_signal.connect(self.on_session_terminated)
        self.logic.mode_sync_request_signal.connect(self.handle_mode_sync_request)

    def handle_mode_sync_request(self, from_user, requested_mode):
        """处理模式切换请求"""
        if not self.main_window:
            return

        mode_text = "P2P直连" if requested_mode == 'p2p' else "服务器中继"
        reply = QMessageBox.question(
            self.main_window,
            "模式切换请求",
            f"{from_user} 请求切换到 {mode_text} 模式。\n是否同意？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        approved = reply == QMessageBox.StandardButton.Yes
        self.logic.respond_to_mode_change_request(from_user, requested_mode, approved)

    def _connect_login_window_signals(self):
        self.login_window.login_requested.connect(self.logic.login)
        self.login_window.register_requested.connect(self.logic.register)
        self.login_window.verification_code_requested.connect(self.logic.request_verification_code)


    def _connect_main_window_signals(self):
        if self.main_window:
            self.main_window.message_sent.connect(self.logic.send_encrypted_message)
            self.main_window.stego_image_sent.connect(self.logic.send_steganography_image)
            self.main_window.file_sent.connect(self.logic.send_file)
            self.main_window.add_friend_requested.connect(self.logic.add_friend)
            self.main_window.friend_selected.connect(self.on_friend_selected)
            self.main_window.mode_change_requested.connect(self.logic.set_mode_for_friend)
            self.main_window.refresh_requested.connect(self.logic.request_friends)
            self.main_window.delete_friend_requested.connect(self.logic.delete_friend)
            self.main_window.logout_requested.connect(self.logic.logout)

    def on_logout_success(self):
        """处理退出登录成功"""
        if self.main_window:
            self.main_window.close()
            self.main_window = None

        # 重新显示登录窗口
        self.login_window = LoginWindow()
        self._connect_login_window_signals()
        self.login_window.show()

        # 重置用户信息
        self.user_email = ""
        self.user_ip = ""

    def on_login_success(self, username):
        self.user_name = username
        self.login_window.close()

        # 检查是否已从登录响应中获取了用户信息
        email = getattr(self.logic, '_user_email', '') or "获取中..."
        ip = getattr(self.logic, '_user_ip', '') or "获取中..."

        print(f"[DEBUG] 登录成功，用户信息: 用户名={username}, 邮箱={email}, IP={ip}")

        # 创建主窗口
        self.main_window = MainWindow(
            username=self.user_name,
            email=email,
            ip=ip,
            logic=self.logic
        )

        self._connect_main_window_signals()
        self.main_window.show()

        # 如果登录时没有获取到用户信息，才发送额外请求
        if email == "获取中..." or ip == "获取中...":
            print("[DEBUG] 用户信息不完整，发送额外请求")
            QTimer.singleShot(200, self.logic.request_user_info)

        # 请求好友列表
        QTimer.singleShot(500, self.logic.request_friends)


    def on_connection_failed(self):
        active_window = self.main_window if self.main_window and self.main_window.isVisible() else self.login_window
        QMessageBox.critical(active_window, "连接错误", "无法连接到服务器。应用程序将关闭。")
        self.app.quit()
        
    def update_friend_list(self, friends):
        if self.main_window:
            self.main_window.update_friend_list(friends)
            
    def update_friend_status(self, status_update):
        if self.main_window:
            self.main_window.set_friend_status(status_update)

    def update_chat_mode_indicator(self, username, mode):
        if self.main_window:
            self.main_window.set_chat_mode(username, mode)

    def display_incoming_message(self, message_data):
        if self.main_window:
            mode = message_data.get('mode', 'cs')  # 从消息数据中获取模式
            self.main_window.add_message_to_chat(
                message_data['from'],
                message_data['content'],
                mode=mode
            )

    def display_incoming_stego(self, stego_data):
        if self.main_window:
            self.main_window.add_stego_image_to_chat(
                stego_data['from'],
                stego_data['image_bytes'],
                stego_data['hidden_text'],
                mode=stego_data.get('mode', 'cs'),
                timestamp=stego_data.get('timestamp', time.time())
            )

    def display_incoming_file(self, file_data):
        if self.main_window:
            self.main_window.add_file_to_chat(
                file_data['from'],
                file_data['filename'],
                file_data['file_bytes'],
                mode=file_data.get('mode', 'cs'),
                timestamp=file_data.get('timestamp', time.time())
            )

            
    def display_generic_response(self, response_data):
        if self.main_window:
            title = response_data.get('action', '服务器响应').replace('_', ' ').title()
            message = response_data.get('message', '未收到消息。')
            self.main_window.show_generic_response(title, message)
            if response_data.get('action') == 'add_friend' and response_data.get('status') == 'success':
                self.logic.request_friends()

    def on_verification_code_sent(self, message):
        if self.login_window:
            self.login_window.show_verification_code_result(message)

    def handle_user_info(self, user_info):
        self.user_email = user_info.get("email", "")
        self.user_ip = user_info.get("ip", "")

        # 添加调试信息
        print(f"[DEBUG] 处理用户信息: 邮箱={self.user_email}, IP={self.user_ip}")

        # 更新主窗口的用户信息
        if self.main_window:
            self.main_window.update_user_info(self.user_email, self.user_ip)
            print(f"[DEBUG] 主窗口用户信息已更新: 邮箱={self.user_email}, IP={self.user_ip}")

    def _handle_starred_friends(self, data):
        if self.main_window:
            # 更新UI
            self.main_window.update_friend_list(list(self.logic._friends_data.values()))#--------+++++++++++++++？？？？？

    def on_session_terminated(self, username, message):
        if self.main_window:
            self.main_window.add_system_message(username, message)

    def on_friend_removed(self, username):
        if self.main_window:
            self.main_window.remove_friend(username)

    def on_friend_selected(self, username):
        """处理用户在UI上选择好友的事件。"""
        # 1. 触发密钥交换（如果需要）
        self.logic.initiate_key_exchange(username)

        # 2. 确保聊天输入框状态正确
        if self.main_window:
            friend_data = self.logic._friends_data.get(username, {})
            is_online = friend_data.get("status") == "online"

            chat_widget = self.main_window.chat_widgets.get(username)
            if chat_widget:
                chat_widget.set_input_enabled(is_online)


def start_client():
    app = QApplication(sys.argv)
    # Apply a basic stylesheet for better look and feel
    app.setStyleSheet("""
        QWidget {
            font-size: 14px;
        }
        QPushButton {
            padding: 8px;
            border-radius: 4px;
            background-color: #0078d4;
            color: white;
            border: none;
        }
        QPushButton:hover {
            background-color: #005a9e;
        }
        QPushButton:pressed {
            background-color: #004578;
        }
        QLineEdit, QTextEdit {
            border: 1px solid #ccc;
            padding: 5px;
            border-radius: 4px;
        }
        QListWidget {
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        #linkButton {
            background-color: transparent;
            border: none;
            color: #0078d4;
            text-decoration: underline;
        }
    """)
    controller = MainController(app)
    sys.exit(app.exec())

if __name__ == '__main__':
    start_client() 