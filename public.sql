/*
 Navicat Premium Dump SQL

 Source Server         : sass
 Source Server Type    : PostgreSQL
 Source Server Version : 170010 (170010)
 Source Host           : 207.57.128.6:5432
 Source Catalog        : contract_db
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 170010 (170010)
 File Encoding         : 65001

 Date: 30/05/2026 23:22:04
*/


-- ----------------------------
-- Sequence structure for audit_logs_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."audit_logs_id_seq";
CREATE SEQUENCE "public"."audit_logs_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for chat_history_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."chat_history_id_seq";
CREATE SEQUENCE "public"."chat_history_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for contracts_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."contracts_id_seq";
CREATE SEQUENCE "public"."contracts_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for customers_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."customers_id_seq";
CREATE SEQUENCE "public"."customers_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for exchange_rates_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."exchange_rates_id_seq";
CREATE SEQUENCE "public"."exchange_rates_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for files_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."files_id_seq";
CREATE SEQUENCE "public"."files_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for payments_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."payments_id_seq";
CREATE SEQUENCE "public"."payments_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for users_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."users_id_seq";
CREATE SEQUENCE "public"."users_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Table structure for alembic_version
-- ----------------------------
DROP TABLE IF EXISTS "public"."alembic_version";
CREATE TABLE "public"."alembic_version" (
  "version_num" varchar(32) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Records of alembic_version
-- ----------------------------

-- ----------------------------
-- Table structure for audit_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."audit_logs";
CREATE TABLE "public"."audit_logs" (
  "user_id" int4,
  "action" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "entity_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "entity_id" int4,
  "old_values" json,
  "new_values" json,
  "ip_address" varchar(45) COLLATE "pg_catalog"."default",
  "user_agent" text COLLATE "pg_catalog"."default",
  "id" int4 NOT NULL DEFAULT nextval('audit_logs_id_seq'::regclass),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "is_deleted" bool DEFAULT false,
  "deleted_at" timestamptz(6)
)
;

-- ----------------------------
-- Records of audit_logs
-- ----------------------------
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 1, '{"contract_number": "HT202605282249464627", "status": "draft", "payments_count": 0, "deleted_files": ["/data/contract-system/contracts/2026/05/HT202605282249464627.pdf"]}', '{}', NULL, NULL, 1, '2026-05-29 00:42:11.691216+00', '2026-05-29 00:42:11.691216+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 1, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 2, '2026-05-29 00:42:16.944274+00', '2026-05-29 00:42:16.944274+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 2, '{"contract_number": "HT202605290843540034", "status": "draft", "payments_count": 0, "deleted_files": ["/data/contract-system/contracts/2026/05/HT202605290843540034.pdf"]}', '{}', NULL, NULL, 3, '2026-05-29 00:54:46.425075+00', '2026-05-29 00:54:46.425075+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 2, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 4, '2026-05-29 00:54:50.438513+00', '2026-05-29 00:54:50.438513+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 4, '{"contract_number": "HT20260529103425145B", "status": "active", "payments_count": 0, "deleted_files": ["/data/contract-system/contracts/2026/05/HT20260529103425145B.pdf"]}', '{}', NULL, NULL, 5, '2026-05-29 08:08:03.819558+00', '2026-05-29 08:08:03.819558+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 3, '{"contract_number": "HT202605290902076221", "status": "active", "payments_count": 1, "deleted_files": ["/data/contract-system/contracts/2026/05/HT202605290902076221.pdf"]}', '{}', NULL, NULL, 6, '2026-05-29 08:08:06.009701+00', '2026-05-29 08:08:06.009701+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 3, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 7, '2026-05-29 08:08:09.640391+00', '2026-05-29 08:08:09.640391+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 1, '{"contract_id": 3, "amount": 50000.0, "currency": "HKD", "status": "pending_voucher", "deleted_file": null}', '{}', NULL, NULL, 8, '2026-05-29 08:47:51.735102+00', '2026-05-29 08:47:51.735102+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 2, '{"contract_id": 5, "amount": 50000.0, "currency": "HKD", "status": "pending_voucher", "deleted_file": null}', '{}', NULL, NULL, 9, '2026-05-29 08:57:25.077385+00', '2026-05-29 08:57:25.077385+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 3, '{"contract_id": 5, "amount": 200000.0, "currency": "HKD", "status": "pending_voucher", "deleted_file": null}', '{}', NULL, NULL, 10, '2026-05-29 08:57:27.487792+00', '2026-05-29 08:57:27.487792+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 5, '{"contract_number": "HT20260529164853190C", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT20260529164853190C.pdf"]}', '{}', NULL, NULL, 11, '2026-05-29 08:57:37.137351+00', '2026-05-29 08:57:37.137351+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 4, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 12, '2026-05-29 08:57:40.468652+00', '2026-05-29 08:57:40.468652+00', 'f', NULL);

-- ----------------------------
-- Table structure for chat_history
-- ----------------------------
DROP TABLE IF EXISTS "public"."chat_history";
CREATE TABLE "public"."chat_history" (
  "user_id" int4,
  "session_id" varchar(100) COLLATE "pg_catalog"."default",
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "question" text COLLATE "pg_catalog"."default" NOT NULL,
  "answer" text COLLATE "pg_catalog"."default",
  "context_contracts" json,
  "intent_type" varchar(50) COLLATE "pg_catalog"."default",
  "extracted_entities" json,
  "sql_query" text COLLATE "pg_catalog"."default",
  "llm_model" varchar(50) COLLATE "pg_catalog"."default",
  "tokens_used" int4,
  "confidence" numeric(5,4),
  "tool_calls" json,
  "metadata" json,
  "id" int4 NOT NULL DEFAULT nextval('chat_history_id_seq'::regclass),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "is_deleted" bool DEFAULT false,
  "deleted_at" timestamptz(6)
)
;

-- ----------------------------
-- Records of chat_history
-- ----------------------------
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'assistant', '', '找到了！系统中其实已经有一位 **胡少棟**（注意是"棟"不是"栋"），电话号码是 **97857999**，名下已有 **1份合同**。

看来是同一位客户，只是名字写法略有不同（栋 vs 棟）。我查一下他现有的合同情况。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_9dzkZZjpGcENt87BrTr50247", "type": "function", "function": {"name": "get_customer_contracts", "arguments": "{\"customer_id\": 5}"}}]', '{}', 187, '2026-05-29 09:39:36.479226+00', '2026-05-29 09:39:36.479226+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'user', '请分析上传的图片内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "104c1543-3863-4d5b-b0a0-393a75ec872e", "file_type": "image"}], "file_context": "[image \u6587\u4ef6\u5206\u6790\u7ed3\u679c] file_id=104c1543-3863-4d5b-b0a0-393a75ec872e\n{\"document_type\": \"\u6536\u636e\", \"summary\": \"\u8fd9\u662f\u4e00\u5f20\u7531\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\u51fa\u5177\u7684\u6536\u636e\uff0c\u8bb0\u5f55\u4e86\u80e1\u5c11\u680b\u5148\u751f\u4e8e2026\u5e745\u670828\u65e5\u652f\u4ed8\u7684\u6b3e\u9879\u3002\u8be5\u6b3e\u9879\u4e3a50000\u6e2f\u5e01\uff08\u5927\u5199\uff1a\u4f0d\u4e07\u5143\u6574\uff09\uff0c\u7528\u4e8e\u652f\u4ed830\u7cfb\u57c3\u5c14\u6cd5\u5b9a\u91d1\uff0c\u4ed8\u6b3e\u65b9\u5f0f\u4e3a\u652f\u7968\u3002\u5907\u6ce8\u4e2d\u63d0\u53ca\u8be5\u7b14\u6b3e\u9879\u5bf9\u5e9430\u7cfb\u57c3\u5c14\u6cd5\u8f66\u578b\uff0c\u7f16\u53f7GGH30-0016495\uff0c\u603b\u4ef7\u4e3a\u6e2f\u5e0125\u4e07\u5143\u3002\u6536\u636e\u7531\u6536\u6b3e\u4eba\u9648\u7115\u660e\u7b7e\u6536\uff0c\u5e76\u52a0\u76d6\u516c\u53f8\u516c\u7ae0\u3002\", \"key_info\": {\"amounts\": [\"50000\uff08\u5c0f\u5199\uff09\", \"\u4f0d\u4e07\u5143\u6574\uff08\u5927\u5199\uff09\", \"\u6e2f\u5e01\uff1a25\u4e07\uff08\u603b\u4ef7\uff09\"], \"dates\": [\"2026\u5e745\u670828\u65e5\"], \"names\": [\"\u80e1\u5c11\u680b\", \"\u9648\u7115\u660e\", \"\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\"], \"reference_numbers\": [\"00000213\", \"GGH30-0016495\"]}, \"confidence\": 0.95}"}', 174, '2026-05-29 09:32:33.127625+00', '2026-05-29 09:32:33.127625+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'assistant', '', '好的，我来分析这张图片的内容。这是一张**收据**，我来为您提取关键信息：

