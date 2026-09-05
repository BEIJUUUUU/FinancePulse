"""
PushPlus (推送加) 微信推送模块
支持原生 HTTP 请求，零外部依赖，安全直接推送到个人微信公众号服务通知
"""
import json
import urllib.request
import urllib.error

def send_pushplus(token: str, title: str, content: str, template: str = "html") -> bool:
    """
    通过 PushPlus 接口将内容推送到个人微信
    :param token: PushPlus 用户的个人密钥 Token
    :param title: 微信推送消息的标题
    :param content: 推送的文本、Markdown 或 HTML 内容
    :param template: 模板类型，可选: 'html', 'markdown', 'txt', 'json'
    """
    if not token:
        print("[警告] 未配置 PUSHPLUS_TOKEN，跳过微信推送。请在 config.py 中配置。")
        return False

    url = "http://www.pushplus.plus/send"
    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": template
    }

    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            
            # PushPlus 成功时返回 code: 200
            if res_json.get("code") == 200:
                print(f"[成功] 微信推送成功！PushPlus 返回流水号: {res_json.get('data')}")
                return True
            else:
                print(f"[失败] PushPlus 接口返回错误: {res_json.get('msg')} (code: {res_json.get('code')})")
                return False
    except urllib.error.HTTPError as e:
        print(f"[网络错误] PushPlus HTTP 请求异常: {e.code} - {e.reason}")
        return False
    except Exception as e:
        print(f"[异常] 微信推送过程发生未知异常: {e}")
        return False

if __name__ == "__main__":
    # 快速自测
    test_token = "438c49cdca054ac28eb746bab361295d"
    send_pushplus(
        token=test_token,
        title="财经机器人微信联调测试",
        content="<p>这是一条来自 <b>FinanceNewsBot</b> 的测试消息，微信推送通道配置成功！</p>",
        template="html"
    )
