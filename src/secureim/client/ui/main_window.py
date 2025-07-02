import os
import time
import uuid
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QTextEdit, QPushButton, QSplitter,
    QStackedWidget, QLabel, QInputDialog, QFileDialog, QMessageBox,
    QTextBrowser, QMenu, QStyle, QGroupBox, QFormLayout
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

    def set_input_enabled(self, enabled):
        """启用或禁用聊天输入控件。"""
        self.message_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.send_image_button.setEnabled(enabled)
        self.send_file_button.setEnabled(enabled)

        if not enabled:
            self.message_input.setPlaceholderText("好友已离线，无法发送消息。")
        else:
            self.message_input.setPlaceholderText("输入消息...")

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

    def append_system_message(self, message):
        html = f'''
            <div style="text-align: center; margin: 5px;">
                <i style="color: #888;">{message}</i>
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

    def add_system_message(self, username, message):
        """向指定用户的聊天窗口添加一条系统消息。"""
        chat_widget = self.chat_widgets.get(username)
        if chat_widget:
            chat_widget.append_system_message(message)


class MainWindow(QMainWindow):
    message_sent = pyqtSignal(str, str)
    stego_image_sent = pyqtSignal(str, str, str)
    file_sent = pyqtSignal(str, str)
    add_friend_requested = pyqtSignal(str)
    friend_selected = pyqtSignal(str)
    mode_change_requested = pyqtSignal(str, str)
    delete_friend_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()
    starred_friends_changed = pyqtSignal(dict)
    logout_requested = pyqtSignal()  # 新增: 退出登录信号

    def __init__(self, username, email, ip, parent=None):
        super().__init__(parent)
        self.username = username
        self.email = email
        self.ip = ip
        self.starred_friends = set()  # 存储特别关注的好友
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
        # 好友列表标签
        header_label = QLabel("好友列表:")
        header_layout.addWidget(header_label)
        header_layout.addStretch()  # 添加弹性空间
        refresh_button = QPushButton()
        refresh_button.setToolTip("刷新好友列表")
        refresh_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        refresh_button.setIcon(refresh_icon)
        refresh_button.setFixedSize(QSize(28,28))
        refresh_button.clicked.connect(lambda: self.refresh_requested.emit())
        header_layout.addWidget(refresh_button)

        # 设置按钮 - 现在放在主窗口的菜单栏中
        self.settings_action = QAction("设置", self)
        self.settings_action.triggered.connect(self._show_settings)

        # 创建菜单栏
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("选项")
        settings_menu.addAction(self.settings_action)

        self.logout_action = QAction("退出登录", self)
        self.logout_action.triggered.connect(self.on_logout)
        settings_menu.addAction(self.logout_action)

        # 好友列表控件

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

        # 修改好友列表的点击事件
        self.friend_list_widget.itemClicked.connect(self._on_friend_clicked)  # 新增点击事件处理

        # 主布局

        main_layout.addWidget(splitter)

    # 添加退出登录方法
    def on_logout(self):
        """处理退出登录请求"""
        reply = QMessageBox.question(self, "退出登录",
                                     "确定要退出登录吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()

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

            # 设置特别关注好友的背景色
            if username in self.starred_friends:
                item.setBackground(QColor("#ffcccc"))  # 浅红色背景

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
                # If this friend's chat is currently open, update its input state
                current_chat_widget = self._get_current_chat_widget()
                if current_chat_widget and current_chat_widget.partner_name == username:
                    is_online = friend_update_data.get("status") == "online"
                    current_chat_widget.set_input_enabled(is_online)
                break

    def set_chat_mode(self, username, mode):
        self.friend_chat_modes[username] = mode
        
        item_to_update = None
        for i in range(self.friend_list_widget.count()):
            item = self.friend_list_widget.item(i)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_data and item_data.get("username") == username:
                item_to_update = item
                break
        
        if item_to_update:
            self._update_friend_item_icon(item_to_update)

        # Generate the appropriate system message
        message = ""
        if mode == 'p2p':
            message = "P2P 连接成功！现在是直连通信。"
        elif mode == 'p2p_fail':
            message = "P2P 连接失败。将切换回服务器中继模式。"
        elif mode == 'p2p_connecting':
            message = "正在尝试建立 P2P 连接..."
        elif mode == 'cs':
            message = "已切换到 C/S (服务器中继) 模式。"
        
        # Add the message to the correct user's chat window
        if message:
            chat_widget = self.chat_widgets.get(username)
            if chat_widget:
                chat_widget.append_system_message(message)

    def _update_friend_item_icon(self, item):
        friend_data = item.data(Qt.ItemDataRole.UserRole)
        username = friend_data.get("username")
        status = friend_data.get("status", "offline")
        chat_mode = self.friend_chat_modes.get(username, 'cs')

        online_color = "#2ecc71" if status == "online" else "#95a5a6"
        p2p_color = None

        if status == "online":
            if chat_mode == 'p2p':
                p2p_color = "#3498db"
            elif chat_mode == 'p2p_connecting':
                p2p_color = "#f1c40f"
        
        item.setIcon(self._create_status_icon(online_color, p2p_color))

    def add_message_to_chat(self, sender, message, is_self=False):
        partner = self._get_current_partner_name()
        if not partner: return

        # Determine the target chat widget.
        target_username = partner if is_self else sender
        
        chat_widget = self.chat_widgets.get(target_username)
        if chat_widget:
             chat_widget.append_message(sender, message, is_self=is_self)
    
    def add_stego_image_to_chat(self, sender, image_bytes, hidden_text, is_self=False):
        partner = sender if not is_self else self._get_current_partner_name()
        if partner in self.chat_widgets:
            self.chat_widgets[partner].append_image(sender, image_bytes, hidden_text, is_self=is_self)
    
    def add_file_to_chat(self, sender, filename, file_bytes=None, is_self=False):
        partner = sender if not is_self else self._get_current_partner_name()
        if partner not in self.chat_widgets:
            self._create_chat_widget(partner)

        chat_widget = self.chat_widgets.get(partner)
        if chat_widget:
            chat_widget.append_file_info(sender, filename, file_path=self._save_received_file(filename, file_bytes), is_self=is_self)

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

    def _show_settings(self):
        settings_window = SettingsWindow(self.username, self.email, self.ip)
        settings_window.show()

    def add_system_message(self, username, message):
        """向指定用户的聊天窗口添加一条系统消息。"""
        chat_widget = self.chat_widgets.get(username)
        if chat_widget:
            chat_widget.append_system_message(message)

    def _on_friend_clicked(self, item):  # 修改为点击事件处理# 新增方法：处理好友点击事件
        if not item:
            return

        friend_data = item.data(Qt.ItemDataRole.UserRole)
        if not friend_data:
            return

        username = friend_data.get("username")
        status = friend_data.get("status", "offline")

        # 如果好友离线，直接进入聊天
        if status != "online":
            self._enter_chat(username)
            return

        # 在线好友显示菜单
        menu = QMenu()

        # 开始聊天
        chat_action = QAction("开始聊天", self)
        chat_action.triggered.connect(lambda: self._enter_chat(username))
        menu.addAction(chat_action)

        # 查看信息
        info_action = QAction("查看信息", self)
        info_action.triggered.connect(lambda: self._show_friend_info(friend_data))
        menu.addAction(info_action)

        # 设置/取消特别关注
        star_text = "取消特别关注" if username in self.starred_friends else "设为特别关注"
        star_action = QAction(star_text, self)
        star_action.triggered.connect(lambda: self._toggle_star_friend(username))
        menu.addAction(star_action)

        # 显示菜单
        pos = self.friend_list_widget.viewport().mapFromGlobal(self.cursor().pos())
        menu.exec(self.friend_list_widget.viewport().mapToGlobal(pos))

    def _enter_chat(self, username):
        self.friend_selected.emit(username)
        if username not in self.chat_widgets:
            self._create_chat_widget(username)
        self.chat_stack.setCurrentWidget(self.chat_widgets[username])

    def _show_friend_info(self, friend_data):
        username = friend_data.get("username")
        ip = friend_data.get("ip", "未知")
        port = friend_data.get("port", "未知")
        status = "在线" if friend_data.get("status") == "online" else "离线"

        info = f"用户名: {username}\nIP地址: {ip}\n端口: {port}\n状态: {status}"
        QMessageBox.information(self, "好友信息", info)

    def _toggle_star_friend(self, username):
        if username in self.starred_friends:
            self.starred_friends.remove(username)
        else:
            self.starred_friends.add(username)

        # 更新UI
        self.update_friend_list([item.data(Qt.ItemDataRole.UserRole)
                                 for i in range(self.friend_list_widget.count())
                                 for item in [self.friend_list_widget.item(i)]])

        # 发射信号通知其他组件
        self.starred_friends_changed.emit({"username": username, "starred": username in self.starred_friends})

    def _get_current_chat_widget(self):
        current_widget = self.chat_stack.currentWidget()
        if isinstance(current_widget, ChatWidget):
            return current_widget
        return None

class SettingsWindow(QWidget):
    def __init__(self, username, email, ip, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("设置")
        self.setGeometry(300, 300, 400, 300)

        # 保持对窗口的引用，防止被垃圾回收
        self._window = None

        layout = QVBoxLayout()

        # 账号信息
        account_group = QGroupBox("账号信息")
        account_layout = QFormLayout()
        account_layout.addRow("用户名:", QLabel(username))
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)

        # 开发团队
        team_group = QGroupBox("开发团队")
        team_layout = QVBoxLayout()
        team_layout.addWidget(QLabel("项目名称: 安全IM"))
        team_layout.addWidget(QLabel("开发时间: 2025年7月1日"))
        team_layout.addWidget(QLabel("团队成员: 杨正启, 米天鸿, 陈泽同，苏淇"))
        team_group.setLayout(team_layout)
        layout.addWidget(team_group)

        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout)

    def show(self):
        # 确保窗口不会被垃圾回收
        self._window = self
        super().show()