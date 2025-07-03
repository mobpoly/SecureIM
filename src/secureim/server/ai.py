import threading
import time
import requests
import json
from . import server_crypto  # 服务器端加解密模块
from .state import ai_session_keys

# 硬编码的OpenAI兼容API配置
API_URL = "http://127.0.0.1:1234/v1/chat/completions"
API_KEY = "key"                # 替换为实际API密钥
MODEL = "model"            # 替换为实际模型

# 用于存储每个用户的AI响应生成状态
ai_response_states = {}


def handle_ai_message(username, encrypted_message, send_func):
    """
    处理用户发送给AI的消息
    """
    # 获取该用户的AES密钥
    aes_key = ai_session_keys.get_key(username)
    if not aes_key:
        response = {"type": "response", "status": "error", "message": "未建立安全会话"}
        send_func(response)
        return

    # 解密消息
    try:
        decrypted_data = server_crypto.decrypt_with_aes(aes_key, encrypted_message)
        if decrypted_data is None:
            response = {"type": "response", "status": "error", "message": "解密失败"}
            send_func(response)
            return

        # 提取消息内容
        message_content = decrypted_data.decode('utf-8')
        print(f"用户 {username} 向AI发送消息: {message_content}")

        # 启动新线程处理AI请求
        thread = threading.Thread(
            target=process_ai_request,
            args=(username, message_content, aes_key, send_func)
        )
        thread.daemon = True
        thread.start()

    except Exception as e:
        print(f"处理AI消息时出错: {e}")
        response = {"type": "response", "status": "error", "message": "处理消息失败"}
        send_func(response)


def process_ai_request(username, message, aes_key, send_func):
    """
    处理AI请求并在后台生成响应
    """
    # 存储状态
    ai_response_states[username] = {
        "generating": True,
        "last_update": time.time()
    }

    # 发送等待消息的线程
    def send_waiting_messages():
        while ai_response_states.get(username, {}).get("generating", False):
            # 每5秒发送一次等待消息
            time.sleep(5)

            # 检查是否还在生成中
            if not ai_response_states.get(username, {}).get("generating", False):
                break

            # 加密等待消息
            waiting_msg = "正在生成内容，请等待..."
            encrypted_waiting = server_crypto.encrypt_with_aes(aes_key, waiting_msg.encode('utf-8'))

            # 构造AI响应
            ai_response = {
                "type": "receive_message",
                "payload": {
                    "from": "ai",
                    "content": encrypted_waiting,
                    "timestamp": time.time()
                }
            }

            # 发送等待消息
            send_func(ai_response)

    # 启动等待消息线程
    waiting_thread = threading.Thread(target=send_waiting_messages)
    waiting_thread.daemon = True
    waiting_thread.start()

    try:
        # 调用大模型API
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": MODEL,
            "messages": [{"role": "user", "content": message}],
            "stream": False
        }

        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()

        # 解析响应
        result = response.json()
        ai_content = result['choices'][0]['message']['content']
        print(f"AI生成响应给 {username}: {ai_content[:50]}...")

        # 加密AI响应
        encrypted_response = server_crypto.encrypt_with_aes(aes_key, ai_content.encode('utf-8'))

        # 构造AI响应
        ai_response = {
            "type": "receive_message",
            "payload": {
                "from": "ai",
                "content": encrypted_response,
                "timestamp": time.time()
            }
        }

        # 发送最终响应
        send_func(ai_response)

    except Exception as e:
        print(f"调用AI API时出错: {e}")
        error_msg = "AI服务暂时不可用，请稍后再试"
        encrypted_error = server_crypto.encrypt_with_aes(aes_key, error_msg.encode('utf-8'))

        error_response = {
            "type": "receive_message",
            "payload": {
                "from": "ai",
                "content": encrypted_error,
                "timestamp": time.time()
            }
        }

        send_func(error_response)

    finally:
        # 清理状态
        if username in ai_response_states:
            ai_response_states[username]["generating"] = False