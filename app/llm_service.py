# 在这个服务层中，专门负责与Deep Seek通信，对外提供一个回答函数get_ai_answer()
import os
from pathlib import Path
from dotenv import load_dotenv
import requests

#获取当前脚本的绝对路径，然后往上找一层（既项目根目录）
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"

# 默认在当前同级目录下读取.env文件并自动写入os的系统环境变量，可以写入指定的路径
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
# 给deep seek发送请求
def get_ai_answer(question:str)->str:
    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization":f"Bearer {API_KEY}"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": question}]
            },
            timeout=30,
        )
        # 如果HTTP状态码不是200，抛出异常
        resp.raise_for_status()

        # 从返回的JSON中提取AI的回答
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return f"调用模型失败：{str(e)}"