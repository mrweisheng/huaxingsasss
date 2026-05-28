# 自动部署方案

## 流程

```
本地 git push github master → GitHub Webhook POST → 服务器自动拉取 + 重启
```

无需 SSH、无需密码，推送即部署。

## 新增文件

| 文件 | 用途 |
|------|------|
| `scripts/webhook_listener.py` | Webhook 监听服务，纯 Python 标准库，无需额外依赖 |
| `scripts/deploy.sh` | 服务器端部署脚本：git pull + uv sync + pm2 restart |

## 服务器配置步骤

### 1. 开放端口

Webhook 监听服务运行在 9000 端口，需要放行：

```bash
# firewalld
firewall-cmd --add-port=9000/tcp --permanent && firewall-cmd --reload

# 或 ufw
ufw allow 9000
```

### 2. 启动 Webhook 监听

```bash
cd /home/huaxingsasss

# 设置 Secret（和 GitHub Webhook 配置保持一致）
WEBHOOK_SECRET="你设定的密钥" pm2 start scripts/webhook_listener.py \
  --interpreter python3 \
  --name webhook \
  -o /tmp/webhook-out.log \
  -e /tmp/webhook-error.log

pm2 save
```

验证是否启动成功：

```bash
pm2 status
curl http://127.0.0.1:9000/webhook
```

### 3. 配置 GitHub Webhook

仓库地址：https://github.com/mrweisheng/huaxingsasss/settings/hooks

点击 **Add webhook**：

| 字段 | 值 |
|------|-----|
| Payload URL | `http://207.57.128.6:9000/webhook` |
| Content type | `application/json` |
| Secret | 和服务器 `WEBHOOK_SECRET` 一致 |
| 触发事件 | **Just the push event** |

### 4. 服务器添加 GitHub remote

```bash
cd /home/huaxingsasss
git remote add github https://github.com/mrweisheng/huaxingsasss.git
```

## 部署日志

每次部署的输出记录在 `/tmp/deploy.log`，Webhook 自身日志在 `/tmp/webhook-out.log`。

## 工作机制

1. 本地推送 `git push github master`
2. GitHub 向 `http://207.57.128.6:9000/webhook` 发送 POST 请求
3. `webhook_listener.py` 验证签名 → 确认是 master 分支 → 调用 `deploy.sh`
4. `deploy.sh` 执行：`git pull github master` → `uv sync` → `pm2 restart`
5. 完成，全程约 10-30 秒

## 注意事项

- `WEBHOOK_SECRET` 请设定为一个随机字符串，不要用默认值
- 如果服务器 IP 变更，需要同步更新 GitHub Webhook 的 Payload URL
- Webhook 监听服务本身由 pm2 管理，服务器重启后会自动恢复
