# 凭证录入从 Agent 迁移到合同卡片

## Context

当前凭证（收据）录入完全依赖 Agent 聊天助手，需要 7+ 轮对话（文件分析 -> 搜索客户 -> match_receipt -> 查合同 -> 确认 -> 创建）才能完成一次录入，效率极低。合同创建、客户管理在 Agent 中表现良好，应保留。

**目标**：将凭证录入操作从 Agent 迁移到合同列表卡片的「收」「支」按钮，实现 1-2 步快速录入。Agent 保留凭证分析能力（只查看不录入），但阻止凭证写入操作并引导用户去卡片。

## 审核修订记录

本文档已整合两份独立审核的反馈，所有设计决策均已确认：

| 决策项 | 结论 |
|--------|------|
| 新端点 vs 扩展现有 `upload-receipt` | 新建独立端点，保留 `upload-receipt` 不动 |
| 临时文件清理策略 | 分析阶段存 `TEMP_UPLOAD_DIR`，创建成功后迁移到 `RECEIPT_UPLOAD_DIR`；现有 Celery 任务 `cleanup_temp_files`（每天凌晨3点清理 >24h 文件）兜底 |
| installment_number 并发冲突 | 服务端实时重算，忽略前端传来的值 |
| source 字段 | 不改，保持默认 `manual` |
| 批量凭证失败交互 | 自动跳过（3秒延迟展示错误）+ summary 页面可用缓存 bytes 重试 |
| 期数编号显示 | 不显示编号，改为显示"该合同已有 N 笔收入/支出记录" |
| save_upload 位置 | API 端点层（不在 ReceiptAnalyzer 中） |
| receipt_data 类型 | 使用 `ReceiptAnalysisData` Schema，不用裸 dict |
| 共享工具函数 | 从 `contract_analyzer.py` 提取到 `utils/file_analysis.py` |

## 实施计划

### 阶段 0：提取共享工具函数

从 `contract_analyzer.py` 提取以下模块级函数到 `backend/app/utils/file_analysis.py`，两个 Analyzer 共同引用。打破 `_` 前缀私有函数跨模块导入的惯例问题。

**提取的函数**（当前在 `contract_analyzer.py` 中，保留原始签名不变）：

```python
# backend/app/utils/file_analysis.py
# 所有签名与 contract_analyzer.py 中的原始实现完全一致，仅去掉 _ 前缀

def compress_image(file_bytes: bytes, mime: str) -> tuple[bytes, str]:
    """压缩图片。参数 mime 为已知 MIME 类型，返回 (compressed_bytes, mime_type)。"""

def detect_image_mime(header: bytes) -> str:
    """通过文件头魔数字节检测图片 MIME 类型，未识别返回空字符串。"""

def call_vl_model(file_bytes: bytes, mime: str, prompt: str) -> dict:
    """调用 DashScope VL 视觉模型（settings.DASHSCOPE_VISION_MODEL = qwen3-vl-flash），
    同步调用，返回解析后的 dict（JSON 解析失败时返回 {"raw": content}）。"""

def call_text_model(text: str, prompt: str) -> dict:
    """调用 DashScope 文本模型（settings.DASHSCOPE_TEXT_MODEL = qwen-plus），
    同步调用，返回解析后的 dict（JSON 解析失败时返回 {"raw": content}）。"""

def extract_pdf_text(file_path: str) -> str:
    """从 PDF 文件路径提取文本内容，无文本返回空字符串。"""

def render_pdf_page_to_image(file_path: str, page_num: int = 0, dpi: int = 150) -> bytes:
    """将 PDF 指定页渲染为 PNG bytes。"""

def extract_word_text(file_path: str) -> str:
    """从 Word (.docx) 文件路径提取文本。"""

def extract_excel_text(file_path: str) -> str:
    """从 Excel (.xlsx) 文件路径提取文本。"""

def extract_plain_text(file_bytes: bytes) -> str:
    """从 bytes 提取纯文本内容（自动检测编码）。"""

def is_docx(content: bytes) -> bool:
    """通过文件内容 bytes 判断是否为 Word 文件（ZIP 签名 + [Content_Types] 检测）。"""

def is_xlsx(content: bytes) -> bool:
    """通过文件内容 bytes 判断是否为 Excel 文件（ZIP 签名 + xl/ 检测）。"""

def guess_extension(content: bytes) -> str:
    """通过文件内容 bytes 的魔数字节猜测扩展名，未知返回 '.bin'。"""
```

