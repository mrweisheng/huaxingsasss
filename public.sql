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

 Date: 02/06/2026 10:20:21
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
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 4, '{"contract_id": 6, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "paid", "deleted_file": "/data/contract-system/receipts/6_1_8d452612.jpg"}', '{}', NULL, NULL, 13, '2026-05-31 01:57:40.812187+00', '2026-05-31 01:57:40.812187+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 6, '{"contract_number": "HT20260529165822976E", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT20260529165822976E.pdf"]}', '{}', NULL, NULL, 14, '2026-05-31 01:57:44.600889+00', '2026-05-31 01:57:44.600889+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 5, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 15, '2026-05-31 01:57:47.771892+00', '2026-05-31 01:57:47.771892+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 7, '{"contract_number": "HT20260531095755CF11", "status": "draft", "deleted_files": ["/data/contract-system/contracts/2026/05/20260531095755_1fe9b2ff.pdf"]}', '{}', NULL, NULL, 16, '2026-05-31 01:59:13.537113+00', '2026-05-31 01:59:13.537113+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 5, '{"contract_id": 8, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "paid", "deleted_file": null}', '{}', NULL, NULL, 17, '2026-05-31 02:17:15.8037+00', '2026-05-31 02:17:15.8037+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 8, '{"contract_number": "HT20260531095951CA74", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT20260531095951CA74.pdf"]}', '{}', NULL, NULL, 18, '2026-05-31 02:17:19.681837+00', '2026-05-31 02:17:19.681837+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 6, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 19, '2026-05-31 02:17:22.881448+00', '2026-05-31 02:17:22.881448+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 6, '{"contract_id": 9, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "paid", "deleted_file": null}', '{}', NULL, NULL, 20, '2026-05-31 02:53:24.110278+00', '2026-05-31 02:53:24.110278+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 9, '{"contract_number": "HT20260531101810A697", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT20260531101810A697.pdf"]}', '{}', NULL, NULL, 21, '2026-05-31 02:53:27.841715+00', '2026-05-31 02:53:27.841715+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 7, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 22, '2026-05-31 02:53:30.530391+00', '2026-05-31 02:53:30.530391+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 7, '{"contract_id": 10, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "paid", "deleted_file": null}', '{}', NULL, NULL, 23, '2026-05-31 03:06:48.995897+00', '2026-05-31 03:06:48.995897+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 10, '{"contract_number": "HT202605311054202746", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT202605311054202746.pdf"]}', '{}', NULL, NULL, 24, '2026-05-31 03:06:53.575923+00', '2026-05-31 03:06:53.575923+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 8, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 25, '2026-05-31 03:06:57.057742+00', '2026-05-31 03:06:57.057742+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 11, '{"contract_number": "HT202605311109044556", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT202605311109044556.pdf"]}', '{}', NULL, NULL, 26, '2026-05-31 05:30:13.289077+00', '2026-05-31 05:30:13.289077+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 9, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 27, '2026-05-31 05:30:21.007491+00', '2026-05-31 05:30:21.007491+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 12, '{"contract_number": "HT2026053113313681B0", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT2026053113313681B0.pdf"]}', '{}', NULL, NULL, 28, '2026-05-31 05:58:06.655488+00', '2026-05-31 05:58:06.655488+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 10, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 29, '2026-05-31 05:58:09.782121+00', '2026-05-31 05:58:09.782121+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 13, '{"contract_number": "HT20260531154141E02D", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT20260531154141E02D.pdf"]}', '{}', NULL, NULL, 30, '2026-05-31 07:46:05.74263+00', '2026-05-31 07:46:05.74263+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 11, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 31, '2026-05-31 07:46:09.142066+00', '2026-05-31 07:46:09.142066+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 14, '{"contract_number": "HT20260531154654179B", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT20260531154654179B.pdf"]}', '{}', NULL, NULL, 32, '2026-05-31 14:13:43.202015+00', '2026-05-31 14:13:43.202015+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 12, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 33, '2026-05-31 14:13:46.215284+00', '2026-05-31 14:13:46.215284+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 8, '{"contract_id": 15, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "pending", "deleted_file": null}', '{}', NULL, NULL, 34, '2026-05-31 14:37:27.60604+00', '2026-05-31 14:37:27.60604+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 15, '{"contract_number": "HT2026053122290961D9", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT2026053122290961D9.pdf"]}', '{}', NULL, NULL, 35, '2026-05-31 14:37:30.912249+00', '2026-05-31 14:37:30.912249+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 13, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 36, '2026-05-31 14:37:34.008335+00', '2026-05-31 14:37:34.008335+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 9, '{"contract_id": 16, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "pending", "deleted_file": null}', '{}', NULL, NULL, 37, '2026-06-01 03:11:18.255355+00', '2026-06-01 03:11:18.255355+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 17, '{"contract_number": "HT202606011002560AC1", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT202606011002560AC1.pdf"]}', '{}', NULL, NULL, 38, '2026-06-01 03:11:21.95884+00', '2026-06-01 03:11:21.95884+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 16, '{"contract_number": "HT202605312238336C7A", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/05/HT202605312238336C7A.pdf"]}', '{}', NULL, NULL, 39, '2026-06-01 03:11:23.961827+00', '2026-06-01 03:11:23.961827+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 14, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 40, '2026-06-01 03:11:26.773709+00', '2026-06-01 03:11:26.773709+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 10, '{"contract_id": 18, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "pending", "deleted_file": null}', '{}', NULL, NULL, 41, '2026-06-01 04:30:05.498147+00', '2026-06-01 04:30:05.498147+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 18, '{"contract_number": "HT20260601111354CD34", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT20260601111354CD34.pdf"]}', '{}', NULL, NULL, 42, '2026-06-01 04:30:09.101647+00', '2026-06-01 04:30:09.101647+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 15, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 43, '2026-06-01 04:30:11.943212+00', '2026-06-01 04:30:11.943212+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 11, '{"contract_id": 19, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "pending", "deleted_file": null}', '{}', NULL, NULL, 44, '2026-06-01 06:51:26.651286+00', '2026-06-01 06:51:26.651286+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 19, '{"contract_number": "HT20260601123108B53B", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT20260601123108B53B.pdf"]}', '{}', NULL, NULL, 45, '2026-06-01 06:51:30.557824+00', '2026-06-01 06:51:30.557824+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 16, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 46, '2026-06-01 06:51:33.655687+00', '2026-06-01 06:51:33.655687+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 12, '{"contract_id": 20, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "paid", "deleted_file": "/data/contract-system/receipts/2026/06/a98a7653-de33-489c-90d9-d083b7c9d788.jpg"}', '{}', NULL, NULL, 47, '2026-06-01 08:02:03.327331+00', '2026-06-01 08:02:03.327331+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 20, '{"contract_number": "HT20260601150520C878", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT20260601150520C878.pdf"]}', '{}', NULL, NULL, 48, '2026-06-01 08:02:07.315969+00', '2026-06-01 08:02:07.315969+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 17, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 49, '2026-06-01 08:02:10.806711+00', '2026-06-01 08:02:10.806711+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 13, '{"contract_id": 21, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "pending", "deleted_file": null}', '{}', NULL, NULL, 50, '2026-06-01 13:36:29.199433+00', '2026-06-01 13:36:29.199433+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 21, '{"contract_number": "HT20260601160325BC7D", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT20260601160325BC7D.pdf"]}', '{}', NULL, NULL, 51, '2026-06-01 13:36:32.690092+00', '2026-06-01 13:36:32.690092+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 18, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 52, '2026-06-01 13:36:35.586185+00', '2026-06-01 13:36:35.586185+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 14, '{"contract_id": 22, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "paid", "deleted_file": null}', '{}', NULL, NULL, 53, '2026-06-01 13:53:50.861484+00', '2026-06-01 13:53:50.861484+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 22, '{"contract_number": "HT20260601213801AEC8", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT20260601213801AEC8.pdf"]}', '{}', NULL, NULL, 54, '2026-06-01 13:53:54.375975+00', '2026-06-01 13:53:54.375975+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 19, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 55, '2026-06-01 13:54:01.213909+00', '2026-06-01 13:54:01.213909+00', 'f', NULL);

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
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '请分析上传的图片内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "0168e30a-389e-4034-922d-5cadf44c5f0a", "file_type": "image"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: 0168e30a-389e-4034-922d-5cadf44c5f0a\uff09"}', 570, '2026-06-01 13:55:22.213328+00', '2026-06-01 13:55:22.213328+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '两张是完全一样的，保留其中一张即可', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 572, '2026-06-01 13:55:53.888679+00', '2026-06-01 13:55:53.888679+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '是的', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 574, '2026-06-01 13:56:04.256187+00', '2026-06-01 13:56:04.256187+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'user', '请分析上传的PDF内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "0743a12e-9395-4fa9-939d-92099d7725cb", "file_type": "pdf"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: 0743a12e-9395-4fa9-939d-92099d7725cb\uff09"}', 579, '2026-06-01 14:21:01.322658+00', '2026-06-01 14:21:01.322658+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '好的，我来更新这笔付款记录，补充凭证信息。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_o0cZzi7T1MQF1YA0M0zz9808", "type": "function", "function": {"name": "update_payment", "arguments": "{\"payment_id\": 15, \"notes\": \"\u5df2\u63d0\u4f9b\u73b0\u91d1\u6536\u636e\u51ed\u8bc1\uff0c\u6536\u636e\u7f16\u53f700000213\uff0c\u6536\u6b3e\u4eba\u9648\u7115\u660e\uff0c\u5907\u6ce8\uff1a30\u7cfb\u57c3\u5c14\u6cd5GGH30-0016495\u603b\u4ef7\u6e2f\u5e0125\u4e07\", \"payment_method\": \"cash\", \"receipt_image_path\": \"0168e30a-389e-4034-922d-5cadf44c5f0a\", \"receipt_data\": {\"document_type\":\"cash_receipt\",\"amount\":50000,\"currency\":\"HKD\",\"transaction_date\":\"2026-05-28\",\"payer_name\":\"\u80e1\u5c11\u680b\u5148\u751f\",\"payee_name\":\"\u9648\u7115\u660e\",\"transaction_id\":\"00000213\",\"account_number\":\"GGH30-0016495\",\"notes\":\"30\u7cfb\u57c3\u5c14\u6cd5\uff1aGGH30-0016495\u603b\u4ef7\uff1a\u6e2f\u5e01\uff1a25\u4e07\"}, \"paid_date\": \"2026-05-28\"}"}}]', '{}', 573, '2026-06-01 13:56:00.029711+00', '2026-06-01 13:56:00.029711+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '### ✅ 定金已确认到账！

