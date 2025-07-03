import random
import re
import smtplib
import string
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


from . import database
from .state import online_users, verification_codes

# 邮件服务器配置 - 如果sender_email为空，则使用模拟邮箱
EMAIL_CONFIG = {
    'smtp_server': 'smtp.qq.com',
    'smtp_port': 587,
    'sender_email': '',  # 留空则使用模拟邮箱，填写则使用真实SMTP
    'sender_password': '',  # 邮箱授权码
    'sender_name': 'SecureIM验证服务'
}

def send_to_client(client_socket, data):
    """
    这是一个辅助函数，但由于 request_handler 中的几乎每个函数都需要它，
    所以在这里定义以避免循环导入。
    实际的 send_to_client 在 connection_handler 中。
    更好的设计是有一个 "client" 对象，包含套接字和发送方法。
    为简单起见，我们暂时从 connection_handler 传递套接字和 send_func。
    """
    raise NotImplementedError("This function should be passed from the connection handler.")


def handle_register(payload, send_func):
    username = payload.get('username')
    password = payload.get('password')
    email = payload.get('email')
    public_key = payload.get('public_key')
    verification_code = payload.get('verification_code')  # 新增

    # --- 服务器端验证 ---
    if not all([username, password, email, public_key, verification_code]):  # 修改：增加验证码检查
        response = {"type": "response", "action": "register", "status": "error", "message": "所有字段均为必填项。"}
        send_func(response)
        return None

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        response = {"type": "response", "action": "register", "status": "error", "message": "邮箱格式无效。"}
        send_func(response)
        return None

    if len(password) < 8:
        response = {"type": "response", "action": "register", "status": "error", "message": "密码长度必须至少为8位。"}
        send_func(response)
        return None

    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)

    if not (has_letter and has_digit):
        response = {"type": "response", "action": "register", "status": "error",
                    "message": "密码必须包含字母和数字的组合。"}
        send_func(response)
        return None

    # 新增：验证码验证
    if not verification_codes.verify_code(email, verification_code):
        response = {"type": "response", "action": "register", "status": "error", "message": "验证码错误或已过期。"}
        send_func(response)
        return None
    # --- 验证结束 ---

    success, message = database.add_user(username, password, email, public_key)
    status = "success" if success else "error"
    response = {"type": "response", "action": "register", "status": status, "message": message}
    send_func(response)
    return None

def handle_login(payload, send_func, client_socket, address):
    login_identifier = payload.get('username') # May be username or email
    password = payload.get('password')
    
    username = database.check_credentials(login_identifier, password)
    if username:
        online_users.add_user(username, client_socket, address)
        # 获取用户的完整信息
        user_email = database.get_user_email(username)
        user_ip = address[0] if address else "未知"
        response = {
            "type": "response",
            "action": "login",
            "status": "success",
            "message": "登录成功",
            "username": username,
            "user_info": {  # 新增：用户信息
                "email": user_email or "未知",
                "ip": user_ip
            }
        }
        send_func(response)
        print(f"用户 '{username}' 已登录。")
        broadcast_status_update(username, "online", send_func)
        return username
    else:
        response = {"type": "response", "action": "login", "status": "error", "message": "凭据无效"}
        send_func(response)
        return None

def handle_add_friend(payload, current_user, send_func):
    friend_username = payload.get('friend_username')
    if database.get_user_id(friend_username): # 检查好友是否存在
        success = database.add_friend(current_user, friend_username)
        message = "好友添加成功。" if success else "好友关系已存在或添加失败。"
        status = "success" if success else "error"
    else:
        status = "error"
        message = "用户不存在。"
    response = {"type": "response", "action": "add_friend", "status": status, "message": message}
    send_func(response)

