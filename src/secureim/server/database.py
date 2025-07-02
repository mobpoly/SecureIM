import sqlite3
import hashlib
import os

# 将数据库文件放置在项目根目录下的 'data' 文件夹中，如果不存在则创建
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, 'server.db')


def get_db_connection():
    """建立到数据库的连接。"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    """如果表不存在，则创建所需的数据库表。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 用户表 (users)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            public_key TEXT NOT NULL
        );
    ''')
    
    # 好友关系表 (friendships)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friendships (
            user_id1 INTEGER NOT NULL,
            user_id2 INTEGER NOT NULL,
            PRIMARY KEY (user_id1, user_id2),
            FOREIGN KEY(user_id1) REFERENCES users(id),
            FOREIGN KEY(user_id2) REFERENCES users(id)
        );
    ''')
    
    conn.commit()
    conn.close()
    print(f"数据库表已在 {DB_FILE} 创建或已存在。")

def hash_password(password):
    """为存储密码进行哈希处理。"""
    return hashlib.sha256(password.encode()).hexdigest()

def add_user(username, password, email, public_key):
    """
    向数据库中添加一个新用户。
    返回一个元组 (bool, str)，表示成功状态和消息。
    """
    if not all([username, password, email, public_key]):
        return False, "所有字段均为必填项。"

    conn = get_db_connection()
    cursor = conn.cursor()
    password_hash = hash_password(password)
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, email, public_key) VALUES (?, ?, ?, ?)",
            (username, password_hash, email, public_key)
        )
        conn.commit()
        return True, "注册成功"
    except sqlite3.IntegrityError as e:
        error_message = str(e).lower()
        if 'unique constraint failed: users.username' in error_message:
            return False, "该用户名已被使用。"
        elif 'unique constraint failed: users.email' in error_message:
            return False, "该邮箱已被注册。"
        else:
            return False, "发生未知数据库错误。"
    finally:
        conn.close()

def check_credentials(login_identifier, password):
    """
    使用用户名或邮箱验证用户凭据。
    成功则返回用户名，否则返回None。
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    password_hash = hash_password(password)
    cursor.execute(
        "SELECT username FROM users WHERE (username = ? OR email = ?) AND password_hash = ?",
        (login_identifier, login_identifier, password_hash)
    )
    user = cursor.fetchone()
    conn.close()
    return user['username'] if user else None

def get_user_public_key(username):
    """根据用户名检索公钥。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT public_key FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result['public_key'] if result else None

def get_user_id(username):
    """根据用户名获取用户ID。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result['id'] if result else None

def add_friend(username1, username2):
    """添加一个好友关系。"""
    user_id1 = get_user_id(username1)
    user_id2 = get_user_id(username2)
    
    if not user_id1 or not user_id2 or user_id1 == user_id2:
        return False
        
    # 确保好友关系以一致的顺序存储，以避免重复
    if user_id1 > user_id2:
        user_id1, user_id2 = user_id2, user_id1
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO friendships (user_id1, user_id2) VALUES (?, ?)",
            (user_id1, user_id2)
        )
        conn.commit()
        # 检查插入是否成功
        return conn.total_changes > 0
    except sqlite3.IntegrityError: # 好友关系已存在
        return False
    finally:
        conn.close()

def delete_friend(username1, username2):
    """删除一个好友关系。"""
    user_id1 = get_user_id(username1)
    user_id2 = get_user_id(username2)

    if not user_id1 or not user_id2:
        return False

    if user_id1 > user_id2:
        user_id1, user_id2 = user_id2, user_id1

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM friendships WHERE user_id1 = ? AND user_id2 = ?",
        (user_id1, user_id2)
    )
    conn.commit()
    deleted = conn.total_changes > 0
    conn.close()
    return deleted


def get_friends(username):
    """根据给定的用户检索好友列表。"""
    user_id = get_user_id(username)
    if not user_id:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 好友关系可能存在于任一列中
    cursor.execute("""
        SELECT u.username FROM users u JOIN friendships f ON u.id = f.user_id2 WHERE f.user_id1 = ?
        UNION
        SELECT u.username FROM users u JOIN friendships f ON u.id = f.user_id1 WHERE f.user_id2 = ?
    """, (user_id, user_id))
    
    friends = [row['username'] for row in cursor.fetchall()]
    conn.close()
    return friends 