**胡少棟** 的车辆买卖合同（底盘号GGH30-0016495）定金 **50,000 HKD** 已从 **pending** 转为 **paid（已确认）**，正式参与合同结算。

### 📋 合同付款进度
| 期数 | 金额 | 状态 |
|:----:|:----:|:----:|
| ① **定金** | 50,000 HKD | ✅ **已付** |
| ② **尾款** | 200,000 HKD | ⏳ **未付** |

目前尾款 **200,000 HKD** 尚未支付，如有需要可以随时上传尾款的付款凭证。还有其他需要帮忙的吗？', NULL, NULL, NULL, NULL, 'deepseek-chat', 18053, NULL, 'null', '{}', 576, '2026-06-01 13:56:06.328605+00', '2026-06-01 13:56:06.328605+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '好的，我已经分析了这份PDF文件，以下是提取的关键信息总结：

---

## 📄 两地车牌指标过户服务合约

### 基本信息
| 项目 | 内容 |
|------|------|
| **合同标题** | 两地车牌指标过户服务合约 |
| **签订日期** | 2026年5月28日 |
| **服务方（甲方）** | **华星资源开发有限公司** |
| **委托方（乙方）** | **胡少棟**（证件号：F420825(7)，电话：97857999） |
| **业务类型** | 中港牌业务 |
| **服务内容** | 深圳湾口岸中港车牌指标过户及换车服务 |
| **车牌号** | 粤Z7N80 港 |

### 服务费用明细
| 服务项目 | 金额 |
|---------|:----:|
| 两地车牌指标过户服务 | **¥240,000** |
| 换车服务（含¥5,000换车费） | 已包含在总费用中 |
| **服务总费用** | **¥240,000（人民币贰拾肆万元整）** |

### 付款安排
| 期数 | 金额 | 应付款日期 | 是否已付 |
|:---:|:----:|:----------:|:--------:|
| ① **定金** | **¥50,000** | 2026-05-28（签约当日） | ❌ 未付 |
| ② **剩余款项** | **¥190,000** | 股权转让文件签署完成并书面通知乙方当日 | ❌ 未付 |

### 关键条款
- **违约责任**：乙方单方解约，定金不退；甲方过错导致失败，退还已收服务费
- **争议解决**：受香港法律管辖，争议向甲方所在地香港法院提起诉讼
- **服务期限**：甲方收到定金后启动服务

---

**请问您是否要基于这份合同进行录入？** 我可以帮您：
1. ✅ **录入合同** — 创建客户「胡少棟」并录入合同信息
2. ❓ 如果您有其他需求，也可以告诉我', NULL, NULL, NULL, NULL, 'deepseek-chat', 17424, NULL, 'null', '{}', 581, '2026-06-01 14:21:15.969822+00', '2026-06-01 14:21:15.969822+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '好的，我来分析这份合同文件并开始录入流程。

从合同分析结果来看，我已经提取了关键信息。现在我来推进合同录入流程。

首先，我搜索一下系统中是否已有客户「胡少棟」：', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_yU74irNUDOreHiSDjV7g1798", "type": "function", "function": {"name": "search_customers", "arguments": "{\"name\": \"\u80e1\u5c11\u68df\"}"}}]', '{}', 583, '2026-06-01 14:21:28.108202+00', '2026-06-01 14:21:28.108202+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'tool', '', '{"customers": [{"id": 20, "name": "胡少棟", "contact_person": null, "phone": "97857999", "wechat_group_name": null, "contract_count": 1}], "total": 1}', NULL, 'search_customers', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_yU74irNUDOreHiSDjV7g1798"}', 585, '2026-06-01 14:21:29.958821+00', '2026-06-01 14:21:29.958821+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '好的，客户信息已补充完整。现在我来创建合同。

根据合同内容：
- **业务类型**：中港牌业务（两地车牌指标过户）
- **总金额**：¥240,000（人民币）
- **付款条款**：
  - 第1期：定金 ¥50,000，签约当日（2026-05-28）应付 → **未付**（is_paid=false）
  - 第2期：剩余款项 ¥190,000，股权转让文件签署完成并书面通知乙方当日 → **未付**（is_paid=false）', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_qQOm6GJbZS61Vupqrljp2515", "type": "function", "function": {"name": "create_contract", "arguments": "{\"customer_id\": 20, \"file_id\": \"0743a12e-9395-4fa9-939d-92099d7725cb\", \"title\": \"\u4e24\u5730\u8f66\u724c\u6307\u6807\u8fc7\u6237\u670d\u52a1\u5408\u7ea6\", \"business_type\": \"\u4e2d\u6e2f\u724c\u4e1a\u52a1\", \"business_description\": \"\u6df1\u5733\u6e7e\u53e3\u5cb8\u4e2d\u6e2f\u8f66\u724c\u6307\u6807\u8fc7\u6237\u53ca\u6362\u8f66\u670d\u52a1\uff08\u8f66\u724c\u53f7\uff1a\u7ca4Z7N80\u6e2f\uff09\", \"total_amount\": 240000, \"currency\": \"CNY\", \"signed_date\": \"2026-05-28\", \"contract_data\": {\"\u7532\u65b9\": \"\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\", \"\u4e59\u65b9\": \"\u80e1\u5c11\u68df\", \"\u4e59\u65b9\u8bc1\u4ef6\u53f7\": \"F420825(7)\", \"\u4e59\u65b9\u7535\u8bdd\": \"97857999\", \"\u8f66\u724c\u53f7\": \"\u7ca4Z7N80\u6e2f\", \"\u670d\u52a1\u5185\u5bb9\": \"\u6df1\u5733\u6e7e\u53e3\u5cb8\u4e2d\u6e2f\u8f66\u724c\u6307\u6807\u8fc7\u6237\u53ca\u6362\u8f66\u670d\u52a1\", \"payment_terms\": [{\"installment_name\": \"\u5b9a\u91d1\", \"amount\": 50000, \"currency\": \"CNY\", \"due_date\": \"2026-05-28\", \"is_paid\": false}, {\"installment_name\": \"\u5269\u4f59\u6b3e\u9879\", \"amount\": 190000, \"currency\": \"CNY\", \"due_date\": \"\u80a1\u6743\u8f6c\u8ba9\u6587\u4ef6\u7b7e\u7f72\u5b8c\u6210\u5e76\u4e66\u9762\u901a\u77e5\u4e59\u65b9\u5f53\u65e5\", \"is_paid\": false}], \"\u8fdd\u7ea6\u8d23\u4efb\": \"\u4e59\u65b9\u5355\u65b9\u89e3\u7ea6\uff0c\u5b9a\u91d1\u4e0d\u9000\uff1b\u7532\u65b9\u8fc7\u9519\u5bfc\u81f4\u5931\u8d25\uff0c\u9000\u8fd8\u5df2\u6536\u670d\u52a1\u8d39\", \"\u4e89\u8bae\u89e3\u51b3\": \"\u53d7\u9999\u6e2f\u6cd5\u5f8b\u7ba1\u8f96\uff0c\u4e89\u8bae\u5411\u7532\u65b9\u6240\u5728\u5730\u9999\u6e2f\u6cd5\u9662\u63d0\u8d77\u8bc9\u8bbc\"}}"}}]', '{}', 588, '2026-06-01 14:21:36.089012+00', '2026-06-01 14:21:36.089012+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '## ✅ 合同录入完成！

以下是录入结果的汇总：

### 📋 合同信息
| 项目 | 内容 |
|------|------|
| **合同编号** | **HT2026060122213688B9** |
| **客户** | 胡少棟（证件号已补充） |
| **业务类型** | 中港牌业务 — 深圳湾口岸中港车牌指标过户及换车服务 |
| **车牌号** | 粤Z7N80港 |
| **总金额** | **¥240,000** |
| **签订日期** | 2026-05-28 |
| **合同状态** | ✅ **active（执行中）** |

### 💰 付款安排（待付款）
| 期数 | 金额 | 应付款日期 | 状态 |
|:---:|:----:|:----------:|:----:|
| ① 定金 | **¥50,000** | 2026-05-28（签约当日） | ⏳ **待付** |
| ② 剩余款项 | **¥190,000** | 股权转让文件签署完成当日 | ⏳ **待付** |

### 📌 温馨提示
合同中的两笔款项均标记为**未付**状态。当客户付款后，您可以将**付款凭证（转账截图、收据等）**上传给我，我会帮您关联到对应期数的付款记录，完成确认。

