# 合同管理系统 - 前端

React + TypeScript + Vite + Ant Design

## 快速开始

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build
```

访问 http://localhost:3000

## 技术栈

- React 18
- TypeScript 5
- Vite 5
- Ant Design 5
- Zustand (状态管理)
- Axios (HTTP客户端)

## 项目结构

```
frontend/src/
├── components/     # 公共组件
├── pages/          # 页面组件
├── services/       # API服务
├── store/          # 状态管理
├── types/          # TypeScript类型
└── utils/          # 工具函数
```

## 已完成页面

- ✅ 登录页
- ✅ 客户列表/详情
- ✅ 合同列表/详情/上传
- ✅ 付款管理（占位）
- ✅ 智能问答（占位）

## API代理

开发模式下，`/api` 请求会代理到 `http://localhost:8000`