**同步修改**：`contract_analyzer.py` 改为从 `utils/file_analysis` 导入，删除本地定义。

---

### 阶段 1：后端 — 新增凭证分析 + 快捷创建 API

#### 1.1 新增 `backend/app/services/receipt_analyzer.py`

从 `tools.py` 提取凭证 VL 分析逻辑为独立服务，参照 `contract_analyzer.py` 的架构模式。

**导入共享工具**：从 `utils/file_analysis.py` 导入所有工具函数。

**导入 prompt**：`RECEIPT_ANALYSIS_PROMPT` from `prompts.py`

**核心类 `ReceiptAnalyzer`**（纯分析逻辑，不涉及文件持久化）：

> **设计决策**：保留共享函数的 `file_path` 接口不变（PDF/Word/Excel 库都需要路径）。
> API 端点已将文件保存到 `TEMP_UPLOAD_DIR`，ReceiptAnalyzer 接收文件路径而非 bytes。

```python
class ReceiptAnalyzer:

    @staticmethod
    def analyze_from_file(file_path: str, file_name: str) -> dict:
        """从文件路径分析凭证（图片/PDF/Word/Excel）。

        参数 file_path: 已保存在 TEMP_UPLOAD_DIR 中的文件绝对路径。
        参数 file_name: 原始文件名（用于判断文件类型）。

        Returns:
            {
                "success": True,
                "data": {
                    "amount", "currency", "transaction_date", "payer_name",
                    "payee_name", "payment_method", "confidence",
                    "_warnings": [...]  # 币种/日期缺失时自动注入
                },
                "file_type": "image" | "pdf" | "document"
            }
        """
        # 逻辑：
        #   1. 读取文件 bytes → detect_image_mime / is_docx / is_xlsx / guess_extension 判断类型
        #   2. 图片 → compress_image + call_vl_model(file_bytes, mime, RECEIPT_ANALYSIS_PROMPT)
        #   3. PDF → extract_pdf_text(file_path)：
        #      有文本 → call_text_model(text, prompt)
        #      无文本（扫描件）→ render_pdf_page_to_image(file_path) → call_vl_model
        #   4. Word → extract_word_text(file_path) → call_text_model(text, prompt)
        #   5. Excel → extract_excel_text(file_path) → call_text_model(text, prompt)
        #   6. 对结果执行 _inject_receipt_warnings()
```

**`_inject_receipt_warnings` 逻辑**（从 tools.py 提取）：
- `currency` 为空 → `_warnings.append("币种未识别")`
- `transaction_date` 为空 → `_warnings.append("交易日期未识别")`

**注意**：此方法为同步方法（VL/文本模型调用为同步 HTTP），API 端点需用 `asyncio.to_thread()` 包装以避免阻塞事件循环。

#### 1.2 修改 `backend/app/schemas/payment.py` — 新增 Schema

