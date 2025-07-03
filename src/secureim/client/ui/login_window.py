import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QMessageBox, QStackedWidget, QLabel, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QDialog


class ForgotPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("修改密码")
        self.setFixedSize(350, 300)

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.identifier_input = QLineEdit(self)
        self.identifier_input.setPlaceholderText("输入您的邮箱")
        self.new_password_input = QLineEdit(self)
        self.new_password_input.setPlaceholderText("输入新密码")
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.verification_code_input = QLineEdit(self)
        self.verification_code_input.setPlaceholderText("输入验证码")

        verification_layout = QHBoxLayout()
        self.get_code_button = QPushButton("获取验证码")
        verification_layout.addWidget(self.verification_code_input)
        verification_layout.addWidget(self.get_code_button)

        form_layout.addRow(QLabel("邮箱:"), self.identifier_input)
        form_layout.addRow(QLabel("新密码:"), self.new_password_input)
        form_layout.addRow(QLabel("验证码:"), verification_layout)

        button_layout = QHBoxLayout()
        self.change_button = QPushButton("修改密码")
        self.cancel_button = QPushButton("取消")
        button_layout.addWidget(self.change_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(form_layout)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        # 连接信号
        self.get_code_button.clicked.connect(self.on_get_code)
        self.change_button.clicked.connect(self.on_change_password)
        self.cancel_button.clicked.connect(self.reject)

    def on_get_code(self):
        email = self.identifier_input.text().strip()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            QMessageBox.warning(self, "错误", "请输入有效的邮箱地址")
            return
        self.parent().verification_code_requested.emit(email)


    def on_change_password(self):
        identifier = self.identifier_input.text().strip()
        new_password = self.new_password_input.text()
        verification_code = self.verification_code_input.text().strip()

        if not all([identifier, new_password, verification_code]):
            QMessageBox.warning(self, "错误", "所有字段均为必填项")
            return

        reply = QMessageBox.question(
            self,
            "确认修改",
            "确定要修改密码吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.parent().change_password_requested.emit(identifier, new_password, verification_code)
            self.accept()

class LoginWindow(QWidget):
    # 用于连接到主应用控制器的信号
    login_requested = pyqtSignal(str, str)
    register_requested = pyqtSignal(str, str, str, str)  # 修改：增加verification_code参数
    verification_code_requested = pyqtSignal(str)  # 参数：email
    change_password_requested = pyqtSignal(str, str, str)  # identifier, new_password, verification_code
    def __init__(self, parent=None):
        super().__init__(parent)

        # 新增：验证码相关状态
        self.is_email_verified = False
        self.verification_code = ""

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

    def show_forgot_password_dialog(self):
        dialog = ForgotPasswordDialog(self)
        dialog.exec()

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
        switch_to_register_button.setObjectName("linkButton")  # 用于样式设置
        switch_to_register_button.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.register_page))
        forgot_password_button = QPushButton("忘记密码？点击修改", self)
        forgot_password_button.setObjectName("linkButton")
        forgot_password_button.clicked.connect(self.show_forgot_password_dialog)

        # 创建链接按钮的垂直布局，并添加两个按钮
        links_layout = QVBoxLayout()
        links_layout.addWidget(switch_to_register_button, alignment=Qt.AlignmentFlag.AlignCenter)
        links_layout.addWidget(forgot_password_button, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(form_layout)
        layout.addWidget(login_button)
        layout.addLayout(links_layout)  # 添加链接按钮布局
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

        # 新增：验证码相关UI
        verification_layout = QHBoxLayout()
        self.verification_code_input = QLineEdit(self)
        self.verification_code_input.setPlaceholderText("输入验证码")
        self.get_code_button = QPushButton("获取验证码")
        self.get_code_button.clicked.connect(self.on_get_verification_code)
        verification_layout.addWidget(self.verification_code_input)
        verification_layout.addWidget(self.get_code_button)

        form_layout.addRow(QLabel("验证码:"), verification_layout)

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
        verification_code = self.verification_code_input.text().strip()  # 新增

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

        # 新增：验证码验证
        if not verification_code:
            self.show_error("请输入验证码。")
            return

        # 修改：发送信号时增加验证码参数
        self.register_requested.emit(username, password, email, verification_code)
            
    def show_error(self, message):
        QMessageBox.warning(self, "错误", message)

    def show_info(self, message):
        QMessageBox.information(self, "提示", message)

    def on_get_verification_code(self):
        """获取验证码"""
        email = self.register_email_input.text().strip()

        # 邮箱格式验证
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            self.show_error("请输入有效的邮箱地址。")
            return

        self.verification_code_requested.emit(email)

        # 防止重复点击，设置60秒倒计时
        self.get_code_button.setEnabled(False)
        self.get_code_button.setText("已发送")

        # 可选：添加倒计时逻辑
        from PyQt6.QtCore import QTimer
        self.timer = QTimer()
        self.countdown = 60
        self.timer.timeout.connect(self._update_countdown)
        self.timer.start(1000)

    def _update_countdown(self):
        """倒计时更新"""
        self.countdown -= 1
        if self.countdown > 0:
            self.get_code_button.setText(f"重新获取({self.countdown}s)")
        else:
            self.get_code_button.setText("获取验证码")
            self.get_code_button.setEnabled(True)
            self.timer.stop()

    def show_verification_code_result(self, message):
        """显示验证码发送结果"""
        self.show_info(message)