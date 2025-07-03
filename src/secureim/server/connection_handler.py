import json
from .state import online_users
from . import request_handler as handler
from . import database

def send_to_client(client_socket, data):
    """编码并安全地向客户端发送数据。"""
    try:
        client_socket.sendall((json.dumps(data) + '\n').encode('utf-8'))
    except (BrokenPipeError, ConnectionResetError):
        print(f"错误: 客户端套接字已关闭。无法发送消息。")
    except Exception as e:
        print(f"在 send_to_client 中发生意外错误: {e}")

def broadcast_status_update(username, status):
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
            send_to_client(friend_socket, message)


def handle_client_connection(client_socket, address):
    """处理与单个客户端的通信。"""
    print(f"来自 {address} 的新连接")
    current_user = None
    
    # 创建一个包装好的发送函数，以便传递给请求处理器
    send_func = lambda data: send_to_client(client_socket, data)

    try:
        for line in client_socket.makefile(encoding='utf-8'):
            try:
                data = json.loads(line)
                msg_type = data.get("type")
                payload = data.get("payload", {})

                if msg_type == "register":
                    handler.handle_register(payload, send_func)

                elif msg_type == "request_verification_code":
                    handler.handle_request_verification_code(payload, send_func)

                elif msg_type == "login":
                    user = handler.handle_login(payload, send_func, client_socket, address)
                    if user:
                        current_user = user
                        broadcast_status_update(current_user, "online")

                # --- 以下操作需要用户先登录 ---
                elif not current_user:
                    send_func({"type": "response", "status": "error", "message": "未登录"})
                    continue

                elif msg_type == "add_friend":
                    handler.handle_add_friend(payload, current_user, send_func)

                elif msg_type == "delete_friend":
                    handler.handle_delete_friend(payload, current_user, send_func)
                    # 通知被删除的好友
                    friend_username = payload.get('friend_username')
                    friend_socket = online_users.get_socket(friend_username)
                    if friend_socket:
                         send_to_client(friend_socket, {"type": "friend_removed", "payload": {"username": current_user}})

                elif msg_type == "get_friends":
                    handler.handle_get_friends(current_user, send_func)

                elif msg_type == "get_public_key":
                    handler.handle_get_public_key(payload, send_func)

                elif msg_type in ["relay_message", "relay_session_key"]:
                    to_user = payload.get('to')
                    target_socket = online_users.get_socket(to_user)
                    if target_socket:
                        log_msg_type = "会话密钥" if msg_type == "relay_session_key" else "消息"
                        print(f"[C/S 中继] 正在从中继 '{current_user}' 到 '{to_user}' 的{log_msg_type}。")
                        
                        relay_payload = {"from": current_user, **payload}
                        del relay_payload['to']
                        relay_type = "receive_message" if msg_type == "relay_message" else "receive_session_key"
                        relay_message = {"type": relay_type, "payload": relay_payload}
                        send_to_client(target_socket, relay_message)
                    else:
                        send_func({"type": "response", "status": "error", "message": f"用户 '{to_user}' 不在线。"})

            except json.JSONDecodeError:
                print(f"从 {address} 收到无效的JSON")
            except Exception as e:
                print(f"处理客户端 {address} 时发生错误: {e}")

    except (ConnectionResetError, BrokenPipeError):
        print(f"客户端 {address} 意外断开连接。")
    finally:
        if current_user:
            print(f"用户 '{current_user}' 已断开连接。")
            online_users.remove_user(current_user)
            broadcast_status_update(current_user, "offline")
        client_socket.close()
        print(f"与 {address} 的连接已关闭。") 