```python
class ReceiptAnalysisData(BaseModel):
    """凭证 AI 分析结果的结构化数据，也用于 CreateFromReceiptRequest.receipt_data"""
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    transaction_date: Optional[str] = None
    payer_name: Optional[str] = None
    payee_name: Optional[str] = None
    payment_method: Optional[str] = None
    confidence: Optional[float] = None
    warnings: list[str] = Field(default_factory=list, alias="_warnings")

    model_config = ConfigDict(populate_by_name=True)


class PendingMatchItem(BaseModel):
    """待匹配的已有付款记录（仅 income 类型）"""
    payment_id: int
    installment_number: int
    installment_name: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    score: int
    match_reason: str


class ReceiptAnalyzeResponse(BaseModel):
    """凭证分析 + 匹配结果的响应"""
    analysis: ReceiptAnalysisData
    temp_file_path: str          # 临时文件路径（TEMP_UPLOAD_DIR 下）
    pending_matches: list[PendingMatchItem] = []
    existing_payment_count: int  # 该合同该类型已有几笔付款（供前端展示上下文）
    next_installment_number: int


class CreateFromReceiptRequest(BaseModel):
    """从凭证创建/匹配付款记录的请求"""
    contract_id: int
    payment_type: str  # "income" | "expense"
    temp_file_path: str     # analyze-receipt 返回的临时文件路径
    receipt_data: Optional[ReceiptAnalysisData] = None  # 结构化分析数据（非裸 dict）
    match_payment_id: Optional[int] = None    # 分支 A：匹配到已有记录
    installment_number: Optional[int] = None  # 分支 B：服务端忽略此值，实时重算
    installment_name: Optional[str] = None
    currency: str          # 必填，服务端二次校验
    amount: Decimal
    paid_date: date        # 必填，服务端二次校验
    payment_method: Optional[str] = None
    payee_name: Optional[str] = None  # expense 必填（Pydantic validator 校验）
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate_exclusive_fields(self) -> "CreateFromReceiptRequest":
        """match_payment_id 和 installment_number 互斥，且必须二选一"""
        has_match = self.match_payment_id is not None
        has_inst = self.installment_number is not None
        if has_match and has_inst:
            raise ValueError("match_payment_id 和 installment_number 不能同时提供")
        if not has_match and not has_inst:
            raise ValueError("必须提供 match_payment_id 或 installment_number 之一")
        return self

    @model_validator(mode="after")
    def _validate_expense_payee(self) -> "CreateFromReceiptRequest":
        """expense 类型时 payee_name 必填"""
        if self.payment_type == "expense" and not self.payee_name:
            raise ValueError("支出类型必须填写收款方（payee_name）")
        return self
```

#### 1.3 修改 `backend/app/api/v1/payments.py` — 新增 2 个端点

**端点 1: `POST /payments/analyze-receipt`**

```
请求: multipart/form-data
  - contract_id: int (Form)
  - payment_type: str (Form, "income" | "expense")
  - file: UploadFile (File)

权限:
  - income 角色 → payment_type 必须是 "income"
  - expense 角色 → payment_type 必须是 "expense"
  - admin → 均可
  - income 角色 → 校验 contract.sales_person_id == current_user.id

流程:
  1. 验证文件大小 (settings.MAX_FILE_SIZE)
  2. 读取 file bytes → 保存到 TEMP_UPLOAD_DIR/{user_id}/{unique_filename}
     （使用 file_utils.generate_unique_filename 生成唯一文件名）
     得到 temp_file_path（绝对路径）
  3. asyncio.to_thread(ReceiptAnalyzer.analyze_from_file, temp_file_path, file.filename)
     → analysis 结果
  4. 仅 income 类型: 查该合同 status=pending, type=income 的记录，按金额/币种评分
     评分逻辑（合同已知，简化为金额+币种匹配）:
       - 金额完全匹配 (差值 < 1) → +50
       - 金额近似 (差比 < 5%) → +30
       - 币种匹配 → +10
     按分数降序取前 5 条
  5. PaymentService.get_next_installment_number(db, contract_id, payment_type)
  6. 查询该合同该类型已有付款数量 → existing_payment_count
  7. 返回 ReceiptAnalyzeResponse
```

**端点 2: `POST /payments/create-from-receipt`**

```
请求: JSON body → CreateFromReceiptRequest

权限: 同 analyze-receipt

服务端二次校验:
  - currency 不能为空
  - paid_date 不能为空

流程（分支逻辑）:

  分支 A: match_payment_id 有值
    → 查询 payment，验证:
      - 属于同一合同（payment.contract_id == contract_id）
      - 类型匹配（payment.type == payment_type）
      - 状态为 pending（非 pending → 400 "只能匹配待确认状态的记录"）
    → 将临时文件从 TEMP_UPLOAD_DIR 移动到 RECEIPT_UPLOAD_DIR/YYYY/MM/
    → 构建 PaymentUpdate(receipt_image_path, receipt_data, paid_date, payment_method,
                          installment_name, notes)
    → PaymentService.update_payment() → 自动 pending→paid + 结算

  分支 B: installment_number 有值（服务端忽略前端值）
    → 服务端实时调用 PaymentService.get_next_installment_number(db, contract_id, payment_type)
      得到真实的 installment_number
    → 将临时文件从 TEMP_UPLOAD_DIR 移动到 RECEIPT_UPLOAD_DIR/YYYY/MM/
    → PaymentService.create_payment_with_exchange_rate(
        contract_id, real_installment_number, currency, amount, paid_date,
        payment_method, receipt_image_path, notes, created_by, type,
        payee_name, installment_name, receipt_data)
    → 有凭证直接 status='paid'，自动参与结算

  响应: PaymentResponse
```

