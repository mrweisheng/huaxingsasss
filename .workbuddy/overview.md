# 收付管理 & 客户详情 UI 改造完成

## 收付管理页面

### 改造内容
| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| 筛选 | 1个状态下拉 | 搜索框 + 日期范围 + 状态下拉 |
| 列数 | 13 列，太密集 | 精简至约 8 列 |
| 合同编号/客户 | 两列分开，占空间 | 合并为一列两行显示 |
| 币种/金额 | 拆为两列 | 合并显示（如 HK$ 120,000.00） |
| 折算CNY | 始终显示一列 | 仅跨币种时显示在金额下方 |
| 备注 | 占一列，宽度不足 | 移入行展开区域 |
| KPI 摘要 | 无 | 4 卡片行（收入/支出/待处理/逾期） |
| 行视觉 | 统一白色 | 逾期行浅红底色、已付金额绿色 |
| 入场动画 | 无 | fadeIn 动画 |

### 后端变更
- payment list API 新增 `keyword`、`date_from`、`date_to` 参数

## 客户详情页面

### 改造内容
| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| 容器 padding | 无（贴边） | `padding: 20px 24px` + 入场动画 |
| 顶部操作栏 | 裸 Button | detail-header 风格（与合同详情一致） |
| 客户信息区 | Card + Descriptions | cd-topbar + cd-info-strip（4列网格） |
| 合同统计 | Statistic 裸组件 | cd-kpi-row 三卡片（总数、总额、已付） |
| 关联合同表 | Card 封装 | cd-payment-section 风格容器 |
| 风格统一性 | 孤立不与全站对齐 | 完全对齐合同详情 cd-* 体系 |
| CSS 文件 | 无 | 新建 CustomerDetail.css |

---

## 改动文件清单

- `backend/app/api/v1/payments.py` — 新增 keyword/date_from/date_to
- `frontend/src/services/payment.ts` — 更新 PaymentListParams 类型
- `frontend/src/pages/PaymentList.tsx` — 完整重写
- `frontend/src/pages/PaymentList.css` — 完整重写
- `frontend/src/pages/CustomerDetail.tsx` — 完整重写
- `frontend/src/pages/CustomerDetail.css` — 新文件
