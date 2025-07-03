import socket
import threading
import json
import time
import uuid

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
        self.MAX_UDP_SIZE = 1400  # 安全的UDP数据包大小
        self._fragment_buffer = {}# 用于重组分片数据

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

            # 增加接收缓冲区大小
            self._p2p_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024*4)
            self._p2p_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024*4)

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
                return False
            try:
                # 序列化数据
                json_data = json.dumps(data)
                data_bytes = json_data.encode('utf-8')

                # 检查数据大小是否需要分片
                if len(data_bytes) <= self.MAX_UDP_SIZE:
                    # 小数据直接发送
                    self._p2p_socket.sendto(data_bytes + b'\n', recipient_addr)
                else:
                    # 大数据需要分片发送
                    return self._send_fragmented_data(data_bytes, recipient_addr)

                return True
            except Exception as e:
                print(f"发送P2P数据时出错: {e}")
                return False
        else:
            # TCP发送逻辑保持不变
            if not self._socket:
                print("错误: 未连接到服务器。")
                return False
            try:
                self._socket.sendall((json.dumps(data) + '\n').encode('utf-8'))
                return True
            except (BrokenPipeError, ConnectionResetError) as e:
                print(f"发送数据时出错，连接已断开: {e}")
                self.connection_failed_signal.emit()
                return False

    def _send_fragmented_data(self, data_bytes, recipient_addr):
        """发送分片数据"""
        try:
            fragment_id = str(uuid.uuid4())
            total_size = len(data_bytes)
            fragment_size = self.MAX_UDP_SIZE - 200  # 预留头部信息空间
            total_fragments = (total_size + fragment_size - 1) // fragment_size

            print(f"发送大数据包，总大小: {total_size} 字节，分片数: {total_fragments}")

            for i in range(total_fragments):
                start = i * fragment_size
                end = min(start + fragment_size, total_size)
                fragment_data = data_bytes[start:end]

                # 创建分片包
                fragment_packet = {
                    "type": "fragment",
                    "fragment_id": fragment_id,
                    "fragment_index": i,
                    "total_fragments": total_fragments,
                    "data": fragment_data.decode('utf-8', errors='ignore')  # 转为base64更安全
                }

                # 使用base64编码二进制数据
                import base64
                fragment_packet["data"] = base64.b64encode(fragment_data).decode('ascii')

                packet_json = json.dumps(fragment_packet)
                self._p2p_socket.sendto(packet_json.encode('utf-8') + b'\n', recipient_addr)

            return True
        except Exception as e:
            print(f"发送分片数据时出错: {e}")
            return False

    def start_listening(self):
        self._is_listening = True
        self._listener_thread = threading.Thread(target=self._listen_for_server_messages)
        self._listener_thread.daemon = True
        self._listener_thread.start()

    def _listen_for_p2p_messages(self):
        while self._is_listening:
            try:
                data, addr = self._p2p_socket.recvfrom(8192)  # 增加接收缓冲区
                message_str = data.decode('utf-8').strip()

                try:
                    message = json.loads(message_str)

                    # 检查是否为分片数据
                    if message.get("type") == "fragment":
                        self._handle_fragment(message, addr)
                    else:
                        # 普通消息直接处理
                        self.p2p_message_received_signal.emit({"data": message, "addr": addr})

                except json.JSONDecodeError:
                    print(f"收到无效的JSON数据: {message_str[:100]}...")

            except OSError as e:
                if not self._is_listening:
                    break
                print(f"P2P监听器出错 (OSError): {e}")
            except Exception as e:
                print(f"P2P监听器出错 (其他错误): {e}")

    def _handle_fragment(self, fragment, addr):
        """处理接收到的分片数据"""
        try:
            fragment_id = fragment["fragment_id"]
            fragment_index = fragment["fragment_index"]
            total_fragments = fragment["total_fragments"]
            fragment_data = fragment["data"]

            # 使用base64解码
            import base64
            fragment_bytes = base64.b64decode(fragment_data.encode('ascii'))

            # 初始化分片缓冲区
            if fragment_id not in self._fragment_buffer:
                self._fragment_buffer[fragment_id] = {
                    "fragments": {},
                    "total_fragments": total_fragments,
                    "addr": addr
                }

            # 存储分片
            self._fragment_buffer[fragment_id]["fragments"][fragment_index] = fragment_bytes

            # 检查是否收到所有分片
            buffer_entry = self._fragment_buffer[fragment_id]
            if len(buffer_entry["fragments"]) == total_fragments:
                # 重组数据
                complete_data = b""
                for i in range(total_fragments):
                    complete_data += buffer_entry["fragments"][i]

                # 清理缓冲区
                del self._fragment_buffer[fragment_id]

                # 解析重组后的消息
                try:
                    complete_message = json.loads(complete_data.decode('utf-8'))
                    self.p2p_message_received_signal.emit({"data": complete_message, "addr": addr})
                    print(f"成功重组分片消息，总大小: {len(complete_data)} 字节")
                except json.JSONDecodeError as e:
                    print(f"重组后的数据不是有效JSON: {e}")

        except Exception as e:
            print(f"处理分片数据时出错: {e}")

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