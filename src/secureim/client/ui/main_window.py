import os
import time
import uuid
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QTextEdit, QPushButton, QSplitter,
    QStackedWidget, QLabel, QInputDialog, QFileDialog, QMessageBox,
    QTextBrowser, QMenu, QStyle
)
from PyQt6.QtGui import QIcon, QPixmap, QImage, QColor, QPainter, QAction
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QUrl, QBuffer, QIODevice

# 默认文件保存目录（Windows）
# 在实际应用中，最好提供一个选项让用户自己配置
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "SecureIM")


class ChatWidget(QWidget):
    """用于单个聊天会话的控件。"""
    def __init__(self, partner_name, parent=None):
        super().__init__(parent)
        self.partner_name = partner_name
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.chat_display = QTextBrowser(self)
        self.chat_display.setOpenExternalLinks(True) # 允许打开外部链接，但需谨慎
        
        input_layout = QHBoxLayout()
        self.message_input = QTextEdit(self)
        self.message_input.setFixedHeight(60)
        
        button_layout = QVBoxLayout()
        self.send_button = QPushButton("发送文本")
        self.send_image_button = QPushButton("发送图片")
        self.send_file_button = QPushButton("发送文件")
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.send_image_button)
        button_layout.addWidget(self.send_file_button)
        
        input_layout.addWidget(self.message_input)
        input_layout.addLayout(button_layout)
        
        layout.addWidget(self.chat_display)
        layout.addLayout(input_layout)
        
        self.setLayout(layout)

    def append_message(self, sender, message, is_self=False):
        align_right = is_self
        bubble_color = "#dcf8c6" if align_right else "#ffffff"
        text_align = 'right' if align_right else 'left'
        
        # HTML-escape the message content to prevent rendering issues
        from html import escape
        message = escape(message).replace('\n', '<br>')

        html = f'''
            <div style="text-align: {text_align}; margin: 2px;">
                <div style="display: inline-block; text-align: left; max-width: 70%; 
                            background: {bubble_color}; padding: 8px; border-radius: 8px;">
                    <b>{escape(sender)}:</b><br>{message}
                </div>
            </div>
        '''
        self.chat_display.append(html)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def append_file_info(self, sender, filename, file_path=None, is_self=False):
        align_right = is_self
        bubble_color = "#dcf8c6" if align_right else "#ffffff"
        text_align = 'right' if align_right else 'left'
        
        if file_path:
            # For received files, link to the saved path
            inner_html = f'收到文件: <a href="{QUrl.fromLocalFile(file_path).toString()}">{filename}</a>'
        else:
            inner_html = f'已发送文件: {filename}'

        html = f'''
            <div style="text-align: {text_align}; margin: 2px;">
                <div style="display: inline-block; text-align: left; max-width: 70%; 
                            background: {bubble_color}; padding: 8px; border-radius: 8px;">
                    <b>{sender}:</b><br>{inner_html}
                </div>
            </div>
        '''
        self.chat_display.append(html)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def append_image(self, sender, image_bytes, hidden_text, is_self=False):
        try:
            image = QImage.fromData(image_bytes)
            pixmap = QPixmap.fromImage(image)
            
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buffer, "PNG")
            img_data = buffer.data().toBase64().data().decode()

            align_right = is_self
            bubble_color = "#dcf8c6" if align_right else "#ffffff"
            text_align = 'right' if align_right else 'left'

            html = f'''
                <div style="text-align: {text_align}; margin: 2px;">
                    <div style="display: inline-block; text-align: left; max-width: 70%; 
                                background: {bubble_color}; padding: 8px; border-radius: 8px;">
                        <b>{sender}:</b><br>
                        <img src="data:image/png;base64,{img_data}" width="250"><br>
                        <i>[隐藏文本]: {hidden_text}</i>
                    </div>
                </div>
            '''
            self.chat_display.append(html)
            self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
        except Exception as e:
            self.append_message("系统", f"显示图片时出错: {e}")


