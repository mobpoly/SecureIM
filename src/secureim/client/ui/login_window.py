import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QMessageBox, QStackedWidget, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt

class LoginWindow(QWidget):
    # 用于连接到主应用控制器的信号
    login_requested = pyqtSignal(str, str)
    register_requested = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("安全IM - 登录")
        self.setFixedSize(350, 250)

        # 主布局
        self.stacked_widget = QStackedWidget(self)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.stacked_widget)
        
        # 创建页面
        self.login_page = QWidget()
        self.register_page = QWidget()
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.register_page)
        
        # 为两个页面设置UI
        self._setup_login_ui()
        self._setup_register_ui()

        self.setLayout(main_layout)

    def _setup_login_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.login_username_input = QLineEdit(self)
        self.login_username_input.setPlaceholderText("输入您的用户名或邮箱")
        self.login_password_input = QLineEdit(self)
        self.login_password_input.setPlaceholderText("输入您的密码")
        self.login_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form_layout.addRow(QLabel("用户名:"), self.login_username_input)
        form_layout.addRow(QLabel("密码:"), self.login_password_input)
        
        login_button = QPushButton("登录", self)
        login_button.clicked.connect(self.on_login)

        switch_to_register_button = QPushButton("没有账户？点击注册", self)
        switch_to_register_button.setObjectName("linkButton") # 用于样式设置
        switch_to_register_button.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.register_page))

        layout.addLayout(form_layout)
        layout.addWidget(login_button)
        layout.addWidget(switch_to_register_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.login_page.setLayout(layout)

    def _setup_register_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.register_username_input = QLineEdit(self)
        self.register_username_input.setPlaceholderText("选择一个用户名")
        self.register_password_input = QLineEdit(self)
        self.register_password_input.setPlaceholderText("选择一个密码")
        self.register_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.register_email_input = QLineEdit(self)
        self.register_email_input.setPlaceholderText("输入您的邮箱 (必填)")
        
        form_layout.addRow(QLabel("用户名:"), self.register_username_input)
        form_layout.addRow(QLabel("密码:"), self.register_password_input)
        form_layout.addRow(QLabel("邮箱:"), self.register_email_input)

        register_button = QPushButton("注册", self)
        register_button.clicked.connect(self.on_register)
        
        switch_to_login_button = QPushButton("已有账户？点击登录", self)
        switch_to_login_button.setObjectName("linkButton")
        switch_to_login_button.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.login_page))

        layout.addLayout(form_layout)
        layout.addWidget(register_button)
        layout.addWidget(switch_to_login_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.register_page.setLayout(layout)

    def on_login(self):
        username = self.login_username_input.text().strip()
        password = self.login_password_input.text()
        if username and password:
            self.login_requested.emit(username, password)
        else:
            self.show_error("请输入用户名和密码。")

    def on_register(self):
        username = self.register_username_input.text().strip()
        password = self.register_password_input.text()
        email = self.register_email_input.text().strip()

        # 客户端验证
        if not all([username, password, email]):
            self.show_error("用户名、密码和邮箱都不能为空。")
            return
        
        # 邮箱格式验证
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            self.show_error("请输入有效的邮箱地址。")
            return

        # 密码复杂度验证
        if len(password) < 8:
            self.show_error("密码长度必须至少为8位。")
            return
        
        has_letter = any(c.isalpha() for c in password)
        has_digit = any(c.isdigit() for c in password)

        if not (has_letter and has_digit):
            self.show_error("密码必须包含字母和数字的组合。")
            return

        self.register_requested.emit(username, password, email)
            
    def show_error(self, message):
        QMessageBox.warning(self, "错误", message)

    def show_info(self, message):
        QMessageBox.information(self, "提示", message) 