---

## 📄 文件分析结果

**文件类型：** 收据（华星资源开发有限公司出具）

### 关键信息

| 项目 | 内容 |
|------|------|
| **客户姓名** | 胡少栋 |
| **付款日期** | 2026年5月28日 |
| **付款金额** | **50,000 HKD**（伍万元整） |
| **付款方式** | 支票 |
| **用途** | 30系埃尔法定金 |
| **车型/编号** | 30系埃尔法，编号 GGH30-0016495 |
| **车辆总价** | 250,000 HKD（港币25万元） |
| **收据编号** | 00000213 |
| **收款人** | 陈焕明 |

### 总结
这是一张**定金收据**，胡少栋先生为购买30系埃尔法（总价25万港币）支付了**5万港币定金**，付款方式为支票。

---

请问您需要我基于这张收据进行什么操作？比如：
1. **查找已有客户和合同**，将这笔付款关联进去？
2. 或者这是新业务，需要**录入合同和客户信息**？', NULL, NULL, NULL, NULL, 'deepseek-chat', 4853, NULL, 'null', '{}', 175, '2026-05-29 09:33:04.984359+00', '2026-05-29 09:33:04.984359+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'user', '1', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 176, '2026-05-29 09:33:21.309006+00', '2026-05-29 09:33:21.309006+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'assistant', '', '好的，我先来查找一下客户"胡少栋"是否已经在系统中有记录。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_m3palzM9H3uKp64IsPA50450", "type": "function", "function": {"name": "search_customers", "arguments": "{\"name\": \"\u80e1\u5c11\u680b\"}"}}]', '{}', 177, '2026-05-29 09:33:22.631908+00', '2026-05-29 09:33:22.631908+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'tool', '', '{"customers": [], "total": 0}', NULL, 'search_customers', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_m3palzM9H3uKp64IsPA50450"}', 178, '2026-05-29 09:33:22.64033+00', '2026-05-29 09:33:22.64033+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'assistant', '', '系统中还没有"胡少栋"这位客户的信息。这是一笔新业务，我来帮您录入。

首先，我需要确认一下信息：

**客户信息：**
- 姓名：胡少栋
- 电话/证件号：收据上没有显示，您能提供他的联系电话吗？

**合同信息：**
- 业务类型：买港车（30系埃尔法）
- 总价：250,000 HKD
- 已付定金：50,000 HKD（支票支付，2026年5月28日）
- 签订日期：收据日期是2026年5月28日，合同也是这天签的吗？