请问还有什么需要我帮忙的吗？', NULL, NULL, NULL, NULL, 'deepseek-chat', 34807, NULL, 'null', '{}', 590, '2026-06-01 14:21:39.463188+00', '2026-06-01 14:21:39.463188+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '好的，我来分析这张图片的内容。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_DNrkHw1x0xQvB8e5hAa88172", "type": "function", "function": {"name": "analyze_image", "arguments": "{\"file_id\": \"d79ae6eb-9cdc-4150-83b5-1b54e5e90e94\", \"analysis_type\": \"receipt\"}"}}]', '{}', 592, '2026-06-01 14:22:33.132389+00', '2026-06-01 14:22:33.132389+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '好的，我来分析这个上传的文件。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_Evvj75vpkOwOr4eQFm324402", "type": "function", "function": {"name": "analyze_image", "arguments": "{\"file_id\": \"9575fc72-88e2-4647-a02a-a75593a57922\", \"analysis_type\": \"contract\"}"}}]', '{}', 542, '2026-06-01 13:54:10.100728+00', '2026-06-01 13:54:10.100728+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"success": true, "data": {"contract_number": null, "title": "车辆买卖合约（香港）", "signed_date": "2026-05-28", "business_type": "车辆业务", "business_description": "购买车辆，车身底盘号码GGH30-0016495", "party_a": {"name": "华星资源开发有限公司", "contact": "98702065", "address": null}, "party_b": {"name": "胡少棟", "id_type": "证件类型及号码", "id_number": "F420825(7)", "phone": "97857999"}, "vehicle_info": {"plate_number": null, "vehicle_model": null, "registration_number": "GGH30-0016495"}, "port": null, "service_items": [], "payment_terms": [{"name": "定金", "amount": 50000, "due_date": "2026-05-28", "condition": "第一期：乙方已于2026年5月28日支付定金港币伍万元整", "is_paid": true}, {"name": "尾款", "amount": 200000, "due_date": null, "condition": "剩余车辆尾款港币贰拾万元整，须于该车辆完成香港运输署过户登记手续当日，由乙方一次性支付甲方", "is_paid": false}], "total_amount": 250000, "currency": "HKD", "validity_period": {"start_date": "2026-05-28", "end_date": null}, "special_terms": ["乙方确认以车辆现状购入，甲方除拥有合法所有权外不作其他保证", "乙方付清尾款后3个工作日内提车，逾期每日支付停车费港币100元", "自车辆过户登记之日起，一切风险及费用由乙方承担", "甲方保证车辆无抵押或法律纠纷", "乙方须自行购买汽车保险及牌费", "若乙方未支付尾款或提车，甲方有权没收定金并另行出售车辆", "本合约受香港特别行政区法律管辖，争议提交香港法院诉讼解决"], "confidence": 0.95, "full_text": "明哥中港牌\n本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。\n车辆买卖合约（香港）\n甲方（卖方）：华星资源开发有限公司\n联系人：陈焕明\n联系电话：98702065\n乙方（委托方）：\n胡少棟\n证件类型及号码：\nF420825(7)\n联系电话：\n97857999\n经双方协商，现就买卖下述车辆订立本合约，以资共同遵守。\n第一条车辆详情\n1. 车身底盘号码/车辆识别号码：\nGGH30-0016495\n第二条车辆售价与支付\n1. 该车辆之总售价为港币\n贰拾伍万\n元整（$ 250000 ）。\n2. 第一期：乙方已于2026 年\n5\n月\n28\n日支付定金港币\n伍万\n元整\n（$50000\n）。\n3. 剩余车辆尾款港币：\n贰拾万\n元整（$ 200000\n），须于该车辆完\n成香港运输署过户登记手续当日，由乙方一次性支付甲方。\n第三条车辆现状与接收\n乙方特此确认，其已对该车辆之品牌、型号、年份、里程、性能、外观、内饰、\n机件及一切现存状况进行了充分查验，并完全了解与接受。乙方同意以该车辆之\n“现状”购入，甲方除保证拥有合法所有权外，不就车辆之质量、性能、瑕疵或\n适用性作出任何其他明示或默示之保证。\n第四条车辆交付与责任\n1. 提车期限：乙方在付清第二条约定的全部尾款后，须于三（3）个工作日内，\n亲赴甲方指定地点提取该车辆。\n2. 逾期停车费：若乙方未能在上述约定期限内提走车辆，每逾期一日，须向甲\n方支付停车费港币壹佰元整（HK$100）。甲方有权将车辆移至其他地点停放，\n相关风险与费用由乙方承担。\n3. 风险转移：自该车辆于运输署完成过户登记之日起，无论乙方是否已提车，\n该车辆之一切风险（如损毁、失窃）及一切相关费用与法律责任（如罚款、事故）\n均转移由乙方承担。\n第五条文件与过户\n1. 甲方保证拥有该车辆之合法所有权，并承诺该车辆不附带任何抵押或法律纠\n纷。\n2. 甲方应配合提供办理过户所需之车辆登记文件（牌簿）等。\n\n明哥中港牌\n本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。\n第六条保险\n乙方须自行购买有效的汽车保险及牌费。\n第七条违约责任\n若乙方未按本合同约定支付尾款或提取车辆，甲方有权没收定金，并可将车辆另\n行出售。\n第八条其他\n1. 本合约受香港特别行政区法律管辖。\n2. 任何争议，应提交香港法院诉讼解决。\n3. 本合约一式两份，双方各执一份，自签署之日起生效。\n甲方签署：\n公司名称：\n华星资源开发有限公司\n日期：\n2026 年\n5\n月\n28\n日\n乙方签署：\n日期：\n2026 年\n5\n月\n28\n日"}, "file_id": "9575fc72-88e2-4647-a02a-a75593a57922", "file_path": "2026/06/9575fc72-88e2-4647-a02a-a75593a57922.pdf", "file_type": "pdf", "analysis_type": "contract"}', NULL, 'analyze_image', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_Evvj75vpkOwOr4eQFm324402"}', 544, '2026-06-01 13:54:11.567499+00', '2026-06-01 13:54:11.567499+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '请分析上传的PDF内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "9575fc72-88e2-4647-a02a-a75593a57922", "file_type": "pdf"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: 9575fc72-88e2-4647-a02a-a75593a57922\uff09"}', 546, '2026-06-01 13:54:23.523571+00', '2026-06-01 13:54:23.523571+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"success": true, "payment": {"id": 15, "contract_id": 23, "installment_number": 1, "installment_name": null, "type": "income", "payee_name": null, "currency": "HKD", "amount": 50000.0, "paid_amount": 50000.0, "exchange_rate": null, "amount_in_cny": null, "paid_amount_in_cny": null, "due_date": null, "paid_date": "2026-05-28", "payment_method": "cash", "status": "paid", "notes": "已提供现金收据凭证，收据编号00000213，收款人陈焕明，备注：30系埃尔法GGH30-0016495总价港币25万", "receipt_image_path": "2026/06/0168e30a-389e-4034-922d-5cadf44c5f0a.jpg", "receipt_data": {"notes": "30系埃尔法：GGH30-0016495总价：港币：25万", "amount": 50000, "currency": "HKD", "payee_name": "陈焕明", "payer_name": "胡少栋先生", "document_type": "cash_receipt", "account_number": "GGH30-0016495", "transaction_id": "00000213", "transaction_date": "2026-05-28"}}}', NULL, 'update_payment', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_o0cZzi7T1MQF1YA0M0zz9808"}', 575, '2026-06-01 13:56:04.298937+00', '2026-06-01 13:56:04.298937+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '是的', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 577, '2026-06-01 13:56:06.352184+00', '2026-06-01 13:56:06.352184+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'tool', '', '{"success": true, "data": {"document_type": "cash_receipt", "amount": 50000, "currency": "CNY", "transaction_date": "2026-05-28", "payer_name": "胡少栋先生", "payee_name": "陈焕明", "transaction_id": "00000215", "bank_name": null, "account_number": null, "notes": "深圳湾现牌24万人民币", "confidence": 0.95}, "file_id": "d79ae6eb-9cdc-4150-83b5-1b54e5e90e94", "file_path": "2026/06/d79ae6eb-9cdc-4150-83b5-1b54e5e90e94.jpg", "file_type": "image", "analysis_type": "receipt"}', NULL, 'analyze_image', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_DNrkHw1x0xQvB8e5hAa88172"}', 594, '2026-06-01 14:22:34.735675+00', '2026-06-01 14:22:34.735675+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'tool', '', '{"matches": [], "message": "未找到匹配的付款记录。请提供客户姓名以便搜索。"}', NULL, 'match_receipt', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_0Usu52EgoPyD8WyY6feZ3809"}', 596, '2026-06-01 14:22:41.556376+00', '2026-06-01 14:22:41.556376+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'tool', '', '{"id": 24, "contract_number": "HT2026060122213688B9", "title": "两地车牌指标过户服务合约", "business_type": "中港牌业务", "business_description": "深圳湾口岸中港车牌指标过户及换车服务（车牌号：粤Z7N80港）", "customer_name": "胡少棟", "currency": "CNY", "total_amount": 240000.0, "paid_amount": 0, "remaining_amount": 240000.0, "total_amount_in_cny": null, "paid_amount_in_cny": 0, "total_expense": 0, "total_expense_in_cny": 0, "status": "active", "wechat_group": null, "signed_date": "2026-05-28", "end_date": null, "payment_stats": {"total": 0, "paid": 0, "expense_count": 0}, "customer_id": 20, "sales_person_id": 1, "remarks": null, "income": {"payments": [], "total_amount": 240000.0, "paid_amount": 0.0, "remaining_amount": 240000.0, "total_paid_in_cny": 0.0}, "expense": {"payments": [], "total_expense": 0.0, "total_expense_in_cny": 0.0}, "profit_in_cny": 0.0}', NULL, 'get_contract_detail', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_nASter8dVGkIlTddXpAM8146"}', 598, '2026-06-01 14:22:43.628471+00', '2026-06-01 14:22:43.628471+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'user', '请分析上传的图片内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "d79ae6eb-9cdc-4150-83b5-1b54e5e90e94", "file_type": "image"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: d79ae6eb-9cdc-4150-83b5-1b54e5e90e94\uff09"}', 600, '2026-06-01 14:22:45.318308+00', '2026-06-01 14:22:45.318308+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '好的，我来为胡少棟的合同创建这笔定金付款记录，并关联凭证。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_G5FK9QbCi4H3uMhhzLgq9618", "type": "function", "function": {"name": "create_payment", "arguments": "{\"contract_id\": 24, \"installment_number\": 1, \"installment_name\": \"\u5b9a\u91d1\", \"amount\": 50000, \"currency\": \"CNY\", \"paid_date\": \"2026-05-28\", \"payment_method\": \"cash\", \"notes\": \"\u5df2\u63d0\u4f9b\u73b0\u91d1\u6536\u6b3e\u6536\u636e\uff0c\u4ed8\u6b3e\u4eba\u80e1\u5c11\u68df\uff0c\u6536\u636e\u7f16\u53f700000215\", \"receipt_data\": {\"document_type\":\"cash_receipt\",\"amount\":50000,\"currency\":\"CNY\",\"transaction_date\":\"2026-05-28\",\"payer_name\":\"\u80e1\u5c11\u680b\",\"payee_name\":\"\u9648\u7115\u660e\",\"transaction_id\":\"00000215\",\"notes\":\"\u6df1\u5733\u6e7e\u73b0\u724c24\u4e07\u4eba\u6c11\u5e01\"}}"}}]', '{}', 601, '2026-06-01 14:22:53.203894+00', '2026-06-01 14:22:53.203894+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'user', '是的呢', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 602, '2026-06-01 14:22:58.255433+00', '2026-06-01 14:22:58.255433+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'tool', '', '{"success": true, "payment": {"id": 16, "contract_id": 24, "installment_number": 1, "installment_name": "定金", "type": "income", "payee_name": null, "currency": "CNY", "amount": 50000.0, "paid_amount": 50000.0, "exchange_rate": null, "amount_in_cny": null, "paid_amount_in_cny": null, "due_date": null, "paid_date": "2026-05-28", "payment_method": "cash", "status": "paid", "notes": "已提供现金收款收据，付款人胡少棟，收据编号00000215", "receipt_image_path": "2026/06/d79ae6eb-9cdc-4150-83b5-1b54e5e90e94.jpg", "receipt_data": {"notes": "深圳湾现牌24万人民币", "amount": 50000, "currency": "CNY", "payee_name": "陈焕明", "payer_name": "胡少栋", "document_type": "cash_receipt", "transaction_id": "00000215", "transaction_date": "2026-05-28"}, "contract_number": "HT2026060122213688B9", "customer_name": "胡少棟"}}', NULL, 'create_payment', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_G5FK9QbCi4H3uMhhzLgq9618"}', 603, '2026-06-01 14:22:58.280301+00', '2026-06-01 14:22:58.280301+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '## ✅ 定金已确认到账！