def handle_delete_friend(payload, current_user, send_func):
    friend_username = payload.get('friend_username')
    success = database.delete_friend(current_user, friend_username)
    message = "好友已删除。" if success else "删除好友失败。"
    status = "success" if success else "error"
    response = {"type": "response", "action": "delete_friend", "status": status, "message": message, "payload": {"friend_username": friend_username}}
    send_func(response)
    
    # 如果成功且对方在线，通知对方刷新列表
    if success:
        friend_socket = online_users.get_socket(friend_username)
        if friend_socket:
            notify = {"type": "friend_removed", "payload": {"username": current_user}}
            # 这里需要一种方法来向特定用户发送消息
            # 暂时无法直接调用，需要在 connection_handler 中完成
            # send_to_specific_client(friend_socket, notify)
            pass # 实际逻辑在 connection_handler 中

def handle_get_friends(current_user, send_func):
    all_friends = database.get_friends(current_user)
    friend_data = []
    for f_user in all_friends:
        friend_info = online_users.get_user_info(f_user)
        if friend_info:
            friend_data.append({
                "username": f_user,
                "status": "online",
                "ip": friend_info['ip'],
                "port": friend_info['port']
            })
        else:
            friend_data.append({"username": f_user, "status": "offline"})
    response = {"type": "all_friends_list", "payload": friend_data}
    send_func(response)

def handle_get_public_key(payload, send_func):
    username = payload.get('username')
    public_key = database.get_user_public_key(username)
    if public_key:
        response = {"type": "public_key_response", "payload": {"username": username, "public_key": public_key}}
    else:
        response = {"type": "response", "status": "error", "message": "用户未找到"}
    send_func(response)

def handle_relay(msg_type, payload, current_user, send_func):
    to_user = payload.get('to')
    target_socket = online_users.get_socket(to_user)
    if target_socket:
        relay_payload = {"from": current_user, **payload}
        del relay_payload['to']
        
        relay_type = "receive_message"
        if msg_type == "relay_session_key":
            relay_type = "receive_session_key"
            
        relay_message = {"type": relay_type, "payload": relay_payload}
        # 需要一个 send_to_specific_client 函数
        # send_to_specific_client(target_socket, relay_message)
    else:
        response = {"type": "response", "status": "error", "message": f"用户 '{to_user}' 不在线。"}
        send_func(response)


def handle_mode_change_request(payload, current_user, send_func):
    """
    处理模式切换请求
    payload 应包含: target_username, requested_mode, request_id
    """
    target_username = payload.get('target_username')
    requested_mode = payload.get('requested_mode')
    request_id = payload.get('request_id')

    # 验证参数
    if not all([target_username, requested_mode, request_id]):
        response = {
            "type": "response",
            "status": "error",
            "message": "模式切换请求参数不完整"
        }
        send_func(response)
        return

    # 验证目标用户是否为好友
    friends = database.get_friends(current_user)
    if target_username not in friends:
        response = {
            "type": "response",
            "status": "error",
            "message": "只能向好友发送模式切换请求"
        }
        send_func(response)
        return

    # 检查目标用户是否在线
    target_socket = online_users.get_socket(target_username)
    if not target_socket:
        response = {
            "type": "response",
            "status": "error",
            "message": f"用户 '{target_username}' 不在线"
        }
        send_func(response)
        return

    # 转发请求给目标用户
    forward_message = {
        "type": "mode_change_request",
        "payload": {
            "from_username": current_user,
            "requested_mode": requested_mode,
            "request_id": request_id
        }
    }

    try:
        from .connection_handler import send_to_client
        send_to_client(target_socket, forward_message)
        print(f"[模式切换] '{current_user}' 向 '{target_username}' 请求切换到 '{requested_mode}' 模式")

        # 向请求方发送确认
        response = {
            "type": "response",
            "status": "success",
            "message": "模式切换请求已发送"
        }
        send_func(response)

    except Exception as e:
        print(f"转发模式切换请求时发生错误: {e}")
        response = {
            "type": "response",
            "status": "error",
            "message": "发送模式切换请求失败"
        }
        send_func(response)