请您先提供一下胡少栋的联系电话，这样我就可以开始创建客户和合同了。', NULL, NULL, NULL, NULL, 'deepseek-chat', 10021, NULL, 'null', '{}', 179, '2026-05-29 09:33:24.7535+00', '2026-05-29 09:33:24.7535+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'user', '胡少栋，我们目前有这个客户吗？', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 180, '2026-05-29 09:39:16.761471+00', '2026-05-29 09:39:16.761471+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'assistant', '', '我刚才已经查过了，系统中**没有找到"胡少栋"这位客户**的记录，所以他是新客户，需要新建。

请问您能提供他的**联系电话**吗？这样我就可以开始创建客户信息，然后录入合同和付款记录了。', NULL, NULL, NULL, NULL, 'deepseek-chat', 5165, NULL, 'null', '{}', 181, '2026-05-29 09:39:17.996135+00', '2026-05-29 09:39:17.996135+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'user', '那我们目前有哪些客户？你帮我看一下。', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 182, '2026-05-29 09:39:31.252722+00', '2026-05-29 09:39:31.252722+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'assistant', '', '好的，我来查一下系统里现有的客户列表。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_HZ4tXjqXALGxhNAv4fXN5342", "type": "function", "function": {"name": "search_customers", "arguments": "{\"limit\": 20}"}}]', '{}', 183, '2026-05-29 09:39:32.586465+00', '2026-05-29 09:39:32.586465+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'tool', '', '{"error": "请至少提供一个搜索条件（name/phone/wechat_group）"}', NULL, 'search_customers', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_HZ4tXjqXALGxhNAv4fXN5342"}', 184, '2026-05-29 09:39:32.602341+00', '2026-05-29 09:39:32.602341+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'assistant', '', '系统需要搜索条件才能查询，我换个方式，先看看有没有姓"胡"的客户，或者您想看看其他名字的客户？', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_PVkTPZGEyOksyoIUHMVH8130", "type": "function", "function": {"name": "search_customers", "arguments": "{\"name\": \"\u80e1\", \"limit\": 20}"}}]', '{}', 185, '2026-05-29 09:39:34.07108+00', '2026-05-29 09:39:34.07108+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'tool', '', '{"customers": [{"id": 5, "name": "胡少棟", "contact_person": null, "phone": "97857999", "wechat_group_name": null, "contract_count": 1}], "total": 1}', NULL, 'search_customers', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_PVkTPZGEyOksyoIUHMVH8130"}', 186, '2026-05-29 09:39:34.820846+00', '2026-05-29 09:39:34.820846+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'user', '可以的，你帮我完成一下', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 202, '2026-05-29 10:10:00.317362+00', '2026-05-29 10:10:00.317362+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'assistant', '', '好的，我来将这份收据关联到该付款记录，确认入账。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_q7k0Scd63sbUMKPYd5Jw9377", "type": "function", "function": {"name": "confirm_payment", "arguments": "{\"payment_id\": 4, \"file_id\": \"fbdadb77-0e22-42b9-b95b-50c58623f24d\"}"}}]', '{}', 203, '2026-05-29 10:10:01.609651+00', '2026-05-29 10:10:01.609651+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'tool', '', '{"success": true, "payment": {"id": 4, "contract_id": 6, "installment_number": 1, "installment_name": null, "currency": "HKD", "amount": 50000.0, "paid_amount": 50000.0, "exchange_rate": 0.8712, "amount_in_cny": 43560.0, "paid_amount_in_cny": 43560.0, "due_date": null, "paid_date": "2026-05-28", "payment_method": "unknown", "status": "paid", "notes": "定金，合同约定已付，暂无凭证", "contract_number": "HT20260529165822976E", "customer_name": "胡少棟"}}', NULL, 'confirm_payment', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_q7k0Scd63sbUMKPYd5Jw9377"}', 204, '2026-05-29 10:10:01.64619+00', '2026-05-29 10:10:01.64619+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'tool', '', '{"contracts": [{"id": 6, "contract_number": "HT20260529165822976E", "title": "车辆买卖合约（香港）", "business_type": "车辆业务", "business_description": "购买丰田车辆（底盘号GGH30-0016495）", "customer_name": "胡少棟", "currency": "HKD", "total_amount": 250000.0, "paid_amount": 0, "remaining_amount": 250000.0, "total_amount_in_cny": null, "paid_amount_in_cny": 0, "status": "active", "wechat_group": null, "signed_date": "2026-05-28", "end_date": null, "payment_stats": {"total": 1, "paid": 0, "pending_voucher": 1}}], "total": 1}', NULL, 'get_customer_contracts', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_9dzkZZjpGcENt87BrTr50247"}', 188, '2026-05-29 09:39:36.48688+00', '2026-05-29 09:39:36.48688+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '9afbcb53-6013-49e8-8ab3-3e25e375f590', 'assistant', '', '已经找到了！情况是这样的：

**客户：胡少棟**（电话：97857999）
- 系统中已有 **1份合同**（合同编号：HT20260529165822976E）
- 合同内容：购买丰田车辆（底盘号GGH30-0016495），总价 **250,000 HKD**
- 签订日期：2026年5月28日
- 目前已有 **1笔待凭证的付款记录**（应该是之前录入的定金）

看来之前已经有人录入了这份合同和定金记录，但还没有上传凭证确认。现在您上传了这张收据，正好可以作为凭证来确认这笔付款！

