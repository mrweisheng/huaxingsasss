# 📱 华星资源 · 移动端适配完成

## 改动总览

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `hooks/useMobile.ts` | **新增** | 移动端断点检测 hook |
| `components/MobileNav.tsx` | **新增** | 底部 TabBar 导航栏 |
| `components/MobileNav.css` | **新增** | 底部导航样式 |
| `components/Layout.tsx` | **修改** | 响应式 Sider/Drawer/MobileNav 集成 |
| `index.css` | **修改** | 移动端组件样式体系 |
| `pages/PaymentList.tsx` | **修改** | 表格列响应式配置 + 展开行详情重做 |
| `pages/PaymentList.css` | **修改** | 展开行移动端样式 |
| `pages/AgentChat.tsx` | **修改** | 移动端 Drawer 会话列表 + 隐藏侧栏 |

### 各页面移动端行为

**列表页**（ContractList/CustomerList）：
- 已是卡片网格，`768px` 以下自动单列
- 搜索框、分页自动全宽、纵向排列
- 卡片去掉了 hover 变形，点击有 `scale(0.98)` 反馈

**收付管理**（PaymentList）：
- 表格在大屏保持不变
- 小屏隐藏业务说明/日期/方式/操作列，关键信息（类型、客户、金额、状态）保留
- 点击行展开显示完整详情（描述、日期、方式、期数、凭证、备注、汇率折算）

**详情页**（ContractDetail/CustomerDetail）：
- 信息网格 1024px 2列 → 768px 1列
- 财务 KPI 区域自动纵向堆叠
- 付款记录列表单列显示

**智能问答**（AgentChat）：
- 左侧会话面板在移动端隐藏
- 顶部新增 `📋` 历史按钮，点击弹出 Drawer 会话列表
- 桌面端行为完全不变

**全部页面共享**：
- 底部固定 TabBar：客户/合同/收付/问答（按角色过滤）
- 左上角汉堡菜单：完整导航 + 用户信息 + 退出
- iOS 安全区适配
- 触摸目标 ≥44px，禁用文本选择，防输入缩放

### 桌面端行为零变动

所有移动端功能通过 `isMobile` 条件包裹或 CSS 媒体查询实现，**不破坏原有功能**。