| 项目 | 内容 |
|------|------|
| **客户** | 胡少棟 |
| **合同** | HT2026060122213688B9（深圳湾中港车牌） |
| **期数** | ① 定金 |
| **金额** | **¥50,000** ✅ **已付（已确认）** |
| **付款方式** | 现金 |
| **凭证** | ✅ 已关联收据（编号00000215） |

### 📊 合同付款进度
| 款项 | 金额 | 状态 |
|:---:|:----:|:----:|
| ① 定金 | ¥50,000 | ✅ **已付清** |
| ② 剩余款项 | ¥190,000 | ⏳ **待付** |
| **合计** | **¥240,000** | **已付 ¥50,000 / 剩余 ¥190,000** |

剩余 **¥190,000** 尾款待付（股权转让文件签署完成当日支付）。后续客户支付尾款时，您再上传凭证给我即可！', NULL, NULL, NULL, NULL, 'deepseek-chat', 18896, NULL, 'null', '{}', 604, '2026-06-01 14:23:00.885402+00', '2026-06-01 14:23:00.885402+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'user', '是的呢', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 605, '2026-06-01 14:23:00.893782+00', '2026-06-01 14:23:00.893782+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '请分析上传的PDF内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "9575fc72-88e2-4647-a02a-a75593a57922", "file_type": "pdf"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: 9575fc72-88e2-4647-a02a-a75593a57922\uff09"}', 543, '2026-06-01 13:54:11.559581+00', '2026-06-01 13:54:11.559581+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '好的，我已经成功分析了这份PDF文件，以下是提取的关键信息总结：

---

## 📄 车辆买卖合约（香港）

### 基本信息
| 项目 | 内容 |
|------|------|
| **合同类型** | 车辆买卖合约（香港） |
| **签订日期** | 2026年5月28日 |
| **甲方（卖方）** | **华星资源开发有限公司**（联系人：陈焕明，电话：98702065） |
| **乙方（买方）** | **胡少棟**（证件号：F420825(7)，电话：97857999） |
| **车辆底盘号码** | GGH30-0016495 |

### 交易金额
| 款项 | 金额 | 状态 |
|-----|:----:|:----:|
| **定金** | **50,000 HKD** | ✅ **已付**（2026年5月28日） |
| **尾款** | **200,000 HKD** | ❌ **未付**（须于完成香港运输署过户登记手续当日支付） |
| **总计** | **250,000 HKD** | |

### 主要条款摘要
1. **提车期限**：付清尾款后3个工作日内提车，逾期每日支付停车费 **100 HKD**
2. **风险转移**：自过户登记之日起，一切风险及费用由乙方承担
3. **甲方保证**：车辆无抵押或法律纠纷
4. **违约责任**：若乙方未付尾款或提车，甲方有权没收定金并另行出售车辆
5. **管辖法律**：香港特别行政区法律，争议提交香港法院诉讼解决

---

### ⏩ 接下来我可以为您：
由于这是一份**合同文件**，我可以按标准流程帮您完成**客户和合同的系统录入**。需要我继续推进吗？即：
1. ✅ 创建/匹配客户 **胡少棟**
2. ✅ 创建合同并录入系统（系统会自动将已付的定金记录为待确认付款）