**文件迁移辅助**：
```python
def _move_temp_to_permanent(temp_file_path: str) -> str:
    """将临时文件从 TEMP_UPLOAD_DIR 移动到 RECEIPT_UPLOAD_DIR/YYYY/MM/，
    返回永久相对路径。源文件不存在时返回空字符串（兼容清理任务已删除的情况）。"""
```

**错误处理**:
- 文件过大 → 413
- VL API 失败 → 502 (捕获 httpx 异常)
- 合同不存在 → 404
- 角色越权 → 403
- match_payment_id 不属于该合同 → 400
- match_payment_id 对应记录非 pending → 400
- expense 缺少 payee_name → 422 (Pydantic validator)
- currency 或 paid_date 为空 → 422 (服务端显式校验)
- installment_number 唯一约束冲突 → 409（理论上不会再发生，因为服务端实时重算）

---

### 阶段 2：前端 — 凭证录入 Modal 组件

#### 2.1 新增 `frontend/src/types/index.ts` 类型

```typescript
interface ReceiptAnalysisData {
  amount: number | null
  currency: string | null
  transaction_date: string | null
  payer_name: string | null
  payee_name: string | null
  payment_method: string | null
  confidence: number | null
  warnings: string[]
}

interface PendingMatchItem {
  payment_id: number
  installment_number: number
  installment_name: string | null
  amount: number
  currency: string
  status: string
  score: number
  match_reason: string
}

interface ReceiptAnalyzeResponse {
  analysis: ReceiptAnalysisData
  temp_file_path: string
  pending_matches: PendingMatchItem[]
  existing_payment_count: number  // 已有几笔付款
  next_installment_number: number
}

interface CreateFromReceiptRequest {
  contract_id: number
  payment_type: 'income' | 'expense'
  temp_file_path: string
  receipt_data?: ReceiptAnalysisData
  match_payment_id?: number       // 分支 A
  installment_number?: number     // 分支 B
  installment_name?: string
  currency: string
  amount: number
  paid_date: string
  payment_method?: string
  payee_name?: string
  notes?: string
}
```

#### 2.2 修改 `frontend/src/services/payment.ts` — 新增 2 个方法

```typescript
analyzeReceipt: (data: {
  contract_id: number, payment_type: string, file: File
}): Promise<ReceiptAnalyzeResponse> => {
  const formData = new FormData()
  formData.append('contract_id', String(data.contract_id))
  formData.append('payment_type', data.payment_type)
  formData.append('file', data.file)
  return api.post('/payments/analyze-receipt', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

createFromReceipt: (data: CreateFromReceiptRequest): Promise<Payment> => {
  return api.post('/payments/create-from-receipt', data)
}
```

#### 2.3 新增 `frontend/src/components/ReceiptPaymentModal.tsx` + `.css`

参照 `ContractUploadWizard.tsx` 的向导式设计（Ant Design Modal + Steps）。

**Props**:
```typescript
interface Props {
  open: boolean
  onClose: (success: boolean) => void
  contractId: number
  contractNumber: string
  customerName: string
  contractCurrency: string
  paymentType: 'income' | 'expense'
}
```

**核心状态**:
```typescript
// 凭证列表（批量上传，每张独立跟踪状态）
interface ReceiptFile {
  file: File
  fileBytes: ArrayBuffer | null  // 缓存文件 bytes，重试时复用
  id: string  // 前端临时 ID
  status: 'pending' | 'analyzing' | 'analyzed' | 'confirmed' | 'submitting' | 'done' | 'error'
  analysis?: ReceiptAnalyzeResponse
  formData?: {  // 用户编辑后的表单
    match_payment_id?: number
    installment_number: number
    installment_name: string
    currency: string
    amount: number
    paid_date: string
    payment_method: string
    payee_name?: string
    notes: string
  }
  result?: Payment
  error?: string
}

const [receipts, setReceipts] = useState<ReceiptFile[]>([])
const [currentStep, setCurrentStep] = useState<'upload' | 'processing' | 'summary'>('upload')
const [activeIndex, setActiveIndex] = useState(0)  // 当前处理的凭证索引
const [processingPhase, setProcessingPhase] = useState<'analyze' | 'confirm' | 'submit'>('analyze')
const [loading, setLoading] = useState(false)
```