需要我帮您**将这张收据关联到这笔待凭证的付款记录**，完成确认入账吗？', NULL, NULL, NULL, NULL, 'deepseek-chat', 22014, NULL, 'null', '{}', 189, '2026-05-29 09:39:39.074558+00', '2026-05-29 09:39:39.074558+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'user', '请分析上传的图片内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "fbdadb77-0e22-42b9-b95b-50c58623f24d", "file_type": "image"}], "file_context": "[image \u6587\u4ef6\u5206\u6790\u7ed3\u679c] file_id=fbdadb77-0e22-42b9-b95b-50c58623f24d\n{\"document_type\": \"\u6536\u636e\", \"summary\": \"\u8be5\u6587\u4ef6\u4e3a\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\u51fa\u5177\u7684\u6536\u636e\uff0c\u8bb0\u5f55\u4e86\u80e1\u5c11\u680b\u5148\u751f\u4e8e2026\u5e745\u670828\u65e5\u652f\u4ed8\u7684\u6b3e\u9879\u3002\u6536\u6b3e\u91d1\u989d\u4e3a\u6e2f\u5e0150,000\u5143\uff08\u5927\u5199\uff1a\u4f0d\u4e07\u5143\u6574\uff09\uff0c\u4ed8\u6b3e\u65b9\u5f0f\u4e3a\u652f\u7968\uff0c\u6b3e\u9879\u7528\u9014\u4e3a30\u7cfb\u57c3\u5c14\u6cd5\u5b9a\u91d1\u3002\u5907\u6ce8\u4e2d\u63d0\u53ca\u8be5\u7269\u54c1\u7f16\u53f7\u4e3aGGH30-0016495\uff0c\u603b\u4ef7\u4e3a\u6e2f\u5e0125\u4e07\u5143\u3002\u6536\u6b3e\u4eba\u4e3a\u9648\u7115\u660e\uff0c\u5e76\u52a0\u76d6\u4e86\u516c\u53f8\u516c\u7ae0\u3002\", \"key_info\": {\"amounts\": [\"50000\uff08\u5c0f\u5199\uff09\", \"\u4f0d\u4e07\u5143\u6574\uff08\u5927\u5199\uff09\", \"\u6e2f\u5e01\uff1a25\u4e07\uff08\u603b\u4ef7\uff09\"], \"dates\": [\"2026\u5e745\u670828\u65e5\"], \"names\": [\"\u80e1\u5c11\u680b\", \"\u9648\u7115\u660e\", \"\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\"], \"reference_numbers\": [\"00000213\", \"GGH30-0016495\"]}, \"confidence\": 0.95}"}', 190, '2026-05-29 10:08:47.63667+00', '2026-05-29 10:08:47.63667+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'assistant', '', '好的，我已经分析了您上传的图片，这是一份**收据**，不是合同文件。让我为您总结提取到的关键信息：

---

## 📄 文件分析结果

**文件类型：** 收据（华星资源开发有限公司出具）

**关键信息：**

| 项目 | 内容 |
|------|------|
| **客户姓名** | 胡少栋 |
| **付款日期** | 2026年5月28日 |
| **付款金额** | **50,000 HKD**（伍万元整） |
| **付款方式** | 支票 |
| **款项用途** | 30系埃尔法定金 |
| **车辆编号** | GGH30-0016495 |
| **车辆总价** | 250,000 HKD |
| **收据编号** | 00000213 |
| **收款人** | 陈焕明 |

---

这是一份**付款凭证（收据）**，记录了胡少栋先生支付了 **50,000 HKD** 作为30系埃尔法的定金。

请问您希望我如何处理这份收据？比如：
1. **查找已有合同并关联这笔付款** — 我可以在系统中搜索客户"胡少栋"的合同记录
2. **其他操作** — 请告诉我您的需求', NULL, NULL, NULL, NULL, 'deepseek-chat', 5059, NULL, 'null', '{}', 191, '2026-05-29 10:09:17.626489+00', '2026-05-29 10:09:17.626489+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'user', '1', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 192, '2026-05-29 10:09:30.165097+00', '2026-05-29 10:09:30.165097+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'assistant', '', '好的，我先在系统中搜索客户"胡少栋"的信息。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_kIjyls8De0Iy0odkiDUr2469", "type": "function", "function": {"name": "search_customers", "arguments": "{\"name\": \"\u80e1\u5c11\u680b\"}"}}]', '{}', 193, '2026-05-29 10:09:31.192409+00', '2026-05-29 10:09:31.192409+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'tool', '', '{"customers": [{"id": 5, "name": "胡少棟", "contact_person": null, "phone": "97857999", "wechat_group_name": null, "contract_count": 1}], "total": 1}', NULL, 'search_customers', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_kIjyls8De0Iy0odkiDUr2469"}', 194, '2026-05-29 10:09:31.200574+00', '2026-05-29 10:09:31.200574+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'assistant', '', '找到了！系统中已有客户 **胡少棟**（繁体），与收据上的"胡少栋"是同一人。该客户有1份合同，让我查看合同详情。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_uNJU5be9cH95ErMgl3ij9076", "type": "function", "function": {"name": "get_customer_contracts", "arguments": "{\"customer_id\": 5}"}}]', '{}', 195, '2026-05-29 10:09:32.755337+00', '2026-05-29 10:09:32.755337+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'tool', '', '{"contracts": [{"id": 6, "contract_number": "HT20260529165822976E", "title": "车辆买卖合约（香港）", "business_type": "车辆业务", "business_description": "购买丰田车辆（底盘号GGH30-0016495）", "customer_name": "胡少棟", "currency": "HKD", "total_amount": 250000.0, "paid_amount": 0, "remaining_amount": 250000.0, "total_amount_in_cny": null, "paid_amount_in_cny": 0, "status": "active", "wechat_group": null, "signed_date": "2026-05-28", "end_date": null, "payment_stats": {"total": 1, "paid": 0, "pending_voucher": 1}}], "total": 1}', NULL, 'get_customer_contracts', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_uNJU5be9cH95ErMgl3ij9076"}', 196, '2026-05-29 10:09:32.761273+00', '2026-05-29 10:09:32.761273+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'assistant', '', '找到了！客户 **胡少棟** 有一份执行中的合同：

