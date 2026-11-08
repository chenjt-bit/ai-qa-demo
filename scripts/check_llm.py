import os
from pathlib import Path
from dotenv import load_dotenv
import requests

#获取当前脚本的绝对路径，然后往上找一层（既项目根目录）
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
#自动读取.env文件并写入系统环境变量
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("DEEPSEEK_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL")
model = os.getenv("DEEPSEEK_MODEL")

print("Key是否读到：",bool(api_key))
print("Base URL:",base_url)
print("Model:",model)

# 向大模型接口发送请求
req = requests.post(
    f"{base_url}/chat/completions",
    headers={"Authorization":f"Bearer {api_key}"},
    json={
        "model":model,
        "messages":[
            {"role":"user","content":"用一句话介绍你自己"}
        ],
    },
    timeout = 30
)

print("HTTP 状态码：",req.status_code)
print("响应体：",req.json())