**步骤流程**:

```
┌─ upload 步骤 ──────────────────────────────────────────────┐
│  合同上下文信息条: 合同编号 · 客户名 · 币种                   │
│  Upload.Dragger (multiple=true, 必须≥1张)                   │
│  已上传文件列表 (可删除)                                      │
│  [开始处理] 按钮 (disabled until ≥1 file)                    │
└────────────────────────────────────────────────────────────┘
         │ 点击"开始处理" → 进入 processing 步骤
         ▼
┌─ processing 步骤（对每张凭证循环）──────────────────────────┐
│  顶部: 凭证缩略图行 (active 高亮, done 灰勾, error 红叉)      │
│                                                             │
│  ┌─ analyze 阶段 ────────────────────────────────────────┐ │
│  │  Spin + 动态提示语 (timer 轮播)                         │ │
│  │  调用 paymentApi.analyzeReceipt(contractId, type, file) │ │
│  │  同时缓存 fileBytes（用于后续重试，避免重新上传）          │ │
│  │  成功 → 自动进入 confirm 阶段                            │ │
│  │  失败 → 标记 error，3 秒后自动跳到下一张                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ confirm 阶段 ────────────────────────────────────────┐ │
│  │  已有记录上下文提示: "该合同已有 N 笔收入/支出记录"       │ │
│  │  warnings 横幅 (如有): "币种未识别，请手动确认"          │ │
│  │                                                        │ │
│  │  [收入模式]                                             │ │
│  │  匹配选择区 (pending_matches 非空时):                    │ │
│  │    Radio.Group:                                        │ │
│  │    ○ 第1期 定金 ¥50,000 (匹配度60)                     │ │
│  │    ○ 第2期 尾款 ¥30,000 (匹配度30)                     │ │
│  │    ● 创建新记录 (默认选中)                               │ │
│  │                                                        │ │
│  │  表单区:                                                │ │
│  │    金额 (InputNumber, AI 预填)                          │ │
│  │    币种 (Select, 默认合同币种, warning 时红色边框)        │ │
│  │    交易日期 (DatePicker, 默认今天, warning 时红色边框)    │ │
│  │    付款方式 (Select)                                     │ │
│  │    期数名称 (Input, 如"定金"、"尾款")                    │ │
│  │    备注 (TextArea)                                       │ │
│  │                                                        │ │
│  │  [支出模式]                                             │ │
│  │    无匹配选择区                                          │ │
│  │    表单同上 + 额外: 收款方 (Input, 必填)                 │ │
│  │                                                        │ │
│  │  [确认并提交] 按钮                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ submit 阶段 ────────────────────────────────────────┐  │
│  │  调用 paymentApi.createFromReceipt(formData)           │  │
│  │  成功 → 标记 done → activeIndex++ → 回到 analyze       │  │
│  │  失败 → 标记 error → 3 秒后自动跳到下一张               │  │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  全部处理完毕 → 自动进入 summary 步骤                         │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ summary 步骤 ─────────────────────────────────────────────┐
│  成功 N 笔 / 失败 M 笔                                     │
│  每笔摘要: 期数名称、金额、状态图标                           │
│  失败项: [重试] 按钮（用缓存的 fileBytes 重新调分析 API，     │
│          不需要重新上传文件）                                 │
│  [关闭] 按钮                                                │
└────────────────────────────────────────────────────────────┘
```

**Steps 组件**（简化为 3 步）:
```
[上传凭证] → [处理 (N/M)] → [完成]
processing 步骤的标题动态显示: "处理第 N/M 张"
```

**CSS 文件** (`ReceiptPaymentModal.css`):
- 参照 `ContractUploadWizard.css` 的设计系统
- 前缀: `.receipt-modal-*`
- 复用 CSS 变量: `var(--brand-primary)`, `var(--text-*)`, `var(--radius-*)`
- 凭证缩略图行: 横向 flex, 40x40 缩略图, active 蓝色边框, done 灰色 + 勾, error 红色 + 叉
- 匹配卡片: Radio + 浅色卡片, 选中品牌色边框
- warnings 横幅: 参照 `.wizard-duplicate-warning` 橙色样式

