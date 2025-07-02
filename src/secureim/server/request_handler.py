from . import database
from .state import online_users

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
    success = database.add_user(payload['username'], payload['password'], payload.get('email'), payload['public_key'])
    message = "注册成功" if success else "用户名已存在。"
    status = "success" if success else "error"
    response = {"type": "response", "action": "register", "status": status, "message": message}
    send_func(response)
    return None # 注册后不立即登录

def handle_login(payload, send_func, client_socket, address):
    if database.check_credentials(payload['username'], payload['password']):
        current_user = payload['username']
        online_users.add_user(current_user, client_socket, address)
        response = {"type": "response", "action": "login", "status": "success", "message": "登录成功"}
        send_func(response)
        print(f"用户 '{current_user}' 已登录。")
        broadcast_status_update(current_user, "online", send_func)
        return current_user
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
    response = {"type": "response", "action": "delete_friend", "status": status, "message": message}
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

    for friend in friends:
        friend_socket = online_users.get_socket(friend)
        if friend_socket:
            # send_to_specific_client(friend_socket, message)
            pass # 实际逻辑在 connection_handler 中 