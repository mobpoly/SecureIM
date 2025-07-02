import sys
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
        self.logic.friend_removed_signal.connect(lambda: self.logic.request_friends())
        self.logic.session_terminated_signal.connect(self.on_session_terminated)
        
    def _connect_login_window_signals(self):
        self.login_window.login_requested.connect(self.logic.login)
        self.login_window.register_requested.connect(self.logic.register)
        
    def _connect_main_window_signals(self):
        if self.main_window:
            self.main_window.message_sent.connect(self.logic.send_encrypted_message)
            self.main_window.stego_image_sent.connect(self.logic.send_steganography_image)
            self.main_window.file_sent.connect(self.logic.send_file)
            self.main_window.add_friend_requested.connect(self.logic.add_friend)
            self.main_window.friend_selected.connect(self.logic.initiate_key_exchange)
            self.main_window.mode_change_requested.connect(self.logic.set_mode_for_friend)
            self.main_window.refresh_requested.connect(self.logic.request_friends)
            self.main_window.delete_friend_requested.connect(self.logic.delete_friend)

    def on_login_success(self):
        current_username = self.login_window.login_username_input.text()
        self.login_window.close()
        
        self.main_window = MainWindow(username=current_username)
        self._connect_main_window_signals()
        self.main_window.show()
        
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

    def on_session_terminated(self, username, message):
        if self.main_window:
            self.main_window.add_system_message(username, message)

    def update_chat_mode_indicator(self, username, mode):
        if self.main_window:
            self.main_window.set_chat_mode(username, mode)

    def display_incoming_message(self, message_data):
        if self.main_window:
            self.main_window.add_message_to_chat(message_data['from'], message_data['content'])

    def display_incoming_stego(self, stego_data):
        if self.main_window:
            self.main_window.add_stego_image_to_chat(
                stego_data['from'], 
                stego_data['image_bytes'], 
                stego_data['hidden_text']
            )

    def display_incoming_file(self, file_data):
        if self.main_window:
            self.main_window.add_file_to_chat(
                file_data['from'],
                file_data['filename'],
                file_data['file_bytes']
            )
            
    def display_generic_response(self, response_data):
        if self.main_window:
            title = response_data.get('action', '服务器响应').replace('_', ' ').title()
            message = response_data.get('message', '未收到消息。')
            self.main_window.show_generic_response(title, message)
            if response_data.get('action') in ['add_friend', 'delete_friend'] and response_data.get('status') == 'success':
                self.logic.request_friends()

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