您看是否开始录入？', NULL, NULL, NULL, NULL, 'deepseek-chat', 17019, NULL, 'null', '{}', 545, '2026-06-01 13:54:23.519002+00', '2026-06-01 13:54:23.519002+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '好的，我先分析这个PDF文件的内容。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_1DO5zhpc4Sy1ZrpJvpNx6611", "type": "function", "function": {"name": "analyze_image", "arguments": "{\"file_id\": \"0743a12e-9395-4fa9-939d-92099d7725cb\", \"analysis_type\": \"contract\"}"}}]', '{}', 578, '2026-06-01 14:20:59.519593+00', '2026-06-01 14:20:59.519593+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'tool', '', '{"success": true, "data": {"contract_number": null, "title": "两地车牌指标过户服务合约", "signed_date": "2026-05-28", "business_type": "中港牌业务", "business_description": "办理深圳湾口岸中港车牌指标过户及换车服务", "party_a": {"name": "华星资源开发有限公司", "contact": "98702065", "address": null}, "party_b": {"name": "胡少棟", "id_type": "证件类型", "id_number": "F420825(7)", "phone": "97857999"}, "vehicle_info": {"plate_number": "粤Z7N80 港", "vehicle_model": null, "registration_number": null}, "port": "深圳湾", "service_items": [{"name": "两地车牌指标过户服务", "description": "甲方负责安排并办理目标公司的股权过户至乙方名下的全套法律手续，以及后续将两地车牌指标换挂至乙方指定车辆的过户手续。", "amount": 240000}, {"name": "换车服务", "description": "甲方将为乙方提供全套换车协调服务。该服务包括但不限于：协助准备及提交换车文件、跟进申请进度；换车费用￥5000。", "amount": 5000}], "payment_terms": [{"name": "定金", "amount": 50000, "due_date": "2026-05-28", "condition": "本合约签订当日", "is_paid": false}, {"name": "剩余款项", "amount": 190000, "due_date": null, "condition": "在甲方完成目标公司的股权转让法律文件（以相关文件签署完成为准）并书面通知乙方之当日", "is_paid": false}], "total_amount": 240000, "currency": "CNY", "validity_period": {"start_date": "2026-05-28", "end_date": null}, "special_terms": ["若乙方支付定金后单方解除合约，已付定金不予退还。", "若因乙方未能按时支付各期款项、提供资料或配合办理，导致服务延误或产生额外成本，全部责任及费用由乙方承担，且甲方有权暂停服务。", "若因甲方过错导致公司过户或车牌换挂程序失败，甲方应退还已收取的服务费。"], "confidence": 0.95, "full_text": "明哥中港牌\n本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。\n两地车牌指标过户服务合约\n甲方（服务方）：华星资源开发有限公司\n联系电话：98702065\n乙方（委托方）：\n胡少棟\n证件类型及号码：\nF420825(7)\n联络电话：\n97857999\n甲、乙双方在平等自愿的基础上，就甲方为乙方提供粤港两地车牌指标（“两地\n牌”）过户及相关服务事宜，达成如下合约条款，以资共同遵守。\n第一条服务标的与定义\n1. 服务标的：指乙方拟购入的、已具备有效粤港两地通车资格的现成车牌指标\n及其对应的：\n车牌号：\n粤Z7N80 港\n通行口岸：\n深圳湾\n2. 公司过户：指将目标公司的全部已发行股份转让至乙方或其指定人士名下，\n从而使乙方间接持有该两地车牌指标的行为。\n3. 换车服务：指在车牌指标过户完成后，协助乙方办理将车牌指标从原有车辆\n转换挂载至其指定新车辆上的全套手续。\n第二条陈述与保证\n1.甲方陈述并保证:截至本合约签署之日，目标香港公司不存在任何未结清的债务、\n税务纠纷、未决诉讼或行政处罚，公司运作完全符合香港相关法律法规。\n2.乙方责任豁免:乙方成功购入目标香港公司后，仅作为其股权受让方，无需承担\n该目标香港公司及目标大陆公司在本次股权转让完成日(以公司注册处登记为准)\n之前所产生的任何历史债务、法律责任或违规后果。该等责任均应由转让前的股\n东及公司原负责人承担。\n第三条服务总费用及支付方式\n1. 服务总费用：本次服务之全部费用总计为人民币\n贰拾肆万\n元整\n（¥\n240000\n）。\n2. 付款安排：\n（1）定金：本合约签订当日，乙方应向甲方支付定金人民币伍万\n元整（￥\n50000\n）。甲方在收到定金后开始启动服务程序。\n（2）剩余款项：在甲方完成目标公司的股权转让法律文件（以相关文件签署\n完成为准）并书面通知乙方之当日，乙方必须支付剩余款项人民币\n壹拾玖万\n整（￥\n190000\n）。\n\n明哥中港牌\n本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。\n第四条甲方服务内容与责任\n1. 核心服务：甲方负责安排并办理目标公司的股权过户至乙方名下的全套法律\n手续，以及后续将两地车牌指标换挂至乙方指定车辆的过户手续。\n2. 换车服务：甲方将为乙方提供全套换车协调服务。该服务包括但不限于：协\n助准备及提交换车文件、跟进申请进度；换车费用\n￥5000\n。\n3. 甲方提供的服务含办理过程中产生的所有政府官方收费及第三方必要费用，\n包括但不限于：中国大陆部分的车辆保险费；此费用均需由乙方另行承担并直接\n支付给相关机构或通过甲方代缴。\n第五条乙方责任与保证\n1. 及时付款：乙方须严格按本合约第二条约定的时间及金额支付各期款项。\n2. 提供资料：乙方须根据办理进度，及时、真实、准确地提供甲方要求的各类\n身份证明、证件及文件资料（包括其指定的香港公司股东、董事资料及指定车辆\n文件），并予以配合。\n3. 承担官费：乙方须承担本合约第三条所列明的一切政府官方收费及第三方费\n用。\n第六条免责声明及风险提示\n1. 甲方提供的服务为程序性代办及协助，不对中国内地或香港政府部门（如广\n东省公安厅、香港运输署等）的审批结果、时长作出任何保证。\n第七条违约责任\n1. 若乙方支付定金后单方解除合约，已付定金不予退还。\n2. 若因乙方未能按时支付各期款项、提供资料或配合办理，导致服务延误或产\n生额外成本，全部责任及费用由乙方承担，且甲方有权暂停服务。\n3. 若因甲方过错导致公司过户或车牌换挂程序失败，甲方应退还已收取的服务\n费。\n第八条其他\n1. 法律适用与争议解决：本合约受香港特别行政区法律管辖。任何争议，双方\n应友好协商解决；协商不成的，任何一方可向甲方所在地之香港法院提起诉讼。\n甲方（盖章）：华星资源开发有限公司\n授权代表签署：\n日期：\n2026\n年\n5\n月\n28 日\n乙方（签署）：\n日期：\n2026\n年\n5\n月\n28 日"}, "file_id": "0743a12e-9395-4fa9-939d-92099d7725cb", "file_path": "2026/06/0743a12e-9395-4fa9-939d-92099d7725cb.pdf", "file_type": "pdf", "analysis_type": "contract"}', NULL, 'analyze_image', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_1DO5zhpc4Sy1ZrpJvpNx6611"}', 580, '2026-06-01 14:21:01.336125+00', '2026-06-01 14:21:01.336125+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'user', '请分析上传的PDF内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "0743a12e-9395-4fa9-939d-92099d7725cb", "file_type": "pdf"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: 0743a12e-9395-4fa9-939d-92099d7725cb\uff09"}', 582, '2026-06-01 14:21:15.977625+00', '2026-06-01 14:21:15.977625+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'user', '录入', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 584, '2026-06-01 14:21:29.947576+00', '2026-06-01 14:21:29.947576+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '系统中已有客户「胡少棟」（ID: 20），但缺少证件号信息。我来补充一下。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_frgwd9H4s7zOWWSAU7Pd0168", "type": "function", "function": {"name": "update_customer", "arguments": "{\"customer_id\": 20, \"id_card_number\": \"F420825(7)\"}"}}]', '{}', 586, '2026-06-01 14:21:31.555466+00', '2026-06-01 14:21:31.555466+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'tool', '', '{"success": true, "customer": {"id": 20, "name": "胡少棟", "phone": "97857999", "email": null, "wechat_group_name": null}, "message": "客户信息已更新: [''id_card_number'']"}', NULL, 'update_customer', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_frgwd9H4s7zOWWSAU7Pd0168"}', 587, '2026-06-01 14:21:31.566224+00', '2026-06-01 14:21:31.566224+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'tool', '', '{"success": true, "contract": {"id": 24, "contract_number": "HT2026060122213688B9", "customer_name": "胡少棟", "customer_id": 20, "title": "两地车牌指标过户服务合约", "currency": "CNY", "total_amount": 240000.0, "status": "active", "wechat_group": null, "signed_date": "2026-05-28"}, "auto_payments": []}', NULL, 'create_contract', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_qQOm6GJbZS61Vupqrljp2515"}', 589, '2026-06-01 14:21:36.121021+00', '2026-06-01 14:21:36.121021+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'user', '录入', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 591, '2026-06-01 14:21:39.467414+00', '2026-06-01 14:21:39.467414+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'user', '请分析上传的图片内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "d79ae6eb-9cdc-4150-83b5-1b54e5e90e94", "file_type": "image"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: d79ae6eb-9cdc-4150-83b5-1b54e5e90e94\uff09"}', 593, '2026-06-01 14:22:34.72799+00', '2026-06-01 14:22:34.72799+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '这是一张**收款收据**，我来总结提取的信息：

---

## 📄 收款收据分析结果

| 项目 | 内容 |
|------|------|
| **付款人** | 胡少棟先生 |
| **收款人** | 陈焕明 |
| **金额** | **¥50,000（人民币）** |
| **日期** | 2026-05-28 |
| **收据编号** | 00000215 |
| **备注** | 深圳湾现牌24万人民币 |

---

这与刚才录入的合同（胡少棟，深圳湾中港车牌，总价¥240,000）的**定金¥50,000**完全吻合！我来帮您匹配关联。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_0Usu52EgoPyD8WyY6feZ3809", "type": "function", "function": {"name": "match_receipt", "arguments": "{\"receipt_data\": {\"document_type\": \"cash_receipt\", \"amount\": 50000, \"currency\": \"CNY\", \"transaction_date\": \"2026-05-28\", \"payer_name\": \"\u80e1\u5c11\u680b\", \"payee_name\": \"\u9648\u7115\u660e\", \"transaction_id\": \"00000215\", \"notes\": \"\u6df1\u5733\u6e7e\u73b0\u724c24\u4e07\u4eba\u6c11\u5e01\"}}"}}]', '{}', 595, '2026-06-01 14:22:41.548997+00', '2026-06-01 14:22:41.548997+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '系统没有自动匹配到付款记录，因为合同刚创建时两笔款项都标记为未付，所以没有对应的 pending 付款记录。不过没关系，我来手动查询一下合同详情，看看系统是否自动生成了付款记录。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_nASter8dVGkIlTddXpAM8146", "type": "function", "function": {"name": "get_contract_detail", "arguments": "{\"contract_id\": 24}"}}]', '{}', 597, '2026-06-01 14:22:43.622257+00', '2026-06-01 14:22:43.622257+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '10dac6d3-535e-41a2-8b72-d188d0ef9fa7', 'assistant', '', '合同中没有自动生成付款记录（因为合同条款中两笔款项都标记为未付）。现在我需要为这笔定金创建付款记录，并关联凭证。

我确认一下：这张收据是**胡少棟**为**深圳湾中港车牌合同（¥240,000）**支付的**定金¥50,000**，对吗？如果是的话，我直接帮您创建付款记录并关联凭证。', NULL, NULL, NULL, NULL, 'deepseek-chat', 39673, NULL, 'null', '{}', 599, '2026-06-01 14:22:45.314896+00', '2026-06-01 14:22:45.314896+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '好的，那我现在开始推进合同录入流程！