def handle_mode_change_notification(payload, current_user, send_func):
    """
    处理模式变更通知
    payload 应包含: target_username, new_mode
    """
    target_username = payload.get('target_username')
    new_mode = payload.get('new_mode')

    # 验证参数
    if not all([target_username, new_mode]):
        response = {
            "type": "response",
            "status": "error",
            "message": "模式变更通知参数不完整"
        }
        send_func(response)
        return

    # 验证目标用户是否为好友
    friends = database.get_friends(current_user)
    if target_username not in friends:
        response = {
            "type": "response",
            "status": "error",
            "message": "只能向好友发送模式变更通知"
        }
        send_func(response)
        return

    # 检查目标用户是否在线
    target_socket = online_users.get_socket(target_username)
    if not target_socket:
        # 如果目标用户不在线，不报错，只是记录日志
        print(f"[模式切换] 无法通知离线用户 '{target_username}' 模式变更为 '{new_mode}'")
        response = {
            "type": "response",
            "status": "success",
            "message": "目标用户不在线，模式变更通知已记录"
        }
        send_func(response)
        return

    # 转发通知给目标用户
    forward_message = {
        "type": "mode_change_notification",
        "payload": {
            "from_username": current_user,
            "new_mode": new_mode
        }
    }

    try:
        from .connection_handler import send_to_client
        send_to_client(target_socket, forward_message)
        print(f"[模式切换] '{current_user}' 通知 '{target_username}' 模式已变更为 '{new_mode}'")

        # 向通知方发送确认
        response = {
            "type": "response",
            "status": "success",
            "message": "模式变更通知已发送"
        }
        send_func(response)

    except Exception as e:
        print(f"转发模式变更通知时发生错误: {e}")
        response = {
            "type": "response",
            "status": "error",
            "message": "发送模式变更通知失败"
        }
        send_func(response)


def handle_mode_change_response(payload, current_user, send_func):
    """
    处理模式切换响应
    payload 应包含: target_username, request_id, accepted, requested_mode
    """
    target_username = payload.get('target_username')
    request_id = payload.get('request_id')
    accepted = payload.get('accepted', False)
    requested_mode = payload.get('requested_mode')

    # 验证参数
    if not all([target_username, request_id is not None, requested_mode]):
        response = {
            "type": "response",
            "status": "error",
            "message": "模式切换响应参数不完整"
        }
        send_func(response)
        return

    # 检查目标用户是否在线
    target_socket = online_users.get_socket(target_username)
    if not target_socket:
        response = {
            "type": "response",
            "status": "error",
            "message": f"用户 '{target_username}' 不在线"
        }
        send_func(response)
        return

    # 转发响应给请求方
    forward_message = {
        "type": "mode_change_response",
        "payload": {
            "from_username": current_user,
            "request_id": request_id,
            "accepted": accepted,
            "requested_mode": requested_mode
        }
    }

    try:
        from .connection_handler import send_to_client
        send_to_client(target_socket, forward_message)

        action = "同意" if accepted else "拒绝"
        print(f"[模式切换] '{current_user}' {action}了 '{target_username}' 的 '{requested_mode}' 模式切换请求")

        # 向响应方发送确认
        response = {
            "type": "response",
            "status": "success",
            "message": "模式切换响应已发送"
        }
        send_func(response)

    except Exception as e:
        print(f"转发模式切换响应时发生错误: {e}")
        response = {
            "type": "response",
            "status": "error",
            "message": "发送模式切换响应失败"
        }
        send_func(response)


def broadcast_status_update(username, status, send_func_for_user):
    """通知所有好友用户的状态变更。"""
    friends = database.get_friends(username)
    payload = {"username": username, "status": status}

    if status == "online":
        user_info = online_users.get_user_info(username)
        if user_info:
            payload["ip"] = user_info['ip']
            payload["port"] = user_info['port']

    message = {"type": "friend_status_update", "payload": payload}

    return message


