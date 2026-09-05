"""
邮件推送核心引擎 (规范 RFC5322 标准协议，完全兼容 QQ 邮箱 / 163 邮箱 / 企业邮)
支持单收件人与多收件人群发 (逗号/分号/中文逗号分隔均可)
"""
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr

def _parse_receivers(receiver_email: str, fallback: str = "") -> list[str]:
    """解析收件人字符串，支持中英文逗号、分号、空格等多种分隔符"""
    if not receiver_email:
        receiver_email = fallback
    raw = receiver_email.replace("，", ",").replace("；", ";").replace(";", ",").replace(" ", ",")
    receivers = [r.strip() for r in raw.split(",") if r.strip()]
    # 简单格式校验
    valid = [r for r in receivers if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", r)]
    return valid

def send_email_digest(
    smtp_server: str,
    smtp_port: int,
    sender_email: str,
    sender_auth_code: str,
    receiver_email: str,
    subject: str,
    html_content: str,
    attachment_path: str = None
) -> bool:
    """
    通过 SMTP SSL 发送财经早报邮件 (支持多收件人群发)
    """
    if not sender_email or not sender_auth_code:
        print("[警告] 未配置发件人邮箱或授权码，跳过邮件发送。")
        return False

    receivers = _parse_receivers(receiver_email, fallback=sender_email)
    if not receivers:
        print("[警告] 未找到有效的收件人邮箱，跳过邮件发送。")
        return False

    message = MIMEMultipart("related")
    message["From"] = formataddr(("FinancePulse 财经早报", sender_email))
    message["To"] = ", ".join(receivers)
    message["Subject"] = Header(subject, "utf-8")

    # 挂载精美 HTML 正文
    html_part = MIMEText(html_content, "html", "utf-8")
    message.attach(html_part)

    # 挂载附件 (如有)
    if attachment_path and os.path.exists(attachment_path):
        try:
            with open(attachment_path, "rb") as f:
                filename = os.path.basename(attachment_path)
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename*=UTF-8''{Header(filename, 'utf-8').encode()}"
                )
                message.attach(part)
        except Exception as e:
            print(f"[提示] 附件挂载异常: {e}")

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20)
        server.login(sender_email, sender_auth_code)
        server.sendmail(sender_email, receivers, message.as_string())
        server.quit()
        if len(receivers) > 1:
            print(f"[成功] 群发完成！已送达 {len(receivers)} 个收件邮箱: {', '.join(receivers)}")
        else:
            print(f"[成功] 邮件已成功送达目标邮箱: {receivers[0]}！")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[错误] 授权码或账号认证失败！请确认 QQ 邮箱网页版是否已开启 POP3/SMTP 并正确复制 16 位授权码。")
        return False
    except Exception as e:
        print(f"[错误] 邮件发送异常: {e}")
        return False