**合同编号：** HT20260529165822976E
**业务类型：** 车辆业务 — 购买丰田车辆（底盘号GGH30-0016495）
**总价：** 250,000 HKD
**已付金额：** 0 HKD

系统显示该合同已有 **1笔待凭证（pending_voucher）** 的付款记录，应该就是之前录入合同时创建的定金记录。让我查看详情。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_cHEbi6IvkFuwv87ZxEER3858", "type": "function", "function": {"name": "get_contract_detail", "arguments": "{\"contract_id\": 6}"}}]', '{}', 197, '2026-05-29 10:09:34.777476+00', '2026-05-29 10:09:34.777476+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'tool', '', '{"error": "工具执行失败: Object of type Decimal is not JSON serializable"}', NULL, 'get_contract_detail', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_cHEbi6IvkFuwv87ZxEER3858"}', 198, '2026-05-29 10:09:34.797621+00', '2026-05-29 10:09:34.797621+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'assistant', '', '', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_39ux9uNK2rtr3kj1OGnk4173", "type": "function", "function": {"name": "query_payments", "arguments": "{\"contract_id\": 6}"}}]', '{}', 199, '2026-05-29 10:09:35.877082+00', '2026-05-29 10:09:35.877082+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'tool', '', '{"payments": [{"id": 4, "contract_id": 6, "installment_number": 1, "installment_name": null, "currency": "HKD", "amount": 50000.0, "paid_amount": 0, "exchange_rate": 0.8712, "amount_in_cny": 43560.0, "paid_amount_in_cny": null, "due_date": null, "paid_date": "2026-05-28", "payment_method": "unknown", "status": "pending_voucher", "notes": "定金，合同约定已付，暂无凭证", "contract_number": "HT20260529165822976E", "customer_name": "胡少棟"}], "total": 1}', NULL, 'query_payments', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_39ux9uNK2rtr3kj1OGnk4173"}', 200, '2026-05-29 10:09:35.883212+00', '2026-05-29 10:09:35.883212+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'assistant', '', '完全匹配！系统中已有一笔 **待凭证（pending_voucher）** 的付款记录：

- **第1期（定金）：** 50,000 HKD（折合 43,560 CNY）
- **付款日期：** 2026-05-28
- **状态：** 待凭证（已付款但未上传凭证）

现在您上传了这份收据，我可以帮您**确认这笔付款**，将收据关联到该记录，使其正式入账。要这样做吗？', NULL, NULL, NULL, NULL, 'deepseek-chat', 27731, NULL, 'null', '{}', 201, '2026-05-29 10:09:37.695375+00', '2026-05-29 10:09:37.695375+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, 'f169fe0a-3567-4ce3-90c1-8fee26b4445d', 'assistant', '', '✅ **已完成！** 付款确认成功，详情如下：

---

**客户：** 胡少棟
**合同：** HT20260529165822976E（购买丰田车辆 GGH30-0016495）

| 项目 | 内容 |
|------|------|
| **期数** | 第1期（定金） |
| **金额** | 50,000 HKD |
| **折合人民币** | 43,560 CNY |
| **付款日期** | 2026年5月28日 |
| **状态** | ✅ **已确认入账（paid）** |
| **收据** | 已关联至该付款记录 |

**合同付款进度更新：**
- 总价：250,000 HKD
- 已付：50,000 HKD（折合 43,560 CNY）
- 待付：200,000 HKD

请问还有其他需要帮忙的吗？', NULL, NULL, NULL, NULL, 'deepseek-chat', 12577, NULL, 'null', '{}', 205, '2026-05-29 10:10:03.711732+00', '2026-05-29 10:10:03.711732+00', 'f', NULL);

-- ----------------------------
-- Table structure for contracts
-- ----------------------------
DROP TABLE IF EXISTS "public"."contracts";
CREATE TABLE "public"."contracts" (
  "contract_number" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(500) COLLATE "pg_catalog"."default",
  "customer_id" int4,
  "sales_person_id" int4 NOT NULL,
  "currency" varchar(3) COLLATE "pg_catalog"."default" NOT NULL,
  "total_amount" numeric(15,2) NOT NULL,
  "paid_amount" numeric(15,2) NOT NULL,
  "remaining_amount" numeric(15,2),
  "total_amount_in_cny" numeric(15,2),
  "paid_amount_in_cny" numeric(15,2),
  "remaining_amount_in_cny" numeric(15,2),
  "original_file_path" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "file_hash" varchar(64) COLLATE "pg_catalog"."default",
  "contract_data" json NOT NULL DEFAULT '{}'::json,
  "confidence" numeric(5,4),
  "needs_review" bool,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "signed_date" date,
  "start_date" date,
  "end_date" date,
  "remarks" text COLLATE "pg_catalog"."default",
  "created_by" int4,
  "id" int4 NOT NULL DEFAULT nextval('contracts_id_seq'::regclass),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "is_deleted" bool DEFAULT false,
  "deleted_at" timestamptz(6),
  "business_type" varchar(50) COLLATE "pg_catalog"."default",
  "business_description" varchar(200) COLLATE "pg_catalog"."default",
  "wechat_group" varchar(200) COLLATE "pg_catalog"."default",
  "total_expense" numeric(15,2) DEFAULT 0,
  "total_expense_in_cny" numeric(15,2) DEFAULT 0
)
;