class MainWindow(QMainWindow):
    message_sent = pyqtSignal(str, str)
    stego_image_sent = pyqtSignal(str, str, str)
    file_sent = pyqtSignal(str, str)
    add_friend_requested = pyqtSignal(str)
    friend_selected = pyqtSignal(str)
    mode_change_requested = pyqtSignal(str, str)
    delete_friend_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.setWindowTitle(f"安全IM - 已登录为 {username}")
        self.setGeometry(100, 100, 900, 700)
        self.chat_widgets = {}
        self.friend_chat_modes = {}
        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5,5,5,5)
        header_label = QLabel("好友列表:")
        refresh_button = QPushButton()
        refresh_button.setToolTip("刷新好友列表")
        refresh_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        refresh_button.setIcon(refresh_icon)
        refresh_button.setFixedSize(QSize(28,28))
        refresh_button.clicked.connect(lambda: self.refresh_requested.emit())
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(refresh_button)

        self.friend_list_widget = QListWidget()
        self.friend_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.friend_list_widget.customContextMenuRequested.connect(self._show_friend_context_menu)
        self.friend_list_widget.currentItemChanged.connect(self._on_friend_selected)
        add_friend_button = QPushButton("添加好友")
        add_friend_button.clicked.connect(self._on_add_friend)
        
        left_layout.addWidget(header_widget)
        left_layout.addWidget(self.friend_list_widget)
        left_layout.addWidget(add_friend_button)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0,0,0,0)
        self.chat_stack = QStackedWidget()
        placeholder_widget = QLabel("选择一位好友开始聊天。")
        placeholder_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chat_stack.addWidget(placeholder_widget)
        right_layout.addWidget(self.chat_stack)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 650])
        main_layout.addWidget(splitter)

    def _create_status_icon(self, online_status_color, p2p_status_color=None):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QColor(online_status_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 14, 14)
        
        if p2p_status_color:
            painter.setBrush(QColor(p2p_status_color))
            painter.drawEllipse(4, 4, 6, 6)
        
        painter.end()
        return QIcon(pixmap)

    def _update_friend_item_display(self, item):
        friend_data = item.data(Qt.ItemDataRole.UserRole)
        username = friend_data.get("username")
        status = friend_data.get("status", "offline")
        
        display_text = username
        if status == "online":
            ip = friend_data.get("ip")
            port = friend_data.get("port")
            if ip and port:
                display_text += f"\n({ip}:{port})"
        
        item.setText(display_text)
        self._update_friend_item_icon(item)

    def update_friend_list(self, friends):
        self.friend_list_widget.clear()
        # Sort friends to show online users first
        friends.sort(key=lambda f: f.get("status", "offline") == "offline")
        
        for friend_data in friends:
            username = friend_data.get("username")
            self.friend_chat_modes.setdefault(username, 'cs')
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, friend_data)
            self.friend_list_widget.addItem(item)
            self._update_friend_item_display(item)

    def set_friend_status(self, friend_update_data):
        username = friend_update_data.get("username")
        for i in range(self.friend_list_widget.count()):
            item = self.friend_list_widget.item(i)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_data and item_data.get("username") == username:
                item_data.update(friend_update_data)
                item.setData(Qt.ItemDataRole.UserRole, item_data)
                self._update_friend_item_display(item)
                break

    def set_chat_mode(self, username, mode):
        self.friend_chat_modes[username] = mode
        for i in range(self.friend_list_widget.count()):
            item = self.friend_list_widget.item(i)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_data and item_data.get("username") == username:
                self._update_friend_item_icon(item)
                break

    def _update_friend_item_icon(self, item):
        friend_data = item.data(Qt.ItemDataRole.UserRole)
        username = friend_data.get("username")
        status = friend_data.get("status")
        is_online = status == 'online'
        mode = self.friend_chat_modes.get(username, 'cs')
        
        online_color = '#2ecc71' if is_online else '#95a5a6' # Green / Gray
        p2p_color = '#3498db' if mode == 'p2p' and is_online else None # Blue
        
        icon = self._create_status_icon(online_color, p2p_color)
        item.setIcon(icon)

    def add_message_to_chat(self, sender, message, is_self=False):
        partner = sender if not is_self else self.chat_stack.currentWidget().partner_name
        if partner not in self.chat_widgets:
            self._create_chat_widget(partner)
        display_sender = "我" if is_self else sender
        self.chat_widgets[partner].append_message(display_sender, message, is_self=is_self)

    def add_stego_image_to_chat(self, sender, image_bytes, hidden_text, is_self=False):
        partner = sender if not is_self else self.chat_stack.currentWidget().partner_name
        if partner not in self.chat_widgets:
            self._create_chat_widget(partner)
        display_sender = "我" if is_self else sender
        self.chat_widgets[partner].append_image(display_sender, image_bytes, hidden_text, is_self=is_self)
            
    def add_file_to_chat(self, sender, filename, file_bytes=None, is_self=False):
        partner = sender if not is_self else self.chat_stack.currentWidget().partner_name
        if partner not in self.chat_widgets:
            self._create_chat_widget(partner)
        
        display_sender = "我" if is_self else sender
        save_path = None
        
        if file_bytes:
            try:
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                base, ext = os.path.splitext(filename)
                save_path = os.path.join(DOWNLOAD_DIR, filename)
                counter = 1
                while os.path.exists(save_path):
                    save_path = os.path.join(DOWNLOAD_DIR, f"{base}_{counter}{ext}")
                    counter += 1
                with open(save_path, 'wb') as f:
                    f.write(file_bytes)
                self.chat_widgets[partner].append_message("系统", f"收到文件 {filename}，已保存至 {DOWNLOAD_DIR}", is_self=False)
            except Exception as e:
                err_msg = f"保存文件时出错: {e}"
                self.chat_widgets[partner].append_message("系统", err_msg, is_self=False)
        
        self.chat_widgets[partner].append_file_info(display_sender, filename, save_path, is_self=is_self)


    def _on_add_friend(self):
        text, ok = QInputDialog.getText(self, '添加好友', '输入用户名:')
        if ok and text:
            self.add_friend_requested.emit(text.strip())

    def _show_friend_context_menu(self, pos):
        item = self.friend_list_widget.itemAt(pos)
        if not item: return
        friend_data = item.data(Qt.ItemDataRole.UserRole)
        username = friend_data.get("username")
        is_online = friend_data.get("status") == "online"
        current_mode = self.friend_chat_modes.get(username, 'cs')
        
        menu = QMenu()
        mode_action_text = "切换到 P2P 模式" if current_mode == 'cs' else "切换到 C/S 模式"
        target_mode = 'p2p' if current_mode == 'cs' else 'cs'
        switch_mode_action = QAction(mode_action_text, self)
        switch_mode_action.triggered.connect(lambda: self.mode_change_requested.emit(username, target_mode))
        switch_mode_action.setEnabled(is_online)
        
        delete_action = QAction("删除好友", self)
        delete_action.triggered.connect(lambda: self.delete_friend_requested.emit(username))
        
        menu.addAction(switch_mode_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu.exec(self.friend_list_widget.mapToGlobal(pos))

    def _on_friend_selected(self, current_item, previous_item):
        if not current_item:
            self.chat_stack.setCurrentIndex(0)
            return
            
        friend_data = current_item.data(Qt.ItemDataRole.UserRole)
        if not friend_data: return
            
        current_username = friend_data.get("username")
        
        if current_item and (not previous_item or current_item != previous_item):
            self.friend_selected.emit(current_username)
            
        if current_username not in self.chat_widgets:
            self._create_chat_widget(current_username)
            
        self.chat_stack.setCurrentWidget(self.chat_widgets[current_username])

    def _create_chat_widget(self, partner_name):
        chat_widget = ChatWidget(partner_name)
        self.chat_stack.addWidget(chat_widget)
        self.chat_widgets[partner_name] = chat_widget
        chat_widget.send_button.clicked.connect(self._on_send_message)
        chat_widget.send_image_button.clicked.connect(self._on_send_image)
        chat_widget.send_file_button.clicked.connect(self._on_send_file)

    def _get_current_partner_name(self):
        item = self.friend_list_widget.currentItem()
        if not item: return None
        friend_data = item.data(Qt.ItemDataRole.UserRole)
        return friend_data.get("username") if friend_data else None
    
    def _is_current_partner_online(self):
        item = self.friend_list_widget.currentItem()
        if not item: return False
        friend_data = item.data(Qt.ItemDataRole.UserRole)
        return friend_data and friend_data.get("status") == "online"

    def _on_send_message(self):
        current_chat = self.chat_stack.currentWidget()
        if isinstance(current_chat, ChatWidget):
            message = current_chat.message_input.toPlainText().strip()
            partner_name = self._get_current_partner_name()
            if message and partner_name:
                if not self._is_current_partner_online():
                     QMessageBox.warning(self, "离线", f"{partner_name} 不在线。消息无法发送。")
                     return
                self.message_sent.emit(partner_name, message)
                self.add_message_to_chat(self.username, message, is_self=True)
                current_chat.message_input.clear()

    def _on_send_image(self):
        current_chat = self.chat_stack.currentWidget()
        if isinstance(current_chat, ChatWidget):
            hidden_text = current_chat.message_input.toPlainText().strip()
            partner_name = self._get_current_partner_name()
            if not hidden_text:
                QMessageBox.warning(self, "无文本", "请输入要隐藏在图片中的文本。")
                return
            if not partner_name or not self._is_current_partner_online():
                QMessageBox.warning(self, "离线", f"{partner_name or '好友'}不在线。图片无法发送。")
                return
            
            image_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Image Files (*.png *.jpg *.bmp)")
            if image_path:
                self.stego_image_sent.emit(partner_name, image_path, hidden_text)
                with open(image_path, 'rb') as f:
                    self.add_stego_image_to_chat(self.username, f.read(), hidden_text, is_self=True)
                current_chat.message_input.clear()
                
    def _on_send_file(self):
        current_chat = self.chat_stack.currentWidget()
        if isinstance(current_chat, ChatWidget):
            partner_name = self._get_current_partner_name()
            if not partner_name or not self._is_current_partner_online():
                QMessageBox.warning(self, "离线", f"{partner_name or '好友'}不在线。文件无法发送。")
                return
            
            file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
            if file_path:
                self.file_sent.emit(partner_name, file_path)
                filename = os.path.basename(file_path)
                self.add_file_to_chat(self.username, filename, is_self=True)

    def show_generic_response(self, title, message):
        QMessageBox.information(self, title, message) 