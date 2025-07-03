import socket
import threading
import json
import time
from PyQt6.QtCore import QObject, pyqtSignal

class Networking(QObject):
    connection_failed_signal = pyqtSignal()
    server_message_received_signal = pyqtSignal(dict)
    p2p_message_received_signal = pyqtSignal(dict)

    def __init__(self, server_host, server_port, p2p_port, parent=None):
        super().__init__(parent)
        self.server_host = server_host
        self.server_port = server_port
        self.p2p_port = p2p_port
        self._socket = None
        self._p2p_socket = None
        self._is_listening = False

    def connect_to_server(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self.server_host, self.server_port))
            self._file = self._socket.makefile('r', encoding='utf-8')
            self.start_listening()
            return True
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            print(f"错误: 无法连接到服务器 {self.server_host}:{self.server_port}. {e}")
            self.connection_failed_signal.emit()
            return False

    def setup_p2p_listener(self):
        try:
            self._p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._p2p_socket.bind(('', self.p2p_port))
            p2p_thread = threading.Thread(target=self._listen_for_p2p_messages)
            p2p_thread.daemon = True
            p2p_thread.start()
            print(f"P2P监听器已在UDP端口 {self.p2p_port} 上启动")
        except Exception as e:
            print(f"设置P2P监听器时出错: {e}")

    def send_request(self, data, is_p2p=False, recipient_addr=None):
        if is_p2p:
            if not self._p2p_socket or not recipient_addr:
                print(f"错误: P2P套接字或接收方地址不可用。")
                return
            try:
                self._p2p_socket.sendto((json.dumps(data) + '\n').encode('utf-8'), recipient_addr)
            except Exception as e:
                print(f"发送P2P数据时出错: {e}")
        else:
            if not self._socket:
                print("错误: 未连接到服务器。")
                return
            try:
                self._socket.sendall((json.dumps(data) + '\n').encode('utf-8'))
            except (BrokenPipeError, ConnectionResetError) as e:
                print(f"发送数据时出错，连接已断开: {e}")
                self.connection_failed_signal.emit()

    def start_listening(self):
        self._is_listening = True
        self._listener_thread = threading.Thread(target=self._listen_for_server_messages)
        self._listener_thread.daemon = True
        self._listener_thread.start()

    def _listen_for_p2p_messages(self):
        while self._is_listening:
            try:
                data, addr = self._p2p_socket.recvfrom(8192)
                message = json.loads(data.decode('utf-8').strip())
                self.p2p_message_received_signal.emit({"data": message, "addr": addr})
            except OSError as e:
                # 检查是否是因为套接字关闭导致的错误
                if not self._is_listening:
                    break  # 正常退出
                print(f"P2P监听器出错 (OSError): {e}")
            except Exception as e:
                print(f"P2P监听器出错 (其他错误): {e}")

    def _listen_for_server_messages(self):
        while self._is_listening:
            try:
                line = self._file.readline()
                if not line:
                    print("服务器已断开连接。")
                    self.connection_failed_signal.emit()
                    break
                data = json.loads(line)
                self.server_message_received_signal.emit(data)
            except (json.JSONDecodeError, AttributeError):
                time.sleep(0.1)
                continue
            except Exception as e:
                print(f"监听线程出错: {e}")
                self.connection_failed_signal.emit()
                break

    def disconnect(self):
        self._is_listening = False
        if self._socket:
            self._socket.close()
        if self._p2p_socket:
            self._p2p_socket.close()
        print("网络连接已断开。") 