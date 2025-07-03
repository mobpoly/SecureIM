import sys
import os

# 将 src 目录添加到 Python 路径中，以便能够导入 secureim 包
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from secureim.server.main import start_server

if __name__ == '__main__':
    start_server() 