首先，我搜索一下系统中是否已有客户 **胡少棟** 的记录。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_NxQmoU87I5g9IeiznIcV8715", "type": "function", "function": {"name": "search_customers", "arguments": "{\"name\": \"\u80e1\u5c11\u68df\"}"}}]', '{}', 547, '2026-06-01 13:54:29.551866+00', '2026-06-01 13:54:29.551866+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"customers": [], "total": 0}', NULL, 'search_customers', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_NxQmoU87I5g9IeiznIcV8715"}', 549, '2026-06-01 13:54:31.049983+00', '2026-06-01 13:54:31.049983+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '客户 **胡少棟** 已创建成功（客户ID: 20）。现在我来创建合同，将文件中的信息录入系统。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_VAZAxQK7k0xuWhDKG92g8120", "type": "function", "function": {"name": "create_contract", "arguments": "{\"customer_id\": 20, \"file_id\": \"9575fc72-88e2-4647-a02a-a75593a57922\", \"title\": \"\u8f66\u8f86\u4e70\u5356\u5408\u7ea6\uff08\u9999\u6e2f\uff09\", \"total_amount\": 250000, \"currency\": \"HKD\", \"signed_date\": \"2026-05-28\", \"business_type\": \"\u8f66\u8f86\u4e1a\u52a1\", \"business_description\": \"\u8d2d\u4e70\u4e30\u7530/\u51cc\u5fd7\u8f66\u8f86\uff08\u5e95\u76d8\u53f7GGH30-0016495\uff09\", \"contract_data\": {\"\u7532\u65b9\": \"\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\", \"\u7532\u65b9\u8054\u7cfb\u4eba\": \"\u9648\u7115\u660e\", \"\u7532\u65b9\u7535\u8bdd\": \"98702065\", \"\u4e59\u65b9\": \"\u80e1\u5c11\u68df\", \"\u4e59\u65b9\u8bc1\u4ef6\u53f7\": \"F420825(7)\", \"\u4e59\u65b9\u7535\u8bdd\": \"97857999\", \"\u8f66\u8f86\u5e95\u76d8\u53f7\u7801\": \"GGH30-0016495\", \"payment_terms\": [{\"installment_name\": \"\u5b9a\u91d1\", \"amount\": 50000, \"currency\": \"HKD\", \"due_date\": \"2026-05-28\", \"is_paid\": true, \"paid_date\": \"2026-05-28\"}, {\"installment_name\": \"\u5c3e\u6b3e\", \"amount\": 200000, \"currency\": \"HKD\", \"due_date\": \"\u5b8c\u6210\u9999\u6e2f\u8fd0\u8f93\u7f72\u8fc7\u6237\u767b\u8bb0\u624b\u7eed\u5f53\u65e5\", \"is_paid\": false}], \"\u63d0\u8f66\u671f\u9650\": \"\u4ed8\u6e05\u5c3e\u6b3e\u540e3\u4e2a\u5de5\u4f5c\u65e5\u5185\", \"\u903e\u671f\u505c\u8f66\u8d39\": \"100 HKD/\u65e5\", \"\u7ba1\u8f96\u6cd5\u5f8b\": \"\u9999\u6e2f\u7279\u522b\u884c\u653f\u533a\u6cd5\u5f8b\"}}"}}]', '{}', 552, '2026-06-01 13:54:36.207447+00', '2026-06-01 13:54:36.207447+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"success": true, "contract": {"id": 23, "contract_number": "HT202606012154361AE8", "customer_name": "胡少棟", "customer_id": 20, "title": "车辆买卖合约（香港）", "currency": "HKD", "total_amount": 250000.0, "status": "active", "wechat_group": null, "signed_date": "2026-05-28"}, "auto_payments": [{"payment_id": 15, "installment_number": 1, "installment_name": null, "amount": 50000.0, "currency": "HKD", "status": "pending"}]}', NULL, 'create_contract', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_VAZAxQK7k0xuWhDKG92g8120"}', 553, '2026-06-01 13:54:36.252448+00', '2026-06-01 13:54:36.252448+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', 'OK的', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 555, '2026-06-01 13:54:39.978825+00', '2026-06-01 13:54:39.978825+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '请分析上传的图片内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "2cd39f8e-f9ed-49a2-8c30-9235798e11da", "file_type": "image"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: 2cd39f8e-f9ed-49a2-8c30-9235798e11da\uff09"}', 557, '2026-06-01 13:55:08.366612+00', '2026-06-01 13:55:08.366612+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '好的，我来分析这两张图片的内容。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_IJRCOVtjs7X0VtTSaZJ90050", "type": "function", "function": {"name": "analyze_image", "arguments": "{\"file_id\": \"2cd39f8e-f9ed-49a2-8c30-9235798e11da\", \"analysis_type\": \"receipt\"}"}}, {"id": "call_01_zgDJWEAJKa7QchJ7qv6W2053", "type": "function", "function": {"name": "analyze_image", "arguments": "{\"file_id\": \"0168e30a-389e-4034-922d-5cadf44c5f0a\", \"analysis_type\": \"receipt\"}"}}]', '{}', 559, '2026-06-01 13:55:09.998415+00', '2026-06-01 13:55:09.998415+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"success": true, "data": {"document_type": "cash_receipt", "amount": 50000, "currency": "HKD", "transaction_date": "2026-05-28", "payer_name": "胡少栋先生", "payee_name": "陈焕明", "transaction_id": "00000213", "bank_name": null, "account_number": "GGH30-0016495", "notes": "30系埃尔法：GGH30-0016495总价：港币：25万", "confidence": 0.95}, "file_id": "2cd39f8e-f9ed-49a2-8c30-9235798e11da", "file_path": "2026/06/2cd39f8e-f9ed-49a2-8c30-9235798e11da.jpg", "file_type": "image", "analysis_type": "receipt"}', NULL, 'analyze_image', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_IJRCOVtjs7X0VtTSaZJ90050"}', 563, '2026-06-01 13:55:12.226811+00', '2026-06-01 13:55:12.226811+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '系统找到了匹配项！我来向您确认：

---

**是否将这张收据关联到以下合同的定金？**

👤 **客户：胡少棟**
📋 **业务：购买车辆（底盘号GGH30-0016495）**
💰 **金额：50,000 HKD（定金）**
📅 **日期：2026年5月28日**

确认后，系统会自动将这笔定金从 **pending（待确认）** 转为 **paid（已确认）**，参与合同结算。请问可以确认吗？', NULL, NULL, NULL, NULL, 'deepseek-chat', 29365, NULL, 'null', '{}', 564, '2026-06-01 13:55:15.973534+00', '2026-06-01 13:55:15.973534+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '请分析上传的图片内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "2cd39f8e-f9ed-49a2-8c30-9235798e11da", "file_type": "image"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: 2cd39f8e-f9ed-49a2-8c30-9235798e11da\uff09"}', 565, '2026-06-01 13:55:15.98004+00', '2026-06-01 13:55:15.98004+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '两张图片内容一致，都是 **定金收据**。我来用凭证信息匹配到对应的合同付款记录。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_pJRzX6CoiOF7v4tvIIbQ5482", "type": "function", "function": {"name": "match_receipt", "arguments": "{\"receipt_data\": {\"document_type\":\"cash_receipt\",\"amount\":50000,\"currency\":\"HKD\",\"transaction_date\":\"2026-05-28\",\"payer_name\":\"\u80e1\u5c11\u680b\u5148\u751f\",\"payee_name\":\"\u9648\u7115\u660e\",\"transaction_id\":\"00000213\",\"account_number\":\"GGH30-0016495\",\"notes\":\"30\u7cfb\u57c3\u5c14\u6cd5\uff1aGGH30-0016495\u603b\u4ef7\uff1a\u6e2f\u5e01\uff1a25\u4e07\"}}"}}]', '{}', 567, '2026-06-01 13:55:19.866817+00', '2026-06-01 13:55:19.866817+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '找到了匹配的付款记录！我来向您确认：

---

### 🔍 凭证分析结果
| 项目 | 内容 |
|------|------|
| **凭证类型** | 现金收据 |
| **付款人** | 胡少棟先生 |
| **收款人** | 陈焕明 |
| **金额** | **50,000 HKD** |
| **日期** | 2026年5月28日 |
| **收据编号** | 00000213 |
| **备注** | 30系埃尔法 GGH30-0016495 |

### ✅ 系统匹配结果
这笔 **50,000 HKD 定金** 匹配到 **胡少棟** 的 **车辆买卖合同（HT202606012154361AE8）** 第1期定金付款记录。

请问是否确认将这两张凭证关联到该合同的定金记录上？', NULL, NULL, NULL, NULL, 'deepseek-chat', 30032, NULL, 'null', '{}', 569, '2026-06-01 13:55:22.208479+00', '2026-06-01 13:55:22.208479+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '好的，明白了！这两张图片内容相同，都是胡少棟的 **50,000 HKD 定金收据**。那我来确认一下关联操作：

**是否确认将这张收据关联到胡少棟的车辆买卖合同（购买丰田/凌志车辆，底盘号GGH30-0016495）的定金记录上？**

确认后，系统会将这笔定金从 **pending（待确认）** 转为 **paid（已确认）**，参与合同结算。', NULL, NULL, NULL, NULL, 'deepseek-chat', 8977, NULL, 'null', '{}', 571, '2026-06-01 13:55:49.899668+00', '2026-06-01 13:55:49.899668+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', 'OK的', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 548, '2026-06-01 13:54:31.037107+00', '2026-06-01 13:54:31.037107+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '系统中没有找到 **胡少棟** 的记录，我来创建这位客户。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_g5p0booq8sanWUpGkmFY5483", "type": "function", "function": {"name": "create_customer", "arguments": "{\"name\": \"\u80e1\u5c11\u68df\", \"phone\": \"97857999\", \"id_card_number\": \"F420825(7)\"}"}}]', '{}', 550, '2026-06-01 13:54:32.563819+00', '2026-06-01 13:54:32.563819+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"success": true, "customer": {"id": 20, "name": "胡少棟", "phone": "97857999", "email": null, "wechat_group_name": null}, "created": true, "message": "客户创建成功"}', NULL, 'create_customer', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_g5p0booq8sanWUpGkmFY5483"}', 551, '2026-06-01 13:54:32.592494+00', '2026-06-01 13:54:32.592494+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '## ✅ 合同录入完成！

以下是系统录入的完整信息：

---

### 📋 合同信息
| 项目 | 内容 |
|------|------|
| **合同编号** | **HT202606012154361AE8** |
| **客户** | **胡少棟**（证件号：F420825(7)） |
| **业务类型** | 车辆业务 — 购买车辆（底盘号GGH30-0016495） |
| **合同总金额** | **250,000 HKD** |
| **签订日期** | 2026年5月28日 |
| **合同状态** | ✅ **执行中（active）** |

### 💰 付款记录
| 期数 | 款项 | 金额 | 状态 |
|:---:|:----:|:----:|:----:|
| 第1期 | **定金** | **50,000 HKD** | ⏳ **待确认（pending）** |
| 第2期 | **尾款** | **200,000 HKD** | ❌ **未付** |

### ⚠️ 温馨提示
- **定金（50,000 HKD）** 已根据合同原文标记为已付，系统已自动创建了付款记录，但目前状态为 **pending（待确认）**。
- 如果您有定金的**付款凭证（转账截图、收据等）**，请上传给我，我帮您补充凭证，系统会自动将其转为 **paid（已确认）** 状态并参与合同结算。
- **尾款（200,000 HKD）** 须在完成香港运输署过户登记手续当日支付。