---

### 阶段 3：前端 — 合同卡片集成

#### 3.1 修改 `frontend/src/pages/ContractList.tsx`

**改动范围**（最小化）:

1. **新增导入**: `ReceiptPaymentModal`, `Tooltip` from antd, `DollarOutlined` / `AccountBookOutlined` from icons

2. **新增状态**:
   ```typescript
   const [receiptModal, setReceiptModal] = useState<{
     open: boolean
     contract: Contract | null
     type: 'income' | 'expense'
   }>({ open: false, contract: null, type: 'income' })
   ```

3. **footer-actions 区域新增按钮**（在删除按钮之前插入）:
   ```tsx
   <div className="footer-actions" onClick={(e) => e.stopPropagation()}>
     {/* 新增: 收入按钮 */}
     {(role === 'admin' || role === 'income') && (
       <Tooltip title="录入收入">
         <DollarOutlined
           className="action-icon income"
           onClick={(e) => {
             e.stopPropagation()
             setReceiptModal({ open: true, contract, type: 'income' })
           }}
         />
       </Tooltip>
     )}
     {/* 新增: 支出按钮 */}
     {(role === 'admin' || role === 'expense') && (
       <Tooltip title="录入支出">
         <AccountBookOutlined
           className="action-icon expense"
           onClick={(e) => {
             e.stopPropagation()
             setReceiptModal({ open: true, contract, type: 'expense' })
           }}
         />
       </Tooltip>
     )}
     {/* 原有: 删除按钮 (保持不变) */}
     <Popconfirm ...> <DeleteOutlined className="action-icon delete" /> </Popconfirm>
   </div>
   ```

4. **Modal 渲染**（在 ContractUploadWizard 旁边）:
   ```tsx
   {receiptModal.contract && (
     <ReceiptPaymentModal
       open={receiptModal.open}
       onClose={(success) => {
         setReceiptModal(prev => ({ ...prev, open: false }))
         if (success) loadContracts()
       }}
       contractId={receiptModal.contract.id}
       contractNumber={receiptModal.contract.contract_number}
       customerName={receiptModal.contract.customer_name}
       contractCurrency={receiptModal.contract.currency}
       paymentType={receiptModal.type}
     />
   )}
   ```

#### 3.2 修改 `frontend/src/pages/ContractList.css`

新增样式:
```css
.action-icon.income {
  color: #0d9488;
}
.action-icon.income:hover {
  background: rgba(13, 148, 136, 0.08);
}
.action-icon.expense {
  color: #d97706;
}
.action-icon.expense:hover {
  background: rgba(217, 119, 6, 0.08);
}
```

---

### 阶段 4：Agent 引导调整

#### 4.1 修改 `backend/app/ai/tools.py`

**`_DOCUMENT_BLOCKED_TOOLS` 更新**:

```python
_DOCUMENT_BLOCKED_TOOLS = {
    "receipt": {
        "create_contract", "create_customer", "create_expense", "update_contract",
        "create_payment", "update_payment", "match_receipt",  # 新增：阻断凭证写入
    },
    "general": { ... },  # 不变
    "group_chat": { ... },  # 不变
}
```

**`_check_document_guard` hint 更新**:

```python
"receipt": "凭证录入已迁移到合同列表卡片的「收」「支」按钮。请引导用户在合同列表找到对应合同，点击卡片上的按钮进行凭证录入。如需查询付款信息，仍可使用 query_payments / get_contract_detail。",
```

#### 4.2 修改 `backend/app/ai/prompts.py`

**系统提示词中「凭证处理」段落替换**:

```
### 凭证录入
凭证录入（创建付款/支出记录、匹配凭证）已迁移到合同列表卡片的「收」「支」按钮，不再通过聊天完成。
当用户上传凭证并要求录入时：
1. analyze_image 分析凭证内容，展示识别结果
2. 引导用户：请到合同列表找到对应合同，点击卡片上的「收」或「支」按钮完成录入，更快捷方便
你仍然可以：
- analyze_image 分析凭证内容（只查看，不录入）
- query_payments 查询已有付款记录
- get_payment_summary 获取付款汇总
```

