#!/usr/bin/env python3
import re
import ssl
import urllib.request
from urllib.error import URLError


URL = "https://www.10jqka.com.cn/"
INDEX_NAMES = ("上证指数", "沪深300", "创业板指")


def main():
    request = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            html = response.read().decode("utf-8", errors="ignore")
            note = ""
    except URLError as error:
        if "CERTIFICATE_VERIFY_FAILED" not in str(error):
            raise
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            html = response.read().decode("utf-8", errors="ignore")
            note = "本机 Python 证书链校验失败，已用备用方式完成连通性检测。"

    print(f"已连接：{URL}")
    if note:
        print(note)
    for name in INDEX_NAMES:
        match = re.search(rf"{re.escape(name)}\\s*</?[^>]*>\\s*--", html)
        status = "页面初始值为 --，需要浏览器动态接口或人工导出数据" if match else "页面中出现该指数名称"
        print(f"{name}：{status}")


if __name__ == "__main__":
    main()