请问您需要上传定金的付款凭证吗？或者还有其他需要处理的？', NULL, NULL, NULL, NULL, 'deepseek-chat', 34434, NULL, 'null', '{}', 554, '2026-06-01 13:54:39.964771+00', '2026-06-01 13:54:39.964771+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '好的，我来分析这张图片的内容。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_c1SRkvkNbOO4TzRkPNBF3276", "type": "function", "function": {"name": "analyze_image", "arguments": "{\"file_id\": \"2cd39f8e-f9ed-49a2-8c30-9235798e11da\", \"analysis_type\": \"receipt\"}"}}]', '{}', 556, '2026-06-01 13:55:06.759454+00', '2026-06-01 13:55:06.759454+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"success": true, "data": {"document_type": "cash_receipt", "amount": 50000, "currency": "HKD", "transaction_date": "2026-05-28", "payer_name": "胡少栋先生", "payee_name": "陈焕明", "transaction_id": "00000213", "bank_name": null, "account_number": "GGH30-0016495", "notes": "30系埃尔法：GGH30-0016495总价：港币：25万", "confidence": 0.95}, "file_id": "2cd39f8e-f9ed-49a2-8c30-9235798e11da", "file_path": "2026/06/2cd39f8e-f9ed-49a2-8c30-9235798e11da.jpg", "file_type": "image", "analysis_type": "receipt"}', NULL, 'analyze_image', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_c1SRkvkNbOO4TzRkPNBF3276"}', 558, '2026-06-01 13:55:08.373463+00', '2026-06-01 13:55:08.373463+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'user', '请分析上传的图片内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, 'null', '{"attachments": [{"file_id": "0168e30a-389e-4034-922d-5cadf44c5f0a", "file_type": "image"}], "file_context": "\u7528\u6237\u4e0a\u4f20\u4e86\u6587\u4ef6\uff08file_id: 0168e30a-389e-4034-922d-5cadf44c5f0a\uff09"}', 560, '2026-06-01 13:55:12.215265+00', '2026-06-01 13:55:12.215265+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'assistant', '', '## 📄 凭证分析结果

这是一张**现金收款收据**，关键信息如下：

| 项目 | 内容 |
|------|------|
| **付款人** | 胡少棟先生 |
| **收款人** | 陈焕明 |
| **金额** | **50,000 HKD** |
| **日期** | 2026年5月28日 |
| **收据编号** | 00000213 |
| **备注** | 30系埃尔法：GGH30-0016495，总价港币25万 |

这正好对应 **胡少棟** 合同中的 **定金（50,000 HKD）**！我来帮您匹配关联。', NULL, NULL, NULL, NULL, 'deepseek-chat', NULL, NULL, '[{"id": "call_00_G6hVfBdQ9uRFQSUJk1YQ8962", "type": "function", "function": {"name": "match_receipt", "arguments": "{\"receipt_data\": {\"document_type\": \"cash_receipt\", \"amount\": 50000, \"currency\": \"HKD\", \"transaction_date\": \"2026-05-28\", \"payer_name\": \"\u80e1\u5c11\u680b\u5148\u751f\", \"payee_name\": \"\u9648\u7115\u660e\", \"transaction_id\": \"00000213\", \"notes\": \"30\u7cfb\u57c3\u5c14\u6cd5\uff1aGGH30-0016495\u603b\u4ef7\uff1a\u6e2f\u5e01\uff1a25\u4e07\"}}"}}]', '{}', 561, '2026-06-01 13:55:13.711737+00', '2026-06-01 13:55:13.711737+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"matches": [{"payment_id": 15, "contract_id": 23, "contract_number": "HT202606012154361AE8", "customer_name": "胡少棟", "business_type": "车辆业务", "business_description": "购买丰田/凌志车辆（底盘号GGH30-0016495）", "installment_number": 1, "installment_name": null, "amount": 50000.0, "currency": "HKD", "status": "pending", "paid_date": "2026-05-28", "score": 50, "match_reason": "金额匹配、币种匹配"}], "message": "找到 1 条可能匹配的付款记录，请确认正确的关联。"}', NULL, 'match_receipt', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_G6hVfBdQ9uRFQSUJk1YQ8962"}', 562, '2026-06-01 13:55:13.720754+00', '2026-06-01 13:55:13.720754+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"success": true, "data": {"document_type": "cash_receipt", "amount": 50000, "currency": "HKD", "transaction_date": "2026-05-28", "payer_name": "胡少栋先生", "payee_name": "陈焕明", "transaction_id": "00000213", "bank_name": null, "account_number": "GGH30-0016495", "notes": "30系埃尔法：GGH30-0016495总价：港币：25万", "confidence": 0.95}, "file_id": "0168e30a-389e-4034-922d-5cadf44c5f0a", "file_path": "2026/06/0168e30a-389e-4034-922d-5cadf44c5f0a.jpg", "file_type": "image", "analysis_type": "receipt"}', NULL, 'analyze_image', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_01_zgDJWEAJKa7QchJ7qv6W2053"}', 566, '2026-06-01 13:55:15.258824+00', '2026-06-01 13:55:15.258824+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '118a4c60-3b19-402e-a3ba-6988971e2ddf', 'tool', '', '{"matches": [{"payment_id": 15, "contract_id": 23, "contract_number": "HT202606012154361AE8", "customer_name": "胡少棟", "business_type": "车辆业务", "business_description": "购买丰田/凌志车辆（底盘号GGH30-0016495）", "installment_number": 1, "installment_name": null, "amount": 50000.0, "currency": "HKD", "status": "pending", "paid_date": "2026-05-28", "score": 50, "match_reason": "金额匹配、币种匹配"}], "message": "找到 1 条可能匹配的付款记录，请确认正确的关联。"}', NULL, 'match_receipt', NULL, NULL, 'deepseek-chat', NULL, NULL, NULL, '{"tool_call_id": "call_00_pJRzX6CoiOF7v4tvIIbQ5482"}', 568, '2026-06-01 13:55:19.874693+00', '2026-06-01 13:55:19.874693+00', 'f', NULL);

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
  "total_expense_in_cny" numeric(15,2) DEFAULT 0,
  "contract_text" text COLLATE "pg_catalog"."default"
)
;
COMMENT ON COLUMN "public"."contracts"."contract_text" IS '合同全文内容（AI从图片/PDF提取的完整文本）';