-- ----------------------------
-- Records of contracts
-- ----------------------------
INSERT INTO "public"."contracts" VALUES ('HT202605282249464627', '车辆买卖合约（香港）', 1, 1, 'HKD', 250000.00, 0.00, 250000.00, NULL, 0.00, 0.00, '2026/05/HT202605282249464627.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "30e74365-0d7f-46f3-875f-eca205068435", "business_type": "\u4e70\u6e2f\u8f66"}', NULL, 'f', 'draft', '2026-05-28', NULL, NULL, NULL, 1, 1, '2026-05-28 14:49:46.789768+00', '2026-05-29 00:42:11.667+00', 't', '2026-05-29 00:42:11.683734+00', '买港车', NULL, NULL, 0.00, 0.00);
INSERT INTO "public"."contracts" VALUES ('HT202605290843540034', '车辆买卖合约（香港）', 2, 1, 'HKD', 250000.00, 0.00, 250000.00, NULL, 0.00, NULL, '2026/05/HT202605290843540034.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "6244290a-41f3-4068-81a5-88218e934c7f", "business_type": "\u8f66\u8f86\u4e1a\u52a1", "business_description": "\u8d2d\u4e70\u8f66\u8f86\uff0c\u8f66\u8eab\u5e95\u76d8\u53f7\u7801GGH30-0016495"}', NULL, 'f', 'draft', '2026-05-28', NULL, NULL, NULL, 1, 2, '2026-05-29 00:43:54.818038+00', '2026-05-29 00:54:46.416302+00', 't', '2026-05-29 00:54:46.421665+00', '车辆业务', '购买车辆，车身底盘号码GGH30-0016495', NULL, 0.00, 0.00);
INSERT INTO "public"."contracts" VALUES ('HT20260529165822976E', '车辆买卖合约（香港）', 5, 1, 'HKD', 250000.00, 50000.00, 200000.00, NULL, 43560.00, -43560.00, '2026/05/HT20260529165822976E.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "443df660-2cf1-4972-b848-f17844bb999f", "business_type": "\u8f66\u8f86\u4e1a\u52a1", "business_description": "\u8d2d\u4e70\u4e30\u7530\u8f66\u8f86\uff08\u5e95\u76d8\u53f7GGH30-0016495\uff09"}', NULL, 'f', 'active', '2026-05-28', NULL, NULL, NULL, 1, 6, '2026-05-29 08:58:22.832073+00', '2026-05-29 10:10:01.616941+00', 'f', NULL, '车辆业务', '购买丰田车辆（底盘号GGH30-0016495）', NULL, 0.00, 0.00);
INSERT INTO "public"."contracts" VALUES ('HT20260529103425145B', '两地车牌指标过户服务合约', 3, 1, 'CNY', 240000.00, 0.00, 240000.00, NULL, 0.00, NULL, '2026/05/HT20260529103425145B.pdf', '33ee97e02357ecc6a802f0c70c4d20e300c7683d59a4920e147e519f06193e52', '{"source": "agent", "file_id": "96e39fc9-b8c1-4f34-8042-1a10d49720a6", "business_type": "\u4e2d\u6e2f\u724c\u4e1a\u52a1", "business_description": "\u529e\u7406\u6df1\u5733\u6e7e\u53e3\u5cb8\u4e24\u5730\u8f66\u724c\u6307\u6807\u8fc7\u6237\uff0c\u8f66\u724c\u53f7\uff1a\u7ca4Z7N80\u6e2f"}', NULL, 'f', 'active', '2026-05-28', NULL, NULL, NULL, 1, 4, '2026-05-29 02:34:25.83356+00', '2026-05-29 08:08:03.799657+00', 't', '2026-05-29 08:08:03.80766+00', '中港牌业务', '办理深圳湾口岸两地车牌指标过户，车牌号：粤Z7N80港', NULL, 0.00, 0.00);
INSERT INTO "public"."contracts" VALUES ('HT202605290902076221', '车辆买卖合约（香港）', 3, 1, 'HKD', 250000.00, 0.00, 250000.00, NULL, 0.00, NULL, '2026/05/HT202605290902076221.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "70b18c5a-8807-4571-8bc2-f27b8711c191", "business_type": "\u8f66\u8f86\u4e1a\u52a1", "business_description": "\u8d2d\u4e70\u8f66\u8f86\uff08\u5e95\u76d8\u53f7\uff1aGGH30-0016495\uff09\uff0c\u603b\u4ef7250,000 HKD\uff0c\u5df2\u4ed8\u5b9a\u91d150,000 HKD\uff0c\u5c3e\u6b3e200,000 HKD"}', NULL, 'f', 'active', '2026-05-28', NULL, NULL, NULL, 1, 3, '2026-05-29 01:02:07.386264+00', '2026-05-29 08:08:05.979261+00', 't', '2026-05-29 08:08:05.9906+00', '车辆业务', '购买车辆（底盘号：GGH30-0016495），总价250,000 HKD，已付定金50,000 HKD，尾款200,000 HKD', '5月28日17年白外黑内30系埃尔法(10)', 0.00, 0.00);

-- ----------------------------
-- Table structure for customers
-- ----------------------------
DROP TABLE IF EXISTS "public"."customers";
CREATE TABLE "public"."customers" (
  "name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "contact_person" varchar(100) COLLATE "pg_catalog"."default",
  "phone" varchar(20) COLLATE "pg_catalog"."default",
  "email" varchar(100) COLLATE "pg_catalog"."default",
  "id_card_number_encrypted" text COLLATE "pg_catalog"."default",
  "business_license" varchar(50) COLLATE "pg_catalog"."default",
  "address" text COLLATE "pg_catalog"."default",
  "wechat_group_name" varchar(200) COLLATE "pg_catalog"."default",
  "remarks" text COLLATE "pg_catalog"."default",
  "created_by" int4,
  "id" int4 NOT NULL DEFAULT nextval('customers_id_seq'::regclass),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "is_deleted" bool DEFAULT false,
  "deleted_at" timestamptz(6)
)
;

