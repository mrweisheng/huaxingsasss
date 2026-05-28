"""
GitHub Webhook 监听服务
收到 GitHub push 事件后自动拉取代码并重启服务
"""
import hmac
import hashlib
import json
import subprocess
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# 配置 - 通过环境变量设置
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me-to-a-random-string")
PORT = int(os.environ.get("WEBHOOK_PORT", "9000"))
DEPLOY_SCRIPT = os.path.expanduser("~/huaxingsasss/scripts/deploy.sh")


def verify_signature(payload: bytes, signature: str) -> bool:
    """验证 GitHub Webhook 签名"""
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        # 读取请求体
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)
        signature = self.headers.get("X-Hub-Signature-256", "")

        # 验证签名
        if not verify_signature(payload, signature):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            print("[拒绝] 签名验证失败")
            return

        # 检查是否是 master 分支的 push
        data = json.loads(payload)
        ref = data.get("ref", "")
        if ref != "refs/heads/master":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Ignored: not master branch")
            print(f"[忽略] 非 master 分支: {ref}")
            return

        # 触发部署
        print(f"[部署] 收到 master push，执行部署脚本...")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deploy triggered")

        subprocess.Popen(
            ["bash", DEPLOY_SCRIPT],
            stdout=open("/tmp/deploy.log", "a"),
            stderr=subprocess.STDOUT,
        )
        print("[部署] 部署脚本已启动")

    def log_message(self, format, *args):
        print(f"[webhook] {args[0]}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"Webhook 监听服务启动，端口 {PORT}")
    print(f"部署脚本: {DEPLOY_SCRIPT}")
    print(f"端点: http://0.0.0.0:{PORT}/webhook")
    sys.stdout.flush()
    server.serve_forever()