def handle_request_verification_code(payload, send_func):
    """处理验证码请求"""
    email = payload.get('email')

    if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        response = {"type": "response", "action": "request_verification_code",
                    "status": "error", "message": "邮箱格式无效。"}
        send_func(response)
        return

    # 生成6位数字验证码
    code = ''.join(random.choices(string.digits, k=6))
    verification_codes.store_code(email, code)

    # 判断是否使用真实SMTP发送
    sender_email = EMAIL_CONFIG.get('sender_email', '').strip()

    if sender_email:  # 如果配置了发送方邮箱，使用真实SMTP
        success, error_msg = send_verification_email(email, code)
        if success:
            response = {"type": "response", "action": "request_verification_code",
                        "status": "success", "message": "验证码已发送到您的邮箱，请查收。"}
        else:
            # 如果邮件发送失败，从存储中删除验证码
            verification_codes._codes.pop(email, None)
            response = {"type": "response", "action": "request_verification_code",
                        "status": "error", "message": f"验证码发送失败：{error_msg or '邮件服务异常，请稍后重试。'}"}
    else:
        # TODO: 实际发送邮件的逻辑，这里仅模拟
        print(f"[验证码] 发送到 {email}: {code}")  # 开发阶段在控制台显示
        response = {"type": "response", "action": "request_verification_code",
                    "status": "success", "message": "验证码已发送到您的邮箱（开发模式：请查看服务器控制台）。"}
    send_func(response)


def send_verification_email(recipient_email, verification_code):
    """
    发送验证码邮件

    Args:
        recipient_email (str): 收件人邮箱
        verification_code (str): 验证码

    Returns:
        bool: 发送成功返回True，失败返回False
        str: 错误信息（如果发送失败）
    """
    try:
        # 创建邮件对象
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = recipient_email
        subject = 'SecureIM 邮箱验证码'
        msg['Subject'] = Header(subject, 'utf-8')

        # 邮件正文
        email_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #0078d4; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
        .verification-code {{ background-color: #e7f3ff; border: 2px dashed #0078d4; padding: 15px; text-align: center; margin: 20px 0; font-size: 24px; font-weight: bold; color: #0078d4; }}
        .warning {{ color: #d73502; font-size: 14px; margin-top: 20px; }}
        .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SecureIM 邮箱验证</h1>
        </div>
        <div class="content">
            <h2>您好！</h2>
            <p>您正在注册 SecureIM 账户，验证码为：</p>
            <div class="verification-code">{verification_code}</div>
            <p>验证码有效期为 <strong>5分钟</strong>，请及时使用。</p>
            <div class="warning">
                <p><strong>安全提醒：</strong></p>
                <ul>
                    <li>请勿将验证码告诉他人</li>
                    <li>如果您没有请求此验证码，请忽略此邮件</li>
                    <li>此邮件由系统自动发送，请勿回复</li>
                </ul>
            </div>
        </div>
        <div class="footer">
            <p>© 2025 SecureIM. 保护您的通信安全。</p>
        </div>
    </div>
</body>
</html>
        """

        # 添加HTML正文
        msg.attach(MIMEText(email_body, 'html', 'utf-8'))

        # 连接SMTP服务器并发送邮件
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()  # 启用TLS加密
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])

        # 发送邮件
        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG['sender_email'], recipient_email, text)
        server.quit()

        print(f"✅ 验证码邮件已成功发送到: {recipient_email}")
        return True, None

    except smtplib.SMTPAuthenticationError:
        error_msg = "邮箱认证失败，请检查发送方邮箱配置"
        print(f"❌ SMTP认证错误: {error_msg}")
        return False, error_msg

    except smtplib.SMTPRecipientsRefused:
        error_msg = "收件人邮箱地址无效"
        print(f"❌ 收件人邮箱被拒绝: {error_msg}")
        return False, error_msg

    except smtplib.SMTPException as e:
        error_msg = f"SMTP服务异常: {str(e)}"
        print(f"❌ SMTP异常: {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"发送邮件时发生未知错误: {str(e)}"
        print(f"❌ 未知错误: {error_msg}")
        return False, error_msg


def handle_get_user_info(current_user, send_func, address):
    """处理获取用户信息请求"""
    # 获取用户的邮箱
    user_email = database.get_user_email(current_user)

    # 获取用户的IP地址（从连接地址中获取）
    user_ip = address[0] if address else "未知"
    print(f"[DEBUG] 处理用户信息请求: {current_user}, 邮箱={user_email}, IP={user_ip}")

    response = {
        "type": "user_info",
        "payload": {
            "username": current_user,
            "email": user_email or "未知",
            "ip": user_ip
        }
    }
    send_func(response)