**保留不变**: `RECEIPT_ANALYSIS_PROMPT`（ReceiptAnalyzer 和 Agent 都引用它）

---

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| 新增 | `backend/app/utils/file_analysis.py` | 共享文件分析工具函数（从 contract_analyzer.py 提取） |
| 修改 | `backend/app/services/contract_analyzer.py` | 改为从 utils/file_analysis 导入工具函数 |
| 新增 | `backend/app/services/receipt_analyzer.py` | 凭证 VL 分析独立服务（纯分析，不涉及文件持久化） |
| 修改 | `backend/app/schemas/payment.py` | +4 个 Schema 类（含 Pydantic validator 互斥校验） |
| 修改 | `backend/app/api/v1/payments.py` | +2 个端点（含文件保存到临时目录 + 成功后迁移逻辑） |
| 修改 | `frontend/src/types/index.ts` | +4 个类型定义 |
| 修改 | `frontend/src/services/payment.ts` | +2 个 API 方法 |
| 新增 | `frontend/src/components/ReceiptPaymentModal.tsx` | 凭证录入向导 Modal（3 步向导 + 批量处理 + 缓存重试） |
| 新增 | `frontend/src/components/ReceiptPaymentModal.css` | Modal 样式 |
| 修改 | `frontend/src/pages/ContractList.tsx` | 卡片加收/支按钮 + 集成 Modal + 补充 Tooltip 导入 |
| 修改 | `frontend/src/pages/ContractList.css` | 收/支按钮样式 |
| 修改 | `backend/app/ai/tools.py` | 文档守卫阻断列表 + 拦截提示 |
| 修改 | `backend/app/ai/prompts.py` | 系统提示词引导到卡片 |

## 实施顺序

```
Batch 0 (基础设施): 提取共享工具函数到 utils/file_analysis.py → contract_analyzer.py 改导入
Batch 1 (后端核心): receipt_analyzer.py → schemas → API 端点（含服务端校验 + 临时文件处理）
Batch 2 (前端): types → services → ReceiptPaymentModal → ContractList 集成
Batch 3 (Agent): tools.py 守卫 → prompts.py 提示词
```

## 验证方式

1. **后端 API 测试**:
   - 启动后端 `uv run uvicorn app.main:app --reload`
   - Swagger UI 测试 `POST /payments/analyze-receipt`: 上传凭证图片 + contract_id + payment_type，确认返回分析结果、匹配列表和已有记录数
   - Swagger UI 测试 `POST /payments/create-from-receipt`: 用分析返回的 temp_file_path + 表单数据，确认创建付款成功且合同金额正确累加
   - 测试 match_payment_id 分支: 确认 pending→paid 转换和结算，非 pending 记录返回 400
   - 测试 currency/paid_date 为空: 确认 422 校验拦截
   - 验证临时文件清理: 取消操作后等待 Celery 任务执行（或手动触发），确认过期文件被清理
   - 并发测试: 两个请求同时 create 同一合同，确认 installment_number 不冲突

2. **前端集成测试**:
   - 启动前端 `npm run dev`
   - 合同列表卡片验证「收」「支」按钮按角色可见性正确显示
   - 点击「收」→ 批量上传 2 张凭证 → 开始处理 → 逐张 AI 分析 → 编辑确认 → 提交 → 汇总页 → 关闭后卡片金额刷新
   - 点击「支」→ 上传 1 张凭证 → 分析 → 填写收款方 → 提交
   - warnings 场景: 上传币种/日期缺失的凭证，确认表单红色高亮提示
   - 失败场景: 模拟分析失败，确认 3 秒后自动跳过，summary 页面可重试
   - 已有记录提示: 确认显示"该合同已有 N 笔收入记录"

3. **Agent 引导测试**:
   - Agent 聊天中上传凭证 → 确认 Agent 分析内容并展示，但阻止 create_payment/match_receipt/update_payment
   - 确认拦截消息正确引导到卡片操作

4. **构建验证**:
   - 后端: `uv run pytest`
   - 前端: `npm run build`（TypeScript 检查 + Vite 构建）