-- ----------------------------
-- Records of customers
-- ----------------------------
INSERT INTO "public"."customers" VALUES ('胡少棟', NULL, '97857999', NULL, 'RjQyMDgyNSg3KQ==', NULL, NULL, NULL, NULL, 1, 1, '2026-05-28 14:02:25.221717+00', '2026-05-29 00:42:16.91735+00', 't', '2026-05-29 00:42:16.933922+00');
INSERT INTO "public"."customers" VALUES ('胡少棟', NULL, '97857999', NULL, 'RjQyMDgyNSg3KQ==', NULL, NULL, NULL, NULL, 1, 2, '2026-05-29 00:43:51.767493+00', '2026-05-29 00:54:50.431708+00', 't', '2026-05-29 00:54:50.435356+00');
INSERT INTO "public"."customers" VALUES ('胡少棟', NULL, '97857999', NULL, 'RjQyMDgyNSg3KQ==', NULL, NULL, NULL, NULL, 1, 3, '2026-05-29 01:02:03.715637+00', '2026-05-29 08:08:09.61206+00', 't', '2026-05-29 08:08:09.630766+00');
INSERT INTO "public"."customers" VALUES ('胡少棟', NULL, '97857999', NULL, 'RjQyMDgyNSg3KQ==', NULL, NULL, NULL, NULL, 1, 5, '2026-05-29 08:58:20.074385+00', '2026-05-29 08:58:20.074385+00', 'f', NULL);

-- ----------------------------
-- Table structure for exchange_rates
-- ----------------------------
DROP TABLE IF EXISTS "public"."exchange_rates";
CREATE TABLE "public"."exchange_rates" (
  "from_currency" varchar(3) COLLATE "pg_catalog"."default" NOT NULL,
  "to_currency" varchar(3) COLLATE "pg_catalog"."default" NOT NULL,
  "rate" numeric(10,6) NOT NULL,
  "rate_date" date NOT NULL,
  "source" varchar(20) COLLATE "pg_catalog"."default",
  "is_active" bool,
  "remarks" text COLLATE "pg_catalog"."default",
  "created_by" int4,
  "id" int4 NOT NULL DEFAULT nextval('exchange_rates_id_seq'::regclass),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "is_deleted" bool DEFAULT false,
  "deleted_at" timestamptz(6)
)
;

-- ----------------------------
-- Records of exchange_rates
-- ----------------------------
INSERT INTO "public"."exchange_rates" VALUES ('HKD', 'CNY', 0.871200, '2026-05-28', 'boc', 't', NULL, NULL, 1, '2026-05-28 14:16:43.610498+00', '2026-05-28 14:16:43.610498+00', 'f', NULL);
INSERT INTO "public"."exchange_rates" VALUES ('USD', 'CNY', 6.824000, '2026-05-28', 'boc', 't', NULL, NULL, 2, '2026-05-28 14:16:45.681841+00', '2026-05-28 14:16:45.681841+00', 'f', NULL);

-- ----------------------------
-- Table structure for files
-- ----------------------------
DROP TABLE IF EXISTS "public"."files";
CREATE TABLE "public"."files" (
  "original_filename" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "stored_filename" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "file_path" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "file_size" int8 NOT NULL,
  "mime_type" varchar(100) COLLATE "pg_catalog"."default",
  "file_hash" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "related_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "related_id" int4 NOT NULL,
  "ocr_text" text COLLATE "pg_catalog"."default",
  "ocr_confidence" numeric(5,4),
  "ai_extracted_data" json DEFAULT '{}'::json,
  "uploaded_by" int4,
  "id" int4 NOT NULL DEFAULT nextval('files_id_seq'::regclass),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "is_deleted" bool DEFAULT false,
  "deleted_at" timestamptz(6)
)
;

-- ----------------------------
-- Records of files
-- ----------------------------