-- ----------------------------
-- Records of contracts
-- ----------------------------
INSERT INTO "public"."contracts" VALUES ('HT202605282249464627', '车辆买卖合约（香港）', 1, 1, 'HKD', 250000.00, 0.00, 250000.00, NULL, 0.00, 0.00, '2026/05/HT202605282249464627.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "30e74365-0d7f-46f3-875f-eca205068435", "business_type": "\u4e70\u6e2f\u8f66"}', NULL, 'f', 'draft', '2026-05-28', NULL, NULL, NULL, 1, 1, '2026-05-28 14:49:46.789768+00', '2026-05-29 00:42:11.667+00', 't', '2026-05-29 00:42:11.683734+00', '买港车', NULL, NULL, 0.00, 0.00, NULL);
INSERT INTO "public"."contracts" VALUES ('HT202605290843540034', '车辆买卖合约（香港）', 2, 1, 'HKD', 250000.00, 0.00, 250000.00, NULL, 0.00, NULL, '2026/05/HT202605290843540034.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "6244290a-41f3-4068-81a5-88218e934c7f", "business_type": "\u8f66\u8f86\u4e1a\u52a1", "business_description": "\u8d2d\u4e70\u8f66\u8f86\uff0c\u8f66\u8eab\u5e95\u76d8\u53f7\u7801GGH30-0016495"}', NULL, 'f', 'draft', '2026-05-28', NULL, NULL, NULL, 1, 2, '2026-05-29 00:43:54.818038+00', '2026-05-29 00:54:46.416302+00', 't', '2026-05-29 00:54:46.421665+00', '车辆业务', '购买车辆，车身底盘号码GGH30-0016495', NULL, 0.00, 0.00, NULL);
INSERT INTO "public"."contracts" VALUES ('HT20260529103425145B', '两地车牌指标过户服务合约', 3, 1, 'CNY', 240000.00, 0.00, 240000.00, NULL, 0.00, NULL, '2026/05/HT20260529103425145B.pdf', '33ee97e02357ecc6a802f0c70c4d20e300c7683d59a4920e147e519f06193e52', '{"source": "agent", "file_id": "96e39fc9-b8c1-4f34-8042-1a10d49720a6", "business_type": "\u4e2d\u6e2f\u724c\u4e1a\u52a1", "business_description": "\u529e\u7406\u6df1\u5733\u6e7e\u53e3\u5cb8\u4e24\u5730\u8f66\u724c\u6307\u6807\u8fc7\u6237\uff0c\u8f66\u724c\u53f7\uff1a\u7ca4Z7N80\u6e2f"}', NULL, 'f', 'active', '2026-05-28', NULL, NULL, NULL, 1, 4, '2026-05-29 02:34:25.83356+00', '2026-05-29 08:08:03.799657+00', 't', '2026-05-29 08:08:03.80766+00', '中港牌业务', '办理深圳湾口岸两地车牌指标过户，车牌号：粤Z7N80港', NULL, 0.00, 0.00, NULL);
INSERT INTO "public"."contracts" VALUES ('HT202605290902076221', '车辆买卖合约（香港）', 3, 1, 'HKD', 250000.00, 0.00, 250000.00, NULL, 0.00, NULL, '2026/05/HT202605290902076221.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "70b18c5a-8807-4571-8bc2-f27b8711c191", "business_type": "\u8f66\u8f86\u4e1a\u52a1", "business_description": "\u8d2d\u4e70\u8f66\u8f86\uff08\u5e95\u76d8\u53f7\uff1aGGH30-0016495\uff09\uff0c\u603b\u4ef7250,000 HKD\uff0c\u5df2\u4ed8\u5b9a\u91d150,000 HKD\uff0c\u5c3e\u6b3e200,000 HKD"}', NULL, 'f', 'active', '2026-05-28', NULL, NULL, NULL, 1, 3, '2026-05-29 01:02:07.386264+00', '2026-05-29 08:08:05.979261+00', 't', '2026-05-29 08:08:05.9906+00', '车辆业务', '购买车辆（底盘号：GGH30-0016495），总价250,000 HKD，已付定金50,000 HKD，尾款200,000 HKD', '5月28日17年白外黑内30系埃尔法(10)', 0.00, 0.00, NULL);
INSERT INTO "public"."contracts" VALUES ('HT202606012154361AE8', '车辆买卖合约（香港）', 20, 1, 'HKD', 250000.00, 50000.00, 200000.00, NULL, 0.00, NULL, '2026/06/HT202606012154361AE8.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "9575fc72-88e2-4647-a02a-a75593a57922", "business_type": "\u8f66\u8f86\u4e1a\u52a1", "business_description": "\u8d2d\u4e70\u4e30\u7530/\u51cc\u5fd7\u8f66\u8f86\uff08\u5e95\u76d8\u53f7GGH30-0016495\uff09", "\u7532\u65b9": "\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8", "\u7532\u65b9\u8054\u7cfb\u4eba": "\u9648\u7115\u660e", "\u7532\u65b9\u7535\u8bdd": "98702065", "\u4e59\u65b9": "\u80e1\u5c11\u68df", "\u4e59\u65b9\u8bc1\u4ef6\u53f7": "F420825(7)", "\u4e59\u65b9\u7535\u8bdd": "97857999", "\u8f66\u8f86\u5e95\u76d8\u53f7\u7801": "GGH30-0016495", "payment_terms": [{"installment_name": "\u5b9a\u91d1", "amount": 50000, "currency": "HKD", "due_date": "2026-05-28", "is_paid": true, "paid_date": "2026-05-28"}, {"installment_name": "\u5c3e\u6b3e", "amount": 200000, "currency": "HKD", "due_date": "\u5b8c\u6210\u9999\u6e2f\u8fd0\u8f93\u7f72\u8fc7\u6237\u767b\u8bb0\u624b\u7eed\u5f53\u65e5", "is_paid": false}], "\u63d0\u8f66\u671f\u9650": "\u4ed8\u6e05\u5c3e\u6b3e\u540e3\u4e2a\u5de5\u4f5c\u65e5\u5185", "\u903e\u671f\u505c\u8f66\u8d39": "100 HKD/\u65e5", "\u7ba1\u8f96\u6cd5\u5f8b": "\u9999\u6e2f\u7279\u522b\u884c\u653f\u533a\u6cd5\u5f8b"}', NULL, 'f', 'active', '2026-05-28', NULL, NULL, NULL, 1, 23, '2026-06-01 13:54:36.214272+00', '2026-06-01 13:56:04.26512+00', 'f', NULL, '车辆业务', '购买丰田/凌志车辆（底盘号GGH30-0016495）', NULL, 0.00, 0.00, NULL);
INSERT INTO "public"."contracts" VALUES ('HT2026060122213688B9', '两地车牌指标过户服务合约', 20, 1, 'CNY', 240000.00, 50000.00, 190000.00, NULL, 0.00, NULL, '2026/06/HT2026060122213688B9.pdf', '33ee97e02357ecc6a802f0c70c4d20e300c7683d59a4920e147e519f06193e52', '{"source": "agent", "file_id": "0743a12e-9395-4fa9-939d-92099d7725cb", "business_type": "\u4e2d\u6e2f\u724c\u4e1a\u52a1", "business_description": "\u6df1\u5733\u6e7e\u53e3\u5cb8\u4e2d\u6e2f\u8f66\u724c\u6307\u6807\u8fc7\u6237\u53ca\u6362\u8f66\u670d\u52a1\uff08\u8f66\u724c\u53f7\uff1a\u7ca4Z7N80\u6e2f\uff09", "\u7532\u65b9": "\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8", "\u4e59\u65b9": "\u80e1\u5c11\u68df", "\u4e59\u65b9\u8bc1\u4ef6\u53f7": "F420825(7)", "\u4e59\u65b9\u7535\u8bdd": "97857999", "\u8f66\u724c\u53f7": "\u7ca4Z7N80\u6e2f", "\u670d\u52a1\u5185\u5bb9": "\u6df1\u5733\u6e7e\u53e3\u5cb8\u4e2d\u6e2f\u8f66\u724c\u6307\u6807\u8fc7\u6237\u53ca\u6362\u8f66\u670d\u52a1", "payment_terms": [{"installment_name": "\u5b9a\u91d1", "amount": 50000, "currency": "CNY", "due_date": "2026-05-28", "is_paid": false}, {"installment_name": "\u5269\u4f59\u6b3e\u9879", "amount": 190000, "currency": "CNY", "due_date": "\u80a1\u6743\u8f6c\u8ba9\u6587\u4ef6\u7b7e\u7f72\u5b8c\u6210\u5e76\u4e66\u9762\u901a\u77e5\u4e59\u65b9\u5f53\u65e5", "is_paid": false}], "\u8fdd\u7ea6\u8d23\u4efb": "\u4e59\u65b9\u5355\u65b9\u89e3\u7ea6\uff0c\u5b9a\u91d1\u4e0d\u9000\uff1b\u7532\u65b9\u8fc7\u9519\u5bfc\u81f4\u5931\u8d25\uff0c\u9000\u8fd8\u5df2\u6536\u670d\u52a1\u8d39", "\u4e89\u8bae\u89e3\u51b3": "\u53d7\u9999\u6e2f\u6cd5\u5f8b\u7ba1\u8f96\uff0c\u4e89\u8bae\u5411\u7532\u65b9\u6240\u5728\u5730\u9999\u6e2f\u6cd5\u9662\u63d0\u8d77\u8bc9\u8bbc"}', NULL, 'f', 'active', '2026-05-28', NULL, NULL, NULL, 1, 24, '2026-06-01 14:21:36.095549+00', '2026-06-01 14:22:58.262233+00', 'f', NULL, '中港牌业务', '深圳湾口岸中港车牌指标过户及换车服务（车牌号：粤Z7N80港）', NULL, 0.00, 0.00, NULL);

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
INSERT INTO "public"."customers" VALUES ('胡少棟', NULL, '97857999', NULL, 'RjQyMDgyNSg3KQ==', NULL, NULL, NULL, NULL, 1, 20, '2026-06-01 13:54:32.571815+00', '2026-06-01 13:54:32.571815+00', 'f', NULL);

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
  "payee_name" varchar(200) COLLATE "pg_catalog"."default",
  "receipt_data" jsonb,
  "description" varchar(500) COLLATE "pg_catalog"."default"
)
;
COMMENT ON COLUMN "public"."payments"."receipt_data" IS '凭证分析结构化数据（银行转账/微信/支付宝/收据等）';
COMMENT ON COLUMN "public"."payments"."description" IS '自动生成的可读描述';

-- ----------------------------
-- Records of payments
-- ----------------------------
INSERT INTO "public"."payments" VALUES (23, 1, NULL, 'HKD', 50000.00, 50000.00, NULL, NULL, NULL, NULL, '2026-05-28', '2026/06/0168e30a-389e-4034-922d-5cadf44c5f0a.jpg', NULL, NULL, 'cash', 'paid', 'manual', '已提供现金收据凭证，收据编号00000213，收款人陈焕明，备注：30系埃尔法GGH30-0016495总价港币25万', 1, 15, '2026-06-01 13:54:36.239719+00', '2026-06-01 13:56:04.26512+00', 'f', NULL, 'income', NULL, '{"notes": "30系埃尔法：GGH30-0016495总价：港币：25万", "amount": 50000, "currency": "HKD", "payee_name": "陈焕明", "payer_name": "胡少栋先生", "document_type": "cash_receipt", "account_number": "GGH30-0016495", "transaction_id": "00000213", "transaction_date": "2026-05-28"}', 'HT202606012154361AE8 胡少棟 购买丰田/凌志车辆（底盘号GGH30-0016495） 第1期收款');
INSERT INTO "public"."payments" VALUES (24, 1, '定金', 'CNY', 50000.00, 50000.00, NULL, NULL, NULL, NULL, '2026-05-28', '2026/06/d79ae6eb-9cdc-4150-83b5-1b54e5e90e94.jpg', NULL, NULL, 'cash', 'paid', 'manual', '已提供现金收款收据，付款人胡少棟，收据编号00000215', 1, 16, '2026-06-01 14:22:58.262233+00', '2026-06-01 14:22:58.262233+00', 'f', NULL, 'income', NULL, '{"notes": "深圳湾现牌24万人民币", "amount": 50000, "currency": "CNY", "payee_name": "陈焕明", "payer_name": "胡少栋", "document_type": "cash_receipt", "transaction_id": "00000215", "transaction_date": "2026-05-28"}', 'HT2026060122213688B9 胡少棟 深圳湾口岸中港车牌指标过户及换车服务（车牌号：粤Z7N80港） 第1期收款');

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
INSERT INTO "public"."users" VALUES ('admin', '$2b$12$oPTewLgAsUrRRfXbFWqUVeuzqXODoDIsRMCKpLe1mVZQB1GvnYm6W', NULL, '系统管理员', 'admin', NULL, 't', '2026-06-02 02:18:56.040889+00', 1, '2026-05-27 13:45:21.413514+00', '2026-06-02 02:18:55.683492+00', 'f', NULL);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."audit_logs_id_seq"
OWNED BY "public"."audit_logs"."id";
SELECT setval('"public"."audit_logs_id_seq"', 55, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."chat_history_id_seq"
OWNED BY "public"."chat_history"."id";
SELECT setval('"public"."chat_history_id_seq"', 605, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."contracts_id_seq"
OWNED BY "public"."contracts"."id";
SELECT setval('"public"."contracts_id_seq"', 24, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."customers_id_seq"
OWNED BY "public"."customers"."id";
SELECT setval('"public"."customers_id_seq"', 20, true);

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
SELECT setval('"public"."payments_id_seq"', 16, true);

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
