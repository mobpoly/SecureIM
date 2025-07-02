from PIL import Image
import io

# 使用字节终止符，避免中文字符被截断
DELIMITER = b"::EOF::"

# ----------------- 辅助函数 -----------------
def bytes_to_binary(data: bytes) -> str:
    """将字节序列转换为二进制字符串表示。"""
    return ''.join(format(b, '08b') for b in data)

def binary_to_bytes(binary: str) -> bytes:
    """将二进制字符串转换回字节序列。"""
    # 截断到 8 的倍数长度
    valid_len = len(binary) - (len(binary) % 8)
    return bytes(int(binary[i:i+8], 2) for i in range(0, valid_len, 8))

def embed_text_in_image(image_bytes, text_to_hide):
    """
    使用LSB（最低有效位）隐写术将文本消息嵌入到图像中。
    :param image_bytes: 作为字节的原始图像。
    :param text_to_hide: 要隐藏的字符串消息。
    :return: 带有隐藏消息的新图像的字节，如果失败则返回None。
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        payload_bytes = text_to_hide.encode('utf-8') + DELIMITER
        binary_text = bytes_to_binary(payload_bytes)
        
        width, height = image.size
        max_bytes = (width * height * 3) // 8
        if len(binary_text) > max_bytes:
            raise ValueError("文本太长，无法隐藏在此图像中。")
            
        data_index = 0
        new_image_data = []
        
        pixels = list(image.getdata())
        
        for i in range(len(pixels)):
            pixel = list(pixels[i])
            for j in range(3): # R, G, B 通道
                if data_index < len(binary_text):
                    # 修改颜色通道的最低有效位
                    pixel[j] = pixel[j] & ~1 | int(binary_text[data_index])
                    data_index += 1
            new_image_data.append(tuple(pixel))

        new_image = Image.new(image.mode, image.size)
        new_image.putdata(new_image_data)
        
        # 将新图像保存到字节缓冲区
        byte_arr = io.BytesIO()
        new_image.save(byte_arr, format='PNG') # PNG是无损的，最适合LSB
        return byte_arr.getvalue()

    except Exception as e:
        print(f"在图像中嵌入文本时出错: {e}")
        return None


def extract_text_from_image(image_bytes):
    """
    从图像中提取隐藏的文本消息。
    :param image_bytes: 带有隐藏消息的图像（字节形式）。
    :return: 隐藏的文本，如果未找到消息则返回None。
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        binary_data = ""
        pixels = list(image.getdata())

        for pixel in pixels:
            for color_val in pixel:
                binary_data += str(color_val & 1)
        
        # 将连续 bit 转回 bytes
        all_bytes = binary_to_bytes(binary_data)

        delim_index = all_bytes.find(DELIMITER)
        if delim_index != -1:
            hidden_bytes = all_bytes[:delim_index]
            try:
                return hidden_bytes.decode('utf-8')
            except UnicodeDecodeError:
                print("提取文本时 UTF-8 解码失败。")
                return None
        else:
            return None  # 未找到分隔符

    except Exception as e:
        print(f"从图像中提取文本时出错: {e}")
        return None 