-- ----------------------------
-- Table structure for payments
-- ----------------------------
DROP TABLE IF EXISTS "public"."payments";
CREATE TABLE "public"."payments" (
  "contract_id" int4 NOT NULL,
  "installment_number" int4 NOT NULL,
  "installment_name" varchar(50) COLLATE "pg_catalog"."default",
  "currency" varchar(3) COLLATE "pg_catalog"."default" NOT NULL,
  "amount" numeric(15,2) NOT NULL,
  "paid_amount" numeric(15,2),
  "exchange_rate" numeric(10,6),
  "amount_in_cny" numeric(15,2),
  "paid_amount_in_cny" numeric(15,2),
  "due_date" date,
  "paid_date" date,
  "receipt_image_path" varchar(500) COLLATE "pg_catalog"."default",
  "receipt_file_hash" varchar(64) COLLATE "pg_catalog"."default",
  "receipt_ocr_text" text COLLATE "pg_catalog"."default",
  "payment_method" varchar(20) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "source" varchar(20) COLLATE "pg_catalog"."default",
  "notes" text COLLATE "pg_catalog"."default",
  "created_by" int4,
  "id" int4 NOT NULL DEFAULT nextval('payments_id_seq'::regclass),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "is_deleted" bool DEFAULT false,
  "deleted_at" timestamptz(6),
  "type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'income'::character varying,
  "payee_name" varchar(200) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Records of payments
-- ----------------------------
INSERT INTO "public"."payments" VALUES (6, 1, NULL, 'HKD', 50000.00, 50000.00, 0.871200, 43560.00, 43560.00, NULL, '2026-05-28', '6_1_8d452612.jpg', NULL, NULL, 'unknown', 'paid', 'manual', '定金，合同约定已付，暂无凭证', 1, 4, '2026-05-29 08:58:24.690648+00', '2026-05-29 10:10:01.616941+00', 'f', NULL, 'income', NULL);

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS "public"."users";
CREATE TABLE "public"."users" (
  "username" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "password_hash" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "email" varchar(100) COLLATE "pg_catalog"."default",
  "full_name" varchar(100) COLLATE "pg_catalog"."default",
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "department" varchar(50) COLLATE "pg_catalog"."default",
  "is_active" bool,
  "last_login_at" timestamptz(6),
  "id" int4 NOT NULL DEFAULT nextval('users_id_seq'::regclass),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "is_deleted" bool DEFAULT false,
  "deleted_at" timestamptz(6)
)
;

-- ----------------------------
-- Records of users
-- ----------------------------
INSERT INTO "public"."users" VALUES ('admin', '$2b$12$oPTewLgAsUrRRfXbFWqUVeuzqXODoDIsRMCKpLe1mVZQB1GvnYm6W', NULL, '系统管理员', 'admin', NULL, 't', '2026-05-30 14:02:55.529694+00', 1, '2026-05-27 13:45:21.413514+00', '2026-05-30 14:02:55.216928+00', 'f', NULL);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."audit_logs_id_seq"
OWNED BY "public"."audit_logs"."id";
SELECT setval('"public"."audit_logs_id_seq"', 12, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."chat_history_id_seq"
OWNED BY "public"."chat_history"."id";
SELECT setval('"public"."chat_history_id_seq"', 205, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."contracts_id_seq"
OWNED BY "public"."contracts"."id";
SELECT setval('"public"."contracts_id_seq"', 6, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."customers_id_seq"
OWNED BY "public"."customers"."id";
SELECT setval('"public"."customers_id_seq"', 5, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."exchange_rates_id_seq"
OWNED BY "public"."exchange_rates"."id";
SELECT setval('"public"."exchange_rates_id_seq"', 2, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."files_id_seq"
OWNED BY "public"."files"."id";
SELECT setval('"public"."files_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."payments_id_seq"
OWNED BY "public"."payments"."id";
SELECT setval('"public"."payments_id_seq"', 4, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."users_id_seq"
OWNED BY "public"."users"."id";
SELECT setval('"public"."users_id_seq"', 1, true);

-- ----------------------------
-- Primary Key structure for table alembic_version
-- ----------------------------
ALTER TABLE "public"."alembic_version" ADD CONSTRAINT "alembic_version_pkc" PRIMARY KEY ("version_num");

-- ----------------------------
-- Primary Key structure for table audit_logs
-- ----------------------------
ALTER TABLE "public"."audit_logs" ADD CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table chat_history
-- ----------------------------
ALTER TABLE "public"."chat_history" ADD CONSTRAINT "chat_history_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table contracts
-- ----------------------------
CREATE INDEX "idx_contracts_business_type" ON "public"."contracts" USING btree (
  "business_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table contracts
-- ----------------------------
ALTER TABLE "public"."contracts" ADD CONSTRAINT "contracts_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Checks structure for table customers
-- ----------------------------
ALTER TABLE "public"."customers" ADD CONSTRAINT "chk_phone_or_email" CHECK (phone IS NOT NULL OR email IS NOT NULL);

-- ----------------------------
-- Primary Key structure for table customers
-- ----------------------------
ALTER TABLE "public"."customers" ADD CONSTRAINT "customers_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table exchange_rates
-- ----------------------------
ALTER TABLE "public"."exchange_rates" ADD CONSTRAINT "uq_currency_date" UNIQUE ("from_currency", "to_currency", "rate_date");

-- ----------------------------
-- Primary Key structure for table exchange_rates
-- ----------------------------
ALTER TABLE "public"."exchange_rates" ADD CONSTRAINT "exchange_rates_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table files
-- ----------------------------
ALTER TABLE "public"."files" ADD CONSTRAINT "uq_file_hash_related" UNIQUE ("file_hash", "related_type", "related_id");

-- ----------------------------
-- Primary Key structure for table files
-- ----------------------------
ALTER TABLE "public"."files" ADD CONSTRAINT "files_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table payments
-- ----------------------------
CREATE INDEX "idx_payments_type" ON "public"."payments" USING btree (
  "type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table payments
-- ----------------------------
ALTER TABLE "public"."payments" ADD CONSTRAINT "uq_contract_installment_type" UNIQUE ("contract_id", "installment_number", "type");

-- ----------------------------
-- Primary Key structure for table payments
-- ----------------------------
ALTER TABLE "public"."payments" ADD CONSTRAINT "payments_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table users
-- ----------------------------
ALTER TABLE "public"."users" ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table audit_logs
-- ----------------------------
ALTER TABLE "public"."audit_logs" ADD CONSTRAINT "audit_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table chat_history
-- ----------------------------
ALTER TABLE "public"."chat_history" ADD CONSTRAINT "chat_history_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table contracts
-- ----------------------------
ALTER TABLE "public"."contracts" ADD CONSTRAINT "contracts_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."contracts" ADD CONSTRAINT "contracts_customer_id_fkey" FOREIGN KEY ("customer_id") REFERENCES "public"."customers" ("id") ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE "public"."contracts" ADD CONSTRAINT "contracts_sales_person_id_fkey" FOREIGN KEY ("sales_person_id") REFERENCES "public"."users" ("id") ON DELETE RESTRICT ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table customers
-- ----------------------------
ALTER TABLE "public"."customers" ADD CONSTRAINT "customers_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "public"."users" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table exchange_rates
-- ----------------------------
ALTER TABLE "public"."exchange_rates" ADD CONSTRAINT "exchange_rates_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table files
-- ----------------------------
ALTER TABLE "public"."files" ADD CONSTRAINT "files_uploaded_by_fkey" FOREIGN KEY ("uploaded_by") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table payments
-- ----------------------------
ALTER TABLE "public"."payments" ADD CONSTRAINT "payments_contract_id_fkey" FOREIGN KEY ("contract_id") REFERENCES "public"."contracts" ("id") ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE "public"."payments" ADD CONSTRAINT "payments_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
