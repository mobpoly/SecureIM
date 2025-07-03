import socket
import threading
from . import database
from .connection_handler import handle_client_connection

HOST = '0.0.0.0'
PORT = 12345

def start_server():
    """
    初始化并启动安全IM服务器。
    """
    # 1. 初始化数据库
    database.create_tables()
    
    # 2. 创建并绑定服务器套接字
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"服务器正在监听 {HOST}:{PORT}")

    # 3. 循环接受客户端连接
    try:
        while True:
            client_socket, address = server_socket.accept()
            # 为每个客户端创建一个新线程来处理
            thread = threading.Thread(
                target=handle_client_connection, 
                args=(client_socket, address)
            )
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n服务器正在关闭。")
    finally:
        server_socket.close()

if __name__ == '__main__':
    start_server() 