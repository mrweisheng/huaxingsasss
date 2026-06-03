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

 Date: 03/06/2026 16:31:48
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
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 16, '{"contract_id": 24, "amount": 50000.0, "currency": "CNY", "type": "income", "status": "paid", "deleted_file": "/data/contract-system/receipts/2026/06/d79ae6eb-9cdc-4150-83b5-1b54e5e90e94.jpg"}', '{}', NULL, NULL, 56, '2026-06-02 03:44:21.848997+00', '2026-06-02 03:44:21.848997+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 15, '{"contract_id": 23, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "paid", "deleted_file": "/data/contract-system/receipts/2026/06/0168e30a-389e-4034-922d-5cadf44c5f0a.jpg"}', '{}', NULL, NULL, 57, '2026-06-02 03:44:23.787832+00', '2026-06-02 03:44:23.787832+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 24, '{"contract_number": "HT2026060122213688B9", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT2026060122213688B9.pdf"]}', '{}', NULL, NULL, 58, '2026-06-02 03:44:27.545193+00', '2026-06-02 03:44:27.545193+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 23, '{"contract_number": "HT202606012154361AE8", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT202606012154361AE8.pdf"]}', '{}', NULL, NULL, 59, '2026-06-02 03:44:29.631321+00', '2026-06-02 03:44:29.631321+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 20, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 60, '2026-06-02 03:44:32.419147+00', '2026-06-02 03:44:32.419147+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 18, '{"contract_id": 26, "amount": 50000.0, "currency": "CNY", "type": "income", "status": "paid", "deleted_file": "/data/contract-system/receipts/2026/06/76a02d0f-ba11-4385-9ed4-3918107818f8.jpg"}', '{}', NULL, NULL, 61, '2026-06-02 06:24:16.263853+00', '2026-06-02 06:24:16.263853+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'payment', 17, '{"contract_id": 25, "amount": 50000.0, "currency": "HKD", "type": "income", "status": "paid", "deleted_file": "/data/contract-system/receipts/2026/06/90e3fcb4-41b3-4309-920b-a8929c7b6a1c.jpg"}', '{}', NULL, NULL, 62, '2026-06-02 06:24:19.486595+00', '2026-06-02 06:24:19.486595+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 25, '{"contract_number": "HT202606021145559EC1", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT202606021145559EC1.pdf"]}', '{}', NULL, NULL, 63, '2026-06-02 06:24:23.33823+00', '2026-06-02 06:24:23.33823+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'contract', 26, '{"contract_number": "HT20260602114813E545", "status": "active", "deleted_files": ["/data/contract-system/contracts/2026/06/HT20260602114813E545.pdf"]}', '{}', NULL, NULL, 64, '2026-06-02 06:24:25.575679+00', '2026-06-02 06:24:25.575679+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 21, '{"name": "\u80e1\u5c11\u68df", "phone": "97857999"}', '{}', NULL, NULL, 65, '2026-06-02 06:24:29.130365+00', '2026-06-02 06:24:29.130365+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'link_wechat_group', 'contract', 27, '{"wechat_group": null}', '{"wechat_group": "5\u670828\u65e517\u5e74\u767d\u5916\u9ed1\u518530\u7cfb\u57c3\u5c14\u6cd5(10)", "source": "user_manual"}', NULL, NULL, 66, '2026-06-02 07:25:15.674699+00', '2026-06-02 07:25:15.674699+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'link_wechat_group', 'contract', 28, '{"wechat_group": null}', '{"wechat_group": "5\u670828\u65e5\u80e1\u603b\u7cb5Z7N80\u6e2f\u6df1\u5733\u6e7e\u73b0\u724c(9)", "source": "user_manual"}', NULL, NULL, 67, '2026-06-02 07:26:48.047524+00', '2026-06-02 07:26:48.047524+00', 'f', NULL);
INSERT INTO "public"."audit_logs" VALUES (1, 'delete', 'customer', 23, '{"name": "\u9648\u4eae\u575b", "phone": "93499456"}', '{}', NULL, NULL, 68, '2026-06-03 07:26:55.173701+00', '2026-06-03 07:26:55.173701+00', 'f', NULL);

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
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'assistant', '', '好的，已提取到文件中的关键信息，汇总如下：

---

### 📄 车辆买卖合约关键信息

| 项目 | 内容 |
|------|------|
| **合同类型** | 车辆买卖合约（香港） |
| **甲方（卖方）** | **华星资源开发有限公司** |
| **乙方（客户）** | **陈亮坛**（证件号：M860682(5)） |
| **联系电话** | 93499456 |
| **车辆底盘号** | WAUZZZ4M8GD017658 |
| **总售价** | **108,000 HKD** |
| **已付定金** | **20,000 HKD**（2026年5月24日支付） |
| **尾款** | **88,000 HKD**（完成香港运输署过户当日支付） |
| **签订日期** | 2026年5月24日 |

---

请问需要根据以上信息，为客户 **陈亮坛** 创建这份车辆买卖合同记录吗？', NULL, NULL, NULL, NULL, 'deepseek-v4-flash', NULL, NULL, 'null', '{}', 801, '2026-06-03 08:28:35.905363+00', '2026-06-03 08:28:35.905363+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'user', '请分析上传的PDF内容，提取关键信息并总结', NULL, NULL, NULL, NULL, NULL, 'deepseek-v4-flash', NULL, NULL, 'null', '{"attachments": [{"file_id": "47efb5c2-8df1-412c-969c-007a192cb04f", "file_type": "pdf"}], "file_context": "[\u7cfb\u7edf\u5df2\u81ea\u52a8\u63d0\u53d6\u6587\u4ef6\u5185\u5bb9\uff0c\u8bf7\u52ff\u518d\u8c03\u7528 analyze_image \u5de5\u5177]\n\u6587\u4ef6\u7c7b\u578b\uff1aPDF\nfile_id\uff1a47efb5c2-8df1-412c-969c-007a192cb04f\n\u63d0\u53d6\u5185\u5bb9\uff1a\n\u660e\u54e5\u4e2d\u6e2f\u724c\n\u672c\u5408\u540c\u4e00\u5f0f\u5169\u4efd\uff0c\u7532\u3001\u4e59\u96d9\u65b9\u5404\u57f7\u4e00\u4efd\uff0c\u540c\u6642\u5177\u6709\u6cd5\u5f8b\u6548\u61c9\u3002\n\u8f66\u8f86\u4e70\u5356\u5408\u7ea6\uff08\u9999\u6e2f\uff09\n\u7532\u65b9\uff08\u5356\u65b9\uff09\uff1a\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\n\u8054\u7cfb\u4eba\uff1a\u9648\u7115\u660e\n\u8054\u7cfb\u7535\u8bdd\uff1a98702065\n\u4e59\u65b9\uff08\u59d4\u6258\u65b9\uff09\uff1a\n\u9648\u4eae\u575b\n\u8bc1\u4ef6\u7c7b\u578b\u53ca\u53f7\u7801\uff1a\nM860682(5)\n\u8054\u7cfb\u7535\u8bdd\uff1a\n93499456\n\u7ecf\u53cc\u65b9\u534f\u5546\uff0c\u73b0\u5c31\u4e70\u5356\u4e0b\u8ff0\u8f66\u8f86\u8ba2\u7acb\u672c\u5408\u7ea6\uff0c\u4ee5\u8d44\u5171\u540c\u9075\u5b88\u3002\n\u7b2c\u4e00\u6761\u8f66\u8f86\u8be6\u60c5\n1. \u8f66\u8eab\u5e95\u76d8\u53f7\u7801/\u8f66\u8f86\u8bc6\u522b\u53f7\u7801\uff1a\nWAUZZZ4M8GD017658\n\u7b2c\u4e8c\u6761\u8f66\u8f86\u552e\u4ef7\u4e0e\u652f\u4ed8\n1. \u8be5\u8f66\u8f86\u4e4b\u603b\u552e\u4ef7\u4e3a\u6e2f\u5e01\n\u58f9\u62fe\u4e07\u96f6\u634c\u4edf\n\u5143\u6574\uff08$ 108000 \uff09\u3002\n2. \u7b2c\u4e00\u671f\uff1a\u4e59\u65b9\u5df2\u4e8e2026 \u5e74\n5\n\u6708\n24\n\u65e5\u652f\u4ed8\u5b9a\u91d1\u6e2f\u5e01\n\u8d30\u4e07\n\u5143\u6574\n\uff08$ 20000\n\uff09\u3002\n3. \u5269\u4f59\u8f66\u8f86\u5c3e\u6b3e\u6e2f\u5e01\uff1a\n\u634c\u4e07\u634c\u4edf\n\u5143\u6574\uff08$ 88000\n\uff09\uff0c\u987b\u4e8e\u8be5\u8f66\u8f86\n\u5b8c\u6210\u9999\u6e2f\u8fd0\u8f93\u7f72\u8fc7\u6237\u767b\u8bb0\u624b\u7eed\u5f53\u65e5\uff0c\u7531\u4e59\u65b9\u4e00\u6b21\u6027\u652f\u4ed8\u7532\u65b9\u3002\n\u7b2c\u4e09\u6761\u8f66\u8f86\u73b0\u72b6\u4e0e\u63a5\u6536\n\u4e59\u65b9\u7279\u6b64\u786e\u8ba4\uff0c\u5176\u5df2\u5bf9\u8be5\u8f66\u8f86\u4e4b\u54c1\u724c\u3001\u578b\u53f7\u3001\u5e74\u4efd\u3001\u91cc\u7a0b\u3001\u6027\u80fd\u3001\u5916\u89c2\u3001\u5185\u9970\u3001\n\u673a\u4ef6\u53ca\u4e00\u5207\u73b0\u5b58\u72b6\u51b5\u8fdb\u884c\u4e86\u5145\u5206\u67e5\u9a8c\uff0c\u5e76\u5b8c\u5168\u4e86\u89e3\u4e0e\u63a5\u53d7\u3002\u4e59\u65b9\u540c\u610f\u4ee5\u8be5\u8f66\u8f86\u4e4b\n\u201c\u73b0\u72b6\u201d\u8d2d\u5165\uff0c\u7532\u65b9\u9664\u4fdd\u8bc1\u62e5\u6709\u5408\u6cd5\u6240\u6709\u6743\u5916\uff0c\u4e0d\u5c31\u8f66\u8f86\u4e4b\u8d28\u91cf\u3001\u6027\u80fd\u3001\u7455\u75b5\u6216\n\u9002\u7528\u6027\u4f5c\u51fa\u4efb\u4f55\u5176\u4ed6\u660e\u793a\u6216\u9ed8\u793a\u4e4b\u4fdd\u8bc1\u3002\n\u7b2c\u56db\u6761\u8f66\u8f86\u4ea4\u4ed8\u4e0e\u8d23\u4efb\n1. \u63d0\u8f66\u671f\u9650\uff1a\u4e59\u65b9\u5728\u4ed8\u6e05\u7b2c\u4e8c\u6761\u7ea6\u5b9a\u7684\u5168\u90e8\u5c3e\u6b3e\u540e\uff0c\u987b\u4e8e\u4e09\uff083\uff09\u4e2a\u5de5\u4f5c\u65e5\u5185\uff0c\n\u4eb2\u8d74\u7532\u65b9\u6307\u5b9a\u5730\u70b9\u63d0\u53d6\u8be5\u8f66\u8f86\u3002\n2. \u903e\u671f\u505c\u8f66\u8d39\uff1a\u82e5\u4e59\u65b9\u672a\u80fd\u5728\u4e0a\u8ff0\u7ea6\u5b9a\u671f\u9650\u5185\u63d0\u8d70\u8f66\u8f86\uff0c\u6bcf\u903e\u671f\u4e00\u65e5\uff0c\u987b\u5411\u7532\n\u65b9\u652f\u4ed8\u505c\u8f66\u8d39\u6e2f\u5e01\u58f9\u4f70\u5143\u6574\uff08HK$100\uff09\u3002\u7532\u65b9\u6709\u6743\u5c06\u8f66\u8f86\u79fb\u81f3\u5176\u4ed6\u5730\u70b9\u505c\u653e\uff0c\n\u76f8\u5173\u98ce\u9669\u4e0e\u8d39\u7528\u7531\u4e59\u65b9\u627f\u62c5\u3002\n3. \u98ce\u9669\u8f6c\u79fb\uff1a\u81ea\u8be5\u8f66\u8f86\u4e8e\u8fd0\u8f93\u7f72\u5b8c\u6210\u8fc7\u6237\u767b\u8bb0\u4e4b\u65e5\u8d77\uff0c\u65e0\u8bba\u4e59\u65b9\u662f\u5426\u5df2\u63d0\u8f66\uff0c\n\u8be5\u8f66\u8f86\u4e4b\u4e00\u5207\u98ce\u9669\uff08\u5982\u635f\u6bc1\u3001\u5931\u7a83\uff09\u53ca\u4e00\u5207\u76f8\u5173\u8d39\u7528\u4e0e\u6cd5\u5f8b\u8d23\u4efb\uff08\u5982\u7f5a\u6b3e\u3001\u4e8b\u6545\uff09\n\u5747\u8f6c\u79fb\u7531\u4e59\u65b9\u627f\u62c5\u3002\n\u7b2c\u4e94\u6761\u6587\u4ef6\u4e0e\u8fc7\u6237\n1. \u7532\u65b9\u4fdd\u8bc1\u62e5\u6709\u8be5\u8f66\u8f86\u4e4b\u5408\u6cd5\u6240\u6709\u6743\uff0c\u5e76\u627f\u8bfa\u8be5\u8f66\u8f86\u4e0d\u9644\u5e26\u4efb\u4f55\u62b5\u62bc\u6216\u6cd5\u5f8b\u7ea0\n\u7eb7\u3002\n2. \u7532\u65b9\u5e94\u914d\u5408\u63d0\u4f9b\u529e\u7406\u8fc7\u6237\u6240\u9700\u4e4b\u8f66\u8f86\u767b\u8bb0\u6587\u4ef6\uff08\u724c\u7c3f\uff09\u7b49\u3002\n\n\u660e\u54e5\u4e2d\u6e2f\u724c\n\u672c\u5408\u540c\u4e00\u5f0f\u5169\u4efd\uff0c\u7532\u3001\u4e59\u96d9\u65b9\u5404\u57f7\u4e00\u4efd\uff0c\u540c\u6642\u5177\u6709\u6cd5\u5f8b\u6548\u61c9\u3002\n\u7b2c\u516d\u6761\u4fdd\u9669\n\u4e59\u65b9\u987b\u81ea\u884c\u8d2d\u4e70\u6709\u6548\u7684\u6c7d\u8f66\u4fdd\u9669\u3002\n\u7b2c\u4e03\u6761\u8fdd\u7ea6\u8d23\u4efb\n\u82e5\u4e59\u65b9\u672a\u6309\u672c\u5408\u540c\u7ea6\u5b9a\u652f\u4ed8\u5c3e\u6b3e\u6216\u63d0\u53d6\u8f66\u8f86\uff0c\u7532\u65b9\u6709\u6743\u6ca1\u6536\u5b9a\u91d1\uff0c\u5e76\u53ef\u5c06\u8f66\u8f86\u53e6\n\u884c\u51fa\u552e\u3002\n\u7b2c\u516b\u6761\u5176\u4ed6\n1. \u672c\u5408\u7ea6\u53d7\u9999\u6e2f\u7279\u522b\u884c\u653f\u533a\u6cd5\u5f8b\u7ba1\u8f96\u3002\n2. \u4efb\u4f55\u4e89\u8bae\uff0c\u5e94\u63d0\u4ea4\u9999\u6e2f\u6cd5\u9662\u8bc9\u8bbc\u89e3\u51b3\u3002\n3. \u672c\u5408\u7ea6\u4e00\u5f0f\u4e24\u4efd\uff0c\u53cc\u65b9\u5404\u6267\u4e00\u4efd\uff0c\u81ea\u7b7e\u7f72\u4e4b\u65e5\u8d77\u751f\u6548\u3002\n\u7532\u65b9\u7b7e\u7f72\uff1a\n\u516c\u53f8\u540d\u79f0\uff1a\n\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\n\u6388\u6743\u4ee3\u8868\u7b7e\u7f72\uff1a\n\u59d3\u540d\uff1a\n\u65e5\u671f\uff1a\n2026\n\u5e74\n5\n\u6708\n24\n\u65e5\n\u4e59\u65b9\u7b7e\u7f72\uff1a\n\u59d3\u540d/\u516c\u53f8\u540d\u79f0\uff1a\n\u65e5\u671f\uff1a\n2026\n\u5e74\n5\n\u6708\n24\n\u65e5\n\n\u8bf7\u76f4\u63a5\u57fa\u4e8e\u4ee5\u4e0a\u5185\u5bb9\u5411\u7528\u6237\u5c55\u793a\u5173\u952e\u4fe1\u606f\uff0c\u8be2\u95ee\u662f\u5426\u9700\u8981\u521b\u5efa\u5408\u540c\u3002"}', 802, '2026-06-03 08:28:40.350501+00', '2026-06-03 08:28:40.350501+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'assistant', '', '好的，马上为您创建合同！先查询客户是否存在', NULL, NULL, NULL, NULL, 'deepseek-v4-flash', NULL, NULL, '[{"id": "call_f408f9e11b984ecd88feb36b", "type": "function", "function": {"name": "search_customers", "arguments": "{\"name\": \"\u9648\u4eae\u575b\"}"}}]', '{}', 803, '2026-06-03 08:28:53.996588+00', '2026-06-03 08:28:53.996588+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'user', 'OK', NULL, NULL, NULL, NULL, NULL, 'deepseek-v4-flash', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 804, '2026-06-03 08:28:55.65706+00', '2026-06-03 08:28:55.65706+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'tool', '', '{"customers": [], "total": 0}', NULL, 'search_customers', NULL, NULL, 'deepseek-v4-flash', NULL, NULL, NULL, '{"tool_call_id": "call_f408f9e11b984ecd88feb36b"}', 805, '2026-06-03 08:28:55.671173+00', '2026-06-03 08:28:55.671173+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'assistant', '', '客户陈亮坛不存在，我先创建客户档案', NULL, NULL, NULL, NULL, 'deepseek-v4-flash', NULL, NULL, '[{"id": "call_8dc3590c174548088bd631b5", "type": "function", "function": {"name": "create_customer", "arguments": "{\"name\": \"\u9648\u4eae\u575b\", \"phone\": \"93499456\", \"id_card_number\": \"M860682(5)\"}"}}]', '{}', 806, '2026-06-03 08:28:59.534715+00', '2026-06-03 08:28:59.534715+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'tool', '', '{"success": true, "customer": {"id": 24, "name": "陈亮坛", "phone": "93499456", "email": null, "wechat_group_name": null}, "created": true, "message": "客户创建成功"}', NULL, 'create_customer', NULL, NULL, 'deepseek-v4-flash', NULL, NULL, NULL, '{"tool_call_id": "call_8dc3590c174548088bd631b5"}', 807, '2026-06-03 08:28:59.551529+00', '2026-06-03 08:28:59.551529+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'assistant', '', '客户陈亮坛已创建成功！现在为您生成合同记录', NULL, NULL, NULL, NULL, 'deepseek-v4-flash', NULL, NULL, '[{"id": "call_d022c6f7301145b3b6a9da49", "type": "function", "function": {"name": "create_contract", "arguments": "{\"customer_id\": 24, \"file_id\": \"47efb5c2-8df1-412c-969c-007a192cb04f\", \"title\": \"\u8f66\u8f86\u4e70\u5356\u5408\u7ea6\uff08\u9999\u6e2f\uff09\", \"total_amount\": 108000, \"currency\": \"HKD\", \"signed_date\": \"2026-05-24\", \"business_type\": \"\u8f66\u8f86\u4e1a\u52a1\", \"business_description\": \"\u4e70\u5356\u5965\u8fea\u8f66\u8f86\uff08\u5e95\u76d8\u53f7WAUZZZ4M8GD017658\uff09\uff0c\u603b\u552e\u4ef7108,000 HKD\uff0c\u5df2\u4ed8\u5b9a\u91d120,000 HKD\uff0c\u5c3e\u6b3e88,000 HKD\u987b\u4e8e\u5b8c\u6210\u9999\u6e2f\u8fd0\u8f93\u7f72\u8fc7\u6237\u767b\u8bb0\u624b\u7eed\u5f53\u65e5\u652f\u4ed8\"}"}}]', '{}', 808, '2026-06-03 08:29:03.377481+00', '2026-06-03 08:29:03.377481+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'tool', '', '{"success": true, "contract": {"id": 29, "contract_number": "HT2026060316290356B3", "customer_name": "陈亮坛", "customer_id": 24, "title": "车辆买卖合约（香港）", "currency": "HKD", "total_amount": 108000.0, "status": "active", "confidence": null, "needs_review": false, "wechat_group": null, "signed_date": "2026-05-24"}, "auto_payments": []}', NULL, 'create_contract', NULL, NULL, 'deepseek-v4-flash', NULL, NULL, NULL, '{"tool_call_id": "call_d022c6f7301145b3b6a9da49"}', 809, '2026-06-03 08:29:03.414941+00', '2026-06-03 08:29:03.414941+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'assistant', '', '✅ **合同创建成功！** 以下是合同摘要：

---

### 📋 合同信息

| 项目 | 内容 |
|------|------|
| **合同编号** | **HT2026060316290356B3** |
| **客户** | 陈亮坛（电话：93499456） |
| **合同标题** | 车辆买卖合约（香港） |
| **总售价** | **108,000 HKD** |
| **签订日期** | 2026年5月24日 |
| **状态** | **进行中** 🟢 |

### 💰 付款进度
| 期数 | 金额 | 状态 |
|:----:|:----:|:----:|
| ① **定金** | 20,000 HKD | 已支付（无凭证） |
| ② **尾款** | 88,000 HKD | 待支付（过户当日付清） |

---

合同中提到定金 **20,000 HKD** 已于5月24日支付，请问您是否有该笔定金的付款凭证需要上传？', NULL, NULL, NULL, NULL, 'deepseek-v4-flash', NULL, NULL, 'null', '{}', 810, '2026-06-03 08:29:06.997115+00', '2026-06-03 08:29:06.997115+00', 'f', NULL);
INSERT INTO "public"."chat_history" VALUES (1, '03b1c45e-283f-437d-9a79-9c764c3f78df', 'user', 'OK', NULL, NULL, NULL, NULL, NULL, 'deepseek-v4-flash', NULL, NULL, 'null', '{"attachments": null, "file_context": ""}', 811, '2026-06-03 08:29:07.001224+00', '2026-06-03 08:29:07.001224+00', 'f', NULL);

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
INSERT INTO "public"."contracts" VALUES ('HT202606021427370BC3', '两地车牌指标过户服务合约', 22, 1, 'CNY', 240000.00, 50000.00, 190000.00, NULL, 0.00, NULL, '2026/06/HT202606021427370BC3.pdf', '33ee97e02357ecc6a802f0c70c4d20e300c7683d59a4920e147e519f06193e52', '{"source": "agent", "file_id": "e17e71d6-7e22-4a4d-a876-ca7431a26257", "data_source": "cache", "contract_number": null, "title": "\u4e24\u5730\u8f66\u724c\u6307\u6807\u8fc7\u6237\u670d\u52a1\u5408\u7ea6", "signed_date": "2026-05-28", "business_type": "\u4e2d\u6e2f\u724c\u4e1a\u52a1", "business_description": "\u8d2d\u4e70\u73b0\u724c \u7ca4Z7N80\u6e2f \u6df1\u5733\u6e7e\u53e3\u5cb8", "party_a": {"name": "\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8", "contact": "98702065", "address": null}, "party_b": {"name": "\u80e1\u5c11\u68df", "id_type": "\u8bc1\u4ef6\u7c7b\u578b\u53ca\u53f7\u7801", "id_number": "F420825(7)", "phone": "97857999"}, "vehicle_info": {"plate_number": "\u7ca4Z7N80\u6e2f", "vehicle_model": null, "registration_number": null}, "port": "\u6df1\u5733\u6e7e", "service_items": [{"name": "\u6838\u5fc3\u670d\u52a1", "description": "\u7532\u65b9\u8d1f\u8d23\u5b89\u6392\u5e76\u529e\u7406\u76ee\u6807\u516c\u53f8\u7684\u80a1\u6743\u8fc7\u6237\u81f3\u4e59\u65b9\u540d\u4e0b\u7684\u5168\u5957\u6cd5\u5f8b\u624b\u7eed\uff0c\u4ee5\u53ca\u540e\u7eed\u5c06\u4e24\u5730\u8f66\u724c\u6307\u6807\u6362\u6302\u81f3\u4e59\u65b9\u6307\u5b9a\u8f66\u8f86\u7684\u8fc7\u6237\u624b\u7eed\u3002", "amount": 240000}, {"name": "\u6362\u8f66\u670d\u52a1", "description": "\u7532\u65b9\u5c06\u4e3a\u4e59\u65b9\u63d0\u4f9b\u5168\u5957\u6362\u8f66\u534f\u8c03\u670d\u52a1\u3002\u8be5\u670d\u52a1\u5305\u62ec\u4f46\u4e0d\u9650\u4e8e\uff1a\u534f\u52a9\u51c6\u5907\u53ca\u63d0\u4ea4\u6362\u8f66\u6587\u4ef6\u3001\u8ddf\u8fdb\u7533\u8bf7\u8fdb\u5ea6\uff1b\u6362\u8f66\u8d39\u7528\uffe55000\u3002", "amount": 5000}], "payment_terms": [{"name": "\u5b9a\u91d1", "amount": 50000, "due_date": "2026-05-28", "condition": "\u672c\u5408\u7ea6\u7b7e\u8ba2\u5f53\u65e5\uff0c\u4e59\u65b9\u5e94\u5411\u7532\u65b9\u652f\u4ed8\u5b9a\u91d1", "is_paid": false}, {"name": "\u5269\u4f59\u6b3e\u9879", "amount": 190000, "due_date": null, "condition": "\u5728\u7532\u65b9\u5b8c\u6210\u76ee\u6807\u516c\u53f8\u7684\u80a1\u6743\u8f6c\u8ba9\u6cd5\u5f8b\u6587\u4ef6\uff08\u4ee5\u76f8\u5173\u6587\u4ef6\u7b7e\u7f72\u5b8c\u6210\u4e3a\u51c6\uff09\u5e76\u4e66\u9762\u901a\u77e5\u4e59\u65b9\u4e4b\u5f53\u65e5\uff0c\u4e59\u65b9\u5fc5\u987b\u652f\u4ed8\u5269\u4f59\u6b3e\u9879", "is_paid": false}], "total_amount": 240000, "currency": "CNY", "validity_period": {"start_date": "2026-05-28", "end_date": null}, "special_terms": ["\u82e5\u4e59\u65b9\u652f\u4ed8\u5b9a\u91d1\u540e\u5355\u65b9\u89e3\u9664\u5408\u7ea6\uff0c\u5df2\u4ed8\u5b9a\u91d1\u4e0d\u4e88\u9000\u8fd8\u3002", "\u82e5\u56e0\u4e59\u65b9\u672a\u80fd\u6309\u65f6\u652f\u4ed8\u5404\u671f\u6b3e\u9879\u3001\u63d0\u4f9b\u8d44\u6599\u6216\u914d\u5408\u529e\u7406\uff0c\u5bfc\u81f4\u670d\u52a1\u5ef6\u8bef\u6216\u4ea7\u751f\u989d\u5916\u6210\u672c\uff0c\u5168\u90e8\u8d23\u4efb\u53ca\u8d39\u7528\u7531\u4e59\u65b9\u627f\u62c5\uff0c\u4e14\u7532\u65b9\u6709\u6743\u6682\u505c\u670d\u52a1\u3002", "\u82e5\u56e0\u7532\u65b9\u8fc7\u9519\u5bfc\u81f4\u516c\u53f8\u8fc7\u6237\u6216\u8f66\u724c\u6362\u6302\u7a0b\u5e8f\u5931\u8d25\uff0c\u7532\u65b9\u5e94\u9000\u8fd8\u5df2\u6536\u53d6\u7684\u670d\u52a1\u8d39\u3002"], "confidence": 0.95, "full_text": "\u660e\u54e5\u4e2d\u6e2f\u724c\n\u672c\u5408\u540c\u4e00\u5f0f\u5169\u4efd\uff0c\u7532\u3001\u4e59\u96d9\u65b9\u5404\u57f7\u4e00\u4efd\uff0c\u540c\u6642\u5177\u6709\u6cd5\u5f8b\u6548\u61c9\u3002\n\u4e24\u5730\u8f66\u724c\u6307\u6807\u8fc7\u6237\u670d\u52a1\u5408\u7ea6\n\u7532\u65b9\uff08\u670d\u52a1\u65b9\uff09\uff1a\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\n\u8054\u7cfb\u7535\u8bdd\uff1a98702065\n\u4e59\u65b9\uff08\u59d4\u6258\u65b9\uff09\uff1a\n\u80e1\u5c11\u68df\n\u8bc1\u4ef6\u7c7b\u578b\u53ca\u53f7\u7801\uff1a\nF420825(7)\n\u8054\u7edc\u7535\u8bdd\uff1a\n97857999\n\u7532\u3001\u4e59\u53cc\u65b9\u5728\u5e73\u7b49\u81ea\u613f\u7684\u57fa\u7840\u4e0a\uff0c\u5c31\u7532\u65b9\u4e3a\u4e59\u65b9\u63d0\u4f9b\u7ca4\u6e2f\u4e24\u5730\u8f66\u724c\u6307\u6807\uff08\u201c\u4e24\u5730\n\u724c\u201d\uff09\u8fc7\u6237\u53ca\u76f8\u5173\u670d\u52a1\u4e8b\u5b9c\uff0c\u8fbe\u6210\u5982\u4e0b\u5408\u7ea6\u6761\u6b3e\uff0c\u4ee5\u8d44\u5171\u540c\u9075\u5b88\u3002\n\u7b2c\u4e00\u6761\u670d\u52a1\u6807\u7684\u4e0e\u5b9a\u4e49\n1. \u670d\u52a1\u6807\u7684\uff1a\u6307\u4e59\u65b9\u62df\u8d2d\u5165\u7684\u3001\u5df2\u5177\u5907\u6709\u6548\u7ca4\u6e2f\u4e24\u5730\u901a\u8f66\u8d44\u683c\u7684\u73b0\u6210\u8f66\u724c\u6307\u6807\n\u53ca\u5176\u5bf9\u5e94\u7684\uff1a\n\u8f66\u724c\u53f7\uff1a\n\u7ca4Z7N80 \u6e2f\n\u901a\u884c\u53e3\u5cb8\uff1a\n\u6df1\u5733\u6e7e\n2. \u516c\u53f8\u8fc7\u6237\uff1a\u6307\u5c06\u76ee\u6807\u516c\u53f8\u7684\u5168\u90e8\u5df2\u53d1\u884c\u80a1\u4efd\u8f6c\u8ba9\u81f3\u4e59\u65b9\u6216\u5176\u6307\u5b9a\u4eba\u58eb\u540d\u4e0b\uff0c\n\u4ece\u800c\u4f7f\u4e59\u65b9\u95f4\u63a5\u6301\u6709\u8be5\u4e24\u5730\u8f66\u724c\u6307\u6807\u7684\u884c\u4e3a\u3002\n3. \u6362\u8f66\u670d\u52a1\uff1a\u6307\u5728\u8f66\u724c\u6307\u6807\u8fc7\u6237\u5b8c\u6210\u540e\uff0c\u534f\u52a9\u4e59\u65b9\u529e\u7406\u5c06\u8f66\u724c\u6307\u6807\u4ece\u539f\u6709\u8f66\u8f86\n\u8f6c\u6362\u6302\u8f7d\u81f3\u5176\u6307\u5b9a\u65b0\u8f66\u8f86\u4e0a\u7684\u5168\u5957\u624b\u7eed\u3002\n\u7b2c\u4e8c\u6761\u9648\u8ff0\u4e0e\u4fdd\u8bc1\n1.\u7532\u65b9\u9648\u8ff0\u5e76\u4fdd\u8bc1:\u622a\u81f3\u672c\u5408\u7ea6\u7b7e\u7f72\u4e4b\u65e5\uff0c\u76ee\u6807\u9999\u6e2f\u516c\u53f8\u4e0d\u5b58\u5728\u4efb\u4f55\u672a\u7ed3\u6e05\u7684\u503a\u52a1\u3001\n\u7a0e\u52a1\u7ea0\u7eb7\u3001\u672a\u51b3\u8bc9\u8bbc\u6216\u884c\u653f\u5904\u7f5a\uff0c\u516c\u53f8\u8fd0\u4f5c\u5b8c\u5168\u7b26\u5408\u9999\u6e2f\u76f8\u5173\u6cd5\u5f8b\u6cd5\u89c4\u3002\n2.\u4e59\u65b9\u8d23\u4efb\u8c41\u514d:\u4e59\u65b9\u6210\u529f\u8d2d\u5165\u76ee\u6807\u9999\u6e2f\u516c\u53f8\u540e\uff0c\u4ec5\u4f5c\u4e3a\u5176\u80a1\u6743\u53d7\u8ba9\u65b9\uff0c\u65e0\u9700\u627f\u62c5\n\u8be5\u76ee\u6807\u9999\u6e2f\u516c\u53f8\u53ca\u76ee\u6807\u5927\u9646\u516c\u53f8\u5728\u672c\u6b21\u80a1\u6743\u8f6c\u8ba9\u5b8c\u6210\u65e5(\u4ee5\u516c\u53f8\u6ce8\u518c\u5904\u767b\u8bb0\u4e3a\u51c6)\n\u4e4b\u524d\u6240\u4ea7\u751f\u7684\u4efb\u4f55\u5386\u53f2\u503a\u52a1\u3001\u6cd5\u5f8b\u8d23\u4efb\u6216\u8fdd\u89c4\u540e\u679c\u3002\u8be5\u7b49\u8d23\u4efb\u5747\u5e94\u7531\u8f6c\u8ba9\u524d\u7684\u80a1\n\u4e1c\u53ca\u516c\u53f8\u539f\u8d1f\u8d23\u4eba\u627f\u62c5\u3002\n\u7b2c\u4e09\u6761\u670d\u52a1\u603b\u8d39\u7528\u53ca\u652f\u4ed8\u65b9\u5f0f\n1. \u670d\u52a1\u603b\u8d39\u7528\uff1a\u672c\u6b21\u670d\u52a1\u4e4b\u5168\u90e8\u8d39\u7528\u603b\u8ba1\u4e3a\u4eba\u6c11\u5e01\n\u8d30\u62fe\u8086\u4e07\n\u5143\u6574\n\uff08\u00a5\n240000\n\uff09\u3002\n2. \u4ed8\u6b3e\u5b89\u6392\uff1a\n\uff081\uff09\u5b9a\u91d1\uff1a\u672c\u5408\u7ea6\u7b7e\u8ba2\u5f53\u65e5\uff0c\u4e59\u65b9\u5e94\u5411\u7532\u65b9\u652f\u4ed8\u5b9a\u91d1\u4eba\u6c11\u5e01\u4f0d\u4e07\n\u5143\u6574\uff08\uffe5\n50000\n\uff09\u3002\u7532\u65b9\u5728\u6536\u5230\u5b9a\u91d1\u540e\u5f00\u59cb\u542f\u52a8\u670d\u52a1\u7a0b\u5e8f\u3002\n\uff082\uff09\u5269\u4f59\u6b3e\u9879\uff1a\u5728\u7532\u65b9\u5b8c\u6210\u76ee\u6807\u516c\u53f8\u7684\u80a1\u6743\u8f6c\u8ba9\u6cd5\u5f8b\u6587\u4ef6\uff08\u4ee5\u76f8\u5173\u6587\u4ef6\u7b7e\u7f72\n\u5b8c\u6210\u4e3a\u51c6\uff09\u5e76\u4e66\u9762\u901a\u77e5\u4e59\u65b9\u4e4b\u5f53\u65e5\uff0c\u4e59\u65b9\u5fc5\u987b\u652f\u4ed8\u5269\u4f59\u6b3e\u9879\u4eba\u6c11\u5e01\n\u58f9\u62fe\u7396\u4e07\n\u6574\uff08\uffe5\n190000\n\uff09\u3002\n\n\u660e\u54e5\u4e2d\u6e2f\u724c\n\u672c\u5408\u540c\u4e00\u5f0f\u5169\u4efd\uff0c\u7532\u3001\u4e59\u96d9\u65b9\u5404\u57f7\u4e00\u4efd\uff0c\u540c\u6642\u5177\u6709\u6cd5\u5f8b\u6548\u61c9\u3002\n\u7b2c\u56db\u6761\u7532\u65b9\u670d\u52a1\u5185\u5bb9\u4e0e\u8d23\u4efb\n1. \u6838\u5fc3\u670d\u52a1\uff1a\u7532\u65b9\u8d1f\u8d23\u5b89\u6392\u5e76\u529e\u7406\u76ee\u6807\u516c\u53f8\u7684\u80a1\u6743\u8fc7\u6237\u81f3\u4e59\u65b9\u540d\u4e0b\u7684\u5168\u5957\u6cd5\u5f8b\n\u624b\u7eed\uff0c\u4ee5\u53ca\u540e\u7eed\u5c06\u4e24\u5730\u8f66\u724c\u6307\u6807\u6362\u6302\u81f3\u4e59\u65b9\u6307\u5b9a\u8f66\u8f86\u7684\u8fc7\u6237\u624b\u7eed\u3002\n2. \u6362\u8f66\u670d\u52a1\uff1a\u7532\u65b9\u5c06\u4e3a\u4e59\u65b9\u63d0\u4f9b\u5168\u5957\u6362\u8f66\u534f\u8c03\u670d\u52a1\u3002\u8be5\u670d\u52a1\u5305\u62ec\u4f46\u4e0d\u9650\u4e8e\uff1a\u534f\n\u52a9\u51c6\u5907\u53ca\u63d0\u4ea4\u6362\u8f66\u6587\u4ef6\u3001\u8ddf\u8fdb\u7533\u8bf7\u8fdb\u5ea6\uff1b\u6362\u8f66\u8d39\u7528\n\uffe55000\n\u3002\n3. \u7532\u65b9\u63d0\u4f9b\u7684\u670d\u52a1\u542b\u529e\u7406\u8fc7\u7a0b\u4e2d\u4ea7\u751f\u7684\u6240\u6709\u653f\u5e9c\u5b98\u65b9\u6536\u8d39\u53ca\u7b2c\u4e09\u65b9\u5fc5\u8981\u8d39\u7528\uff0c\n\u5305\u62ec\u4f46\u4e0d\u9650\u4e8e\uff1a\u4e2d\u56fd\u5927\u9646\u90e8\u5206\u7684\u8f66\u8f86\u4fdd\u9669\u8d39\uff1b\u6b64\u8d39\u7528\u5747\u9700\u7531\u4e59\u65b9\u53e6\u884c\u627f\u62c5\u5e76\u76f4\u63a5\n\u652f\u4ed8\u7ed9\u76f8\u5173\u673a\u6784\u6216\u901a\u8fc7\u7532\u65b9\u4ee3\u7f34\u3002\n\u7b2c\u4e94\u6761\u4e59\u65b9\u8d23\u4efb\u4e0e\u4fdd\u8bc1\n1. \u53ca\u65f6\u4ed8\u6b3e\uff1a\u4e59\u65b9\u987b\u4e25\u683c\u6309\u672c\u5408\u7ea6\u7b2c\u4e8c\u6761\u7ea6\u5b9a\u7684\u65f6\u95f4\u53ca\u91d1\u989d\u652f\u4ed8\u5404\u671f\u6b3e\u9879\u3002\n2. \u63d0\u4f9b\u8d44\u6599\uff1a\u4e59\u65b9\u987b\u6839\u636e\u529e\u7406\u8fdb\u5ea6\uff0c\u53ca\u65f6\u3001\u771f\u5b9e\u3001\u51c6\u786e\u5730\u63d0\u4f9b\u7532\u65b9\u8981\u6c42\u7684\u5404\u7c7b\n\u8eab\u4efd\u8bc1\u660e\u3001\u8bc1\u4ef6\u53ca\u6587\u4ef6\u8d44\u6599\uff08\u5305\u62ec\u5176\u6307\u5b9a\u7684\u9999\u6e2f\u516c\u53f8\u80a1\u4e1c\u3001\u8463\u4e8b\u8d44\u6599\u53ca\u6307\u5b9a\u8f66\u8f86\n\u6587\u4ef6\uff09\uff0c\u5e76\u4e88\u4ee5\u914d\u5408\u3002\n3. \u627f\u62c5\u5b98\u8d39\uff1a\u4e59\u65b9\u987b\u627f\u62c5\u672c\u5408\u7ea6\u7b2c\u4e09\u6761\u6240\u5217\u660e\u7684\u4e00\u5207\u653f\u5e9c\u5b98\u65b9\u6536\u8d39\u53ca\u7b2c\u4e09\u65b9\u8d39\n\u7528\u3002\n\u7b2c\u516d\u6761\u514d\u8d23\u58f0\u660e\u53ca\u98ce\u9669\u63d0\u793a\n1. \u7532\u65b9\u63d0\u4f9b\u7684\u670d\u52a1\u4e3a\u7a0b\u5e8f\u6027\u4ee3\u529e\u53ca\u534f\u52a9\uff0c\u4e0d\u5bf9\u4e2d\u56fd\u5185\u5730\u6216\u9999\u6e2f\u653f\u5e9c\u90e8\u95e8\uff08\u5982\u5e7f\n\u4e1c\u7701\u516c\u5b89\u5385\u3001\u9999\u6e2f\u8fd0\u8f93\u7f72\u7b49\uff09\u7684\u5ba1\u6279\u7ed3\u679c\u3001\u65f6\u957f\u4f5c\u51fa\u4efb\u4f55\u4fdd\u8bc1\u3002\n\u7b2c\u4e03\u6761\u8fdd\u7ea6\u8d23\u4efb\n1. \u82e5\u4e59\u65b9\u652f\u4ed8\u5b9a\u91d1\u540e\u5355\u65b9\u89e3\u9664\u5408\u7ea6\uff0c\u5df2\u4ed8\u5b9a\u91d1\u4e0d\u4e88\u9000\u8fd8\u3002\n2. \u82e5\u56e0\u4e59\u65b9\u672a\u80fd\u6309\u65f6\u652f\u4ed8\u5404\u671f\u6b3e\u9879\u3001\u63d0\u4f9b\u8d44\u6599\u6216\u914d\u5408\u529e\u7406\uff0c\u5bfc\u81f4\u670d\u52a1\u5ef6\u8bef\u6216\u4ea7\n\u751f\u989d\u5916\u6210\u672c\uff0c\u5168\u90e8\u8d23\u4efb\u53ca\u8d39\u7528\u7531\u4e59\u65b9\u627f\u62c5\uff0c\u4e14\u7532\u65b9\u6709\u6743\u6682\u505c\u670d\u52a1\u3002\n3. \u82e5\u56e0\u7532\u65b9\u8fc7\u9519\u5bfc\u81f4\u516c\u53f8\u8fc7\u6237\u6216\u8f66\u724c\u6362\u6302\u7a0b\u5e8f\u5931\u8d25\uff0c\u7532\u65b9\u5e94\u9000\u8fd8\u5df2\u6536\u53d6\u7684\u670d\u52a1\n\u8d39\u3002\n\u7b2c\u516b\u6761\u5176\u4ed6\n1. \u6cd5\u5f8b\u9002\u7528\u4e0e\u4e89\u8bae\u89e3\u51b3\uff1a\u672c\u5408\u7ea6\u53d7\u9999\u6e2f\u7279\u522b\u884c\u653f\u533a\u6cd5\u5f8b\u7ba1\u8f96\u3002\u4efb\u4f55\u4e89\u8bae\uff0c\u53cc\u65b9\n\u5e94\u53cb\u597d\u534f\u5546\u89e3\u51b3\uff1b\u534f\u5546\u4e0d\u6210\u7684\uff0c\u4efb\u4f55\u4e00\u65b9\u53ef\u5411\u7532\u65b9\u6240\u5728\u5730\u4e4b\u9999\u6e2f\u6cd5\u9662\u63d0\u8d77\u8bc9\u8bbc\u3002\n\u7532\u65b9\uff08\u76d6\u7ae0\uff09\uff1a\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\n\u6388\u6743\u4ee3\u8868\u7b7e\u7f72\uff1a\n\u65e5\u671f\uff1a\n2026\n\u5e74\n5\n\u6708\n28 \u65e5\n\u4e59\u65b9\uff08\u7b7e\u7f72\uff09\uff1a\n\u65e5\u671f\uff1a\n2026\n\u5e74\n5\n\u6708\n28 \u65e5"}', 0.9500, 'f', 'active', '2026-05-28', '2026-05-28', NULL, NULL, 1, 28, '2026-06-02 06:27:37.25769+00', '2026-06-02 07:26:48.036412+00', 'f', NULL, '中港牌业务', '购买现牌 粤Z7N80港 深圳湾口岸', '5月28日胡总粵Z7N80港深圳湾现牌(9)', 0.00, 0.00, '明哥中港牌
本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。
两地车牌指标过户服务合约
甲方（服务方）：华星资源开发有限公司
联系电话：98702065
乙方（委托方）：
胡少棟
证件类型及号码：
F420825(7)
联络电话：
97857999
甲、乙双方在平等自愿的基础上，就甲方为乙方提供粤港两地车牌指标（“两地
牌”）过户及相关服务事宜，达成如下合约条款，以资共同遵守。
第一条服务标的与定义
1. 服务标的：指乙方拟购入的、已具备有效粤港两地通车资格的现成车牌指标
及其对应的：
车牌号：
粤Z7N80 港
通行口岸：
深圳湾
2. 公司过户：指将目标公司的全部已发行股份转让至乙方或其指定人士名下，
从而使乙方间接持有该两地车牌指标的行为。
3. 换车服务：指在车牌指标过户完成后，协助乙方办理将车牌指标从原有车辆
转换挂载至其指定新车辆上的全套手续。
第二条陈述与保证
1.甲方陈述并保证:截至本合约签署之日，目标香港公司不存在任何未结清的债务、
税务纠纷、未决诉讼或行政处罚，公司运作完全符合香港相关法律法规。
2.乙方责任豁免:乙方成功购入目标香港公司后，仅作为其股权受让方，无需承担
该目标香港公司及目标大陆公司在本次股权转让完成日(以公司注册处登记为准)
之前所产生的任何历史债务、法律责任或违规后果。该等责任均应由转让前的股
东及公司原负责人承担。
第三条服务总费用及支付方式
1. 服务总费用：本次服务之全部费用总计为人民币
贰拾肆万
元整
（¥
240000
）。
2. 付款安排：
（1）定金：本合约签订当日，乙方应向甲方支付定金人民币伍万
元整（￥
50000
）。甲方在收到定金后开始启动服务程序。
（2）剩余款项：在甲方完成目标公司的股权转让法律文件（以相关文件签署
完成为准）并书面通知乙方之当日，乙方必须支付剩余款项人民币
壹拾玖万
整（￥
190000
）。

明哥中港牌
本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。
第四条甲方服务内容与责任
1. 核心服务：甲方负责安排并办理目标公司的股权过户至乙方名下的全套法律
手续，以及后续将两地车牌指标换挂至乙方指定车辆的过户手续。
2. 换车服务：甲方将为乙方提供全套换车协调服务。该服务包括但不限于：协
助准备及提交换车文件、跟进申请进度；换车费用
￥5000
。
3. 甲方提供的服务含办理过程中产生的所有政府官方收费及第三方必要费用，
包括但不限于：中国大陆部分的车辆保险费；此费用均需由乙方另行承担并直接
支付给相关机构或通过甲方代缴。
第五条乙方责任与保证
1. 及时付款：乙方须严格按本合约第二条约定的时间及金额支付各期款项。
2. 提供资料：乙方须根据办理进度，及时、真实、准确地提供甲方要求的各类
身份证明、证件及文件资料（包括其指定的香港公司股东、董事资料及指定车辆
文件），并予以配合。
3. 承担官费：乙方须承担本合约第三条所列明的一切政府官方收费及第三方费
用。
第六条免责声明及风险提示
1. 甲方提供的服务为程序性代办及协助，不对中国内地或香港政府部门（如广
东省公安厅、香港运输署等）的审批结果、时长作出任何保证。
第七条违约责任
1. 若乙方支付定金后单方解除合约，已付定金不予退还。
2. 若因乙方未能按时支付各期款项、提供资料或配合办理，导致服务延误或产
生额外成本，全部责任及费用由乙方承担，且甲方有权暂停服务。
3. 若因甲方过错导致公司过户或车牌换挂程序失败，甲方应退还已收取的服务
费。
第八条其他
1. 法律适用与争议解决：本合约受香港特别行政区法律管辖。任何争议，双方
应友好协商解决；协商不成的，任何一方可向甲方所在地之香港法院提起诉讼。
甲方（盖章）：华星资源开发有限公司
授权代表签署：
日期：
2026
年
5
月
28 日
乙方（签署）：
日期：
2026
年
5
月
28 日');
INSERT INTO "public"."contracts" VALUES ('HT2026060316290356B3', '车辆买卖合约（香港）', 24, 1, 'HKD', 108000.00, 0.00, 108000.00, NULL, 0.00, NULL, '2026/06/HT2026060316290356B3.pdf', '0aad48875e112474684fc6d0c0569be12002c709900f4fc80aa0b01ad0c50dec', '{"source": "agent", "file_id": "47efb5c2-8df1-412c-969c-007a192cb04f", "data_source": "pre_extracted", "full_text": "\u660e\u54e5\u4e2d\u6e2f\u724c\n\u672c\u5408\u540c\u4e00\u5f0f\u5169\u4efd\uff0c\u7532\u3001\u4e59\u96d9\u65b9\u5404\u57f7\u4e00\u4efd\uff0c\u540c\u6642\u5177\u6709\u6cd5\u5f8b\u6548\u61c9\u3002\n\u8f66\u8f86\u4e70\u5356\u5408\u7ea6\uff08\u9999\u6e2f\uff09\n\u7532\u65b9\uff08\u5356\u65b9\uff09\uff1a\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\n\u8054\u7cfb\u4eba\uff1a\u9648\u7115\u660e\n\u8054\u7cfb\u7535\u8bdd\uff1a98702065\n\u4e59\u65b9\uff08\u59d4\u6258\u65b9\uff09\uff1a\n\u9648\u4eae\u575b\n\u8bc1\u4ef6\u7c7b\u578b\u53ca\u53f7\u7801\uff1a\nM860682(5)\n\u8054\u7cfb\u7535\u8bdd\uff1a\n93499456\n\u7ecf\u53cc\u65b9\u534f\u5546\uff0c\u73b0\u5c31\u4e70\u5356\u4e0b\u8ff0\u8f66\u8f86\u8ba2\u7acb\u672c\u5408\u7ea6\uff0c\u4ee5\u8d44\u5171\u540c\u9075\u5b88\u3002\n\u7b2c\u4e00\u6761\u8f66\u8f86\u8be6\u60c5\n1. \u8f66\u8eab\u5e95\u76d8\u53f7\u7801/\u8f66\u8f86\u8bc6\u522b\u53f7\u7801\uff1a\nWAUZZZ4M8GD017658\n\u7b2c\u4e8c\u6761\u8f66\u8f86\u552e\u4ef7\u4e0e\u652f\u4ed8\n1. \u8be5\u8f66\u8f86\u4e4b\u603b\u552e\u4ef7\u4e3a\u6e2f\u5e01\n\u58f9\u62fe\u4e07\u96f6\u634c\u4edf\n\u5143\u6574\uff08$ 108000 \uff09\u3002\n2. \u7b2c\u4e00\u671f\uff1a\u4e59\u65b9\u5df2\u4e8e2026 \u5e74\n5\n\u6708\n24\n\u65e5\u652f\u4ed8\u5b9a\u91d1\u6e2f\u5e01\n\u8d30\u4e07\n\u5143\u6574\n\uff08$ 20000\n\uff09\u3002\n3. \u5269\u4f59\u8f66\u8f86\u5c3e\u6b3e\u6e2f\u5e01\uff1a\n\u634c\u4e07\u634c\u4edf\n\u5143\u6574\uff08$ 88000\n\uff09\uff0c\u987b\u4e8e\u8be5\u8f66\u8f86\n\u5b8c\u6210\u9999\u6e2f\u8fd0\u8f93\u7f72\u8fc7\u6237\u767b\u8bb0\u624b\u7eed\u5f53\u65e5\uff0c\u7531\u4e59\u65b9\u4e00\u6b21\u6027\u652f\u4ed8\u7532\u65b9\u3002\n\u7b2c\u4e09\u6761\u8f66\u8f86\u73b0\u72b6\u4e0e\u63a5\u6536\n\u4e59\u65b9\u7279\u6b64\u786e\u8ba4\uff0c\u5176\u5df2\u5bf9\u8be5\u8f66\u8f86\u4e4b\u54c1\u724c\u3001\u578b\u53f7\u3001\u5e74\u4efd\u3001\u91cc\u7a0b\u3001\u6027\u80fd\u3001\u5916\u89c2\u3001\u5185\u9970\u3001\n\u673a\u4ef6\u53ca\u4e00\u5207\u73b0\u5b58\u72b6\u51b5\u8fdb\u884c\u4e86\u5145\u5206\u67e5\u9a8c\uff0c\u5e76\u5b8c\u5168\u4e86\u89e3\u4e0e\u63a5\u53d7\u3002\u4e59\u65b9\u540c\u610f\u4ee5\u8be5\u8f66\u8f86\u4e4b\n\u201c\u73b0\u72b6\u201d\u8d2d\u5165\uff0c\u7532\u65b9\u9664\u4fdd\u8bc1\u62e5\u6709\u5408\u6cd5\u6240\u6709\u6743\u5916\uff0c\u4e0d\u5c31\u8f66\u8f86\u4e4b\u8d28\u91cf\u3001\u6027\u80fd\u3001\u7455\u75b5\u6216\n\u9002\u7528\u6027\u4f5c\u51fa\u4efb\u4f55\u5176\u4ed6\u660e\u793a\u6216\u9ed8\u793a\u4e4b\u4fdd\u8bc1\u3002\n\u7b2c\u56db\u6761\u8f66\u8f86\u4ea4\u4ed8\u4e0e\u8d23\u4efb\n1. \u63d0\u8f66\u671f\u9650\uff1a\u4e59\u65b9\u5728\u4ed8\u6e05\u7b2c\u4e8c\u6761\u7ea6\u5b9a\u7684\u5168\u90e8\u5c3e\u6b3e\u540e\uff0c\u987b\u4e8e\u4e09\uff083\uff09\u4e2a\u5de5\u4f5c\u65e5\u5185\uff0c\n\u4eb2\u8d74\u7532\u65b9\u6307\u5b9a\u5730\u70b9\u63d0\u53d6\u8be5\u8f66\u8f86\u3002\n2. \u903e\u671f\u505c\u8f66\u8d39\uff1a\u82e5\u4e59\u65b9\u672a\u80fd\u5728\u4e0a\u8ff0\u7ea6\u5b9a\u671f\u9650\u5185\u63d0\u8d70\u8f66\u8f86\uff0c\u6bcf\u903e\u671f\u4e00\u65e5\uff0c\u987b\u5411\u7532\n\u65b9\u652f\u4ed8\u505c\u8f66\u8d39\u6e2f\u5e01\u58f9\u4f70\u5143\u6574\uff08HK$100\uff09\u3002\u7532\u65b9\u6709\u6743\u5c06\u8f66\u8f86\u79fb\u81f3\u5176\u4ed6\u5730\u70b9\u505c\u653e\uff0c\n\u76f8\u5173\u98ce\u9669\u4e0e\u8d39\u7528\u7531\u4e59\u65b9\u627f\u62c5\u3002\n3. \u98ce\u9669\u8f6c\u79fb\uff1a\u81ea\u8be5\u8f66\u8f86\u4e8e\u8fd0\u8f93\u7f72\u5b8c\u6210\u8fc7\u6237\u767b\u8bb0\u4e4b\u65e5\u8d77\uff0c\u65e0\u8bba\u4e59\u65b9\u662f\u5426\u5df2\u63d0\u8f66\uff0c\n\u8be5\u8f66\u8f86\u4e4b\u4e00\u5207\u98ce\u9669\uff08\u5982\u635f\u6bc1\u3001\u5931\u7a83\uff09\u53ca\u4e00\u5207\u76f8\u5173\u8d39\u7528\u4e0e\u6cd5\u5f8b\u8d23\u4efb\uff08\u5982\u7f5a\u6b3e\u3001\u4e8b\u6545\uff09\n\u5747\u8f6c\u79fb\u7531\u4e59\u65b9\u627f\u62c5\u3002\n\u7b2c\u4e94\u6761\u6587\u4ef6\u4e0e\u8fc7\u6237\n1. \u7532\u65b9\u4fdd\u8bc1\u62e5\u6709\u8be5\u8f66\u8f86\u4e4b\u5408\u6cd5\u6240\u6709\u6743\uff0c\u5e76\u627f\u8bfa\u8be5\u8f66\u8f86\u4e0d\u9644\u5e26\u4efb\u4f55\u62b5\u62bc\u6216\u6cd5\u5f8b\u7ea0\n\u7eb7\u3002\n2. \u7532\u65b9\u5e94\u914d\u5408\u63d0\u4f9b\u529e\u7406\u8fc7\u6237\u6240\u9700\u4e4b\u8f66\u8f86\u767b\u8bb0\u6587\u4ef6\uff08\u724c\u7c3f\uff09\u7b49\u3002\n\n\u660e\u54e5\u4e2d\u6e2f\u724c\n\u672c\u5408\u540c\u4e00\u5f0f\u5169\u4efd\uff0c\u7532\u3001\u4e59\u96d9\u65b9\u5404\u57f7\u4e00\u4efd\uff0c\u540c\u6642\u5177\u6709\u6cd5\u5f8b\u6548\u61c9\u3002\n\u7b2c\u516d\u6761\u4fdd\u9669\n\u4e59\u65b9\u987b\u81ea\u884c\u8d2d\u4e70\u6709\u6548\u7684\u6c7d\u8f66\u4fdd\u9669\u3002\n\u7b2c\u4e03\u6761\u8fdd\u7ea6\u8d23\u4efb\n\u82e5\u4e59\u65b9\u672a\u6309\u672c\u5408\u540c\u7ea6\u5b9a\u652f\u4ed8\u5c3e\u6b3e\u6216\u63d0\u53d6\u8f66\u8f86\uff0c\u7532\u65b9\u6709\u6743\u6ca1\u6536\u5b9a\u91d1\uff0c\u5e76\u53ef\u5c06\u8f66\u8f86\u53e6\n\u884c\u51fa\u552e\u3002\n\u7b2c\u516b\u6761\u5176\u4ed6\n1. \u672c\u5408\u7ea6\u53d7\u9999\u6e2f\u7279\u522b\u884c\u653f\u533a\u6cd5\u5f8b\u7ba1\u8f96\u3002\n2. \u4efb\u4f55\u4e89\u8bae\uff0c\u5e94\u63d0\u4ea4\u9999\u6e2f\u6cd5\u9662\u8bc9\u8bbc\u89e3\u51b3\u3002\n3. \u672c\u5408\u7ea6\u4e00\u5f0f\u4e24\u4efd\uff0c\u53cc\u65b9\u5404\u6267\u4e00\u4efd\uff0c\u81ea\u7b7e\u7f72\u4e4b\u65e5\u8d77\u751f\u6548\u3002\n\u7532\u65b9\u7b7e\u7f72\uff1a\n\u516c\u53f8\u540d\u79f0\uff1a\n\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\n\u6388\u6743\u4ee3\u8868\u7b7e\u7f72\uff1a\n\u59d3\u540d\uff1a\n\u65e5\u671f\uff1a\n2026\n\u5e74\n5\n\u6708\n24\n\u65e5\n\u4e59\u65b9\u7b7e\u7f72\uff1a\n\u59d3\u540d/\u516c\u53f8\u540d\u79f0\uff1a\n\u65e5\u671f\uff1a\n2026\n\u5e74\n5\n\u6708\n24\n\u65e5"}', NULL, 'f', 'active', '2026-05-24', NULL, NULL, NULL, 1, 29, '2026-06-03 08:29:03.385325+00', '2026-06-03 08:29:03.408046+00', 'f', NULL, '车辆业务', '买卖奥迪车辆（底盘号WAUZZZ4M8GD017658），总售价108,000 HKD，已付定金20,000 HKD，尾款88,000 HKD须于完成香港运输署过户登记手续当日支付', NULL, 0.00, 0.00, '明哥中港牌
本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。
车辆买卖合约（香港）
甲方（卖方）：华星资源开发有限公司
联系人：陈焕明
联系电话：98702065
乙方（委托方）：
陈亮坛
证件类型及号码：
M860682(5)
联系电话：
93499456
经双方协商，现就买卖下述车辆订立本合约，以资共同遵守。
第一条车辆详情
1. 车身底盘号码/车辆识别号码：
WAUZZZ4M8GD017658
第二条车辆售价与支付
1. 该车辆之总售价为港币
壹拾万零捌仟
元整（$ 108000 ）。
2. 第一期：乙方已于2026 年
5
月
24
日支付定金港币
贰万
元整
（$ 20000
）。
3. 剩余车辆尾款港币：
捌万捌仟
元整（$ 88000
），须于该车辆
完成香港运输署过户登记手续当日，由乙方一次性支付甲方。
第三条车辆现状与接收
乙方特此确认，其已对该车辆之品牌、型号、年份、里程、性能、外观、内饰、
机件及一切现存状况进行了充分查验，并完全了解与接受。乙方同意以该车辆之
“现状”购入，甲方除保证拥有合法所有权外，不就车辆之质量、性能、瑕疵或
适用性作出任何其他明示或默示之保证。
第四条车辆交付与责任
1. 提车期限：乙方在付清第二条约定的全部尾款后，须于三（3）个工作日内，
亲赴甲方指定地点提取该车辆。
2. 逾期停车费：若乙方未能在上述约定期限内提走车辆，每逾期一日，须向甲
方支付停车费港币壹佰元整（HK$100）。甲方有权将车辆移至其他地点停放，
相关风险与费用由乙方承担。
3. 风险转移：自该车辆于运输署完成过户登记之日起，无论乙方是否已提车，
该车辆之一切风险（如损毁、失窃）及一切相关费用与法律责任（如罚款、事故）
均转移由乙方承担。
第五条文件与过户
1. 甲方保证拥有该车辆之合法所有权，并承诺该车辆不附带任何抵押或法律纠
纷。
2. 甲方应配合提供办理过户所需之车辆登记文件（牌簿）等。

明哥中港牌
本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。
第六条保险
乙方须自行购买有效的汽车保险。
第七条违约责任
若乙方未按本合同约定支付尾款或提取车辆，甲方有权没收定金，并可将车辆另
行出售。
第八条其他
1. 本合约受香港特别行政区法律管辖。
2. 任何争议，应提交香港法院诉讼解决。
3. 本合约一式两份，双方各执一份，自签署之日起生效。
甲方签署：
公司名称：
华星资源开发有限公司
授权代表签署：
姓名：
日期：
2026
年
5
月
24
日
乙方签署：
姓名/公司名称：
日期：
2026
年
5
月
24
日');
INSERT INTO "public"."contracts" VALUES ('HT202606021425267CF5', '车辆买卖合约（香港）', 22, 1, 'HKD', 250000.00, 50000.00, 200000.00, NULL, 0.00, NULL, '2026/06/HT202606021425267CF5.pdf', 'ade5c8fd8e2e669ecb78ed50df84890ca7aeeb04f6d43152a808585f86872a21', '{"source": "agent", "file_id": "36fa3ebc-7dc5-4196-a6f6-a868b23d1e94", "data_source": "cache", "contract_number": null, "title": "\u8f66\u8f86\u4e70\u5356\u5408\u7ea6\uff08\u9999\u6e2f\uff09", "signed_date": "2026-05-28", "business_type": "\u8f66\u8f86\u4e1a\u52a1", "business_description": "\u4e70\u5356\u8f66\u8f86\uff08\u8f66\u8eab\u5e95\u76d8\u53f7\u7801/\u8f66\u8f86\u8bc6\u522b\u53f7\u7801\uff1aGGH30-0016495\uff09", "party_a": {"name": "\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8", "contact": "98702065", "address": null}, "party_b": {"name": "\u80e1\u5c11\u68df", "id_type": "\u8bc1\u4ef6\u7c7b\u578b\u53ca\u53f7\u7801", "id_number": "F420825(7)", "phone": "97857999"}, "vehicle_info": {"plate_number": null, "vehicle_model": null, "registration_number": null}, "port": null, "service_items": [], "payment_terms": [{"name": "\u7b2c\u4e00\u671f\uff08\u5b9a\u91d1\uff09", "amount": 50000, "due_date": "2026-05-28", "condition": "\u4e59\u65b9\u5df2\u4e8e2026\u5e745\u670828\u65e5\u652f\u4ed8", "is_paid": true}, {"name": "\u5269\u4f59\u8f66\u8f86\u5c3e\u6b3e", "amount": 200000, "due_date": null, "condition": "\u987b\u4e8e\u8be5\u8f66\u8f86\u5b8c\u6210\u9999\u6e2f\u8fd0\u8f93\u7f72\u8fc7\u6237\u767b\u8bb0\u624b\u7eed\u5f53\u65e5\uff0c\u7531\u4e59\u65b9\u4e00\u6b21\u6027\u652f\u4ed8\u7532\u65b9", "is_paid": false}], "total_amount": 250000, "currency": "HKD", "validity_period": {"start_date": "2026-05-28", "end_date": null}, "special_terms": ["\u4e59\u65b9\u7279\u6b64\u786e\u8ba4\uff0c\u5176\u5df2\u5bf9\u8be5\u8f66\u8f86\u4e4b\u54c1\u724c\u3001\u578b\u53f7\u3001\u5e74\u4efd\u3001\u91cc\u7a0b\u3001\u6027\u80fd\u3001\u5916\u89c2\u3001\u5185\u9970\u3001\u673a\u4ef6\u53ca\u4e00\u5207\u73b0\u5b58\u72b6\u51b5\u8fdb\u884c\u4e86\u5145\u5206\u67e5\u9a8c\uff0c\u5e76\u5b8c\u5168\u4e86\u89e3\u4e0e\u63a5\u53d7\u3002\u4e59\u65b9\u540c\u610f\u4ee5\u8be5\u8f66\u8f86\u4e4b\u201c\u73b0\u72b6\u201d\u8d2d\u5165\uff0c\u7532\u65b9\u9664\u4fdd\u8bc1\u62e5\u6709\u5408\u6cd5\u6240\u6709\u6743\u5916\uff0c\u4e0d\u5c31\u8f66\u8f86\u4e4b\u8d28\u91cf\u3001\u6027\u80fd\u3001\u7455\u75b5\u6216\u9002\u7528\u6027\u4f5c\u51fa\u4efb\u4f55\u5176\u4ed6\u660e\u793a\u6216\u9ed8\u793a\u4e4b\u4fdd\u8bc1\u3002", "\u82e5\u4e59\u65b9\u672a\u6309\u672c\u5408\u540c\u7ea6\u5b9a\u652f\u4ed8\u5c3e\u6b3e\u6216\u63d0\u53d6\u8f66\u8f86\uff0c\u7532\u65b9\u6709\u6743\u6ca1\u6536\u5b9a\u91d1\uff0c\u5e76\u53ef\u5c06\u8f66\u8f86\u53e6\u884c\u51fa\u552e\u3002", "\u672c\u5408\u7ea6\u53d7\u9999\u6e2f\u7279\u522b\u884c\u653f\u533a\u6cd5\u5f8b\u7ba1\u8f96\u3002\u4efb\u4f55\u4e89\u8bae\uff0c\u5e94\u63d0\u4ea4\u9999\u6e2f\u6cd5\u9662\u8bc9\u8bbc\u89e3\u51b3\u3002"], "confidence": 0.95, "full_text": "\u660e\u54e5\u4e2d\u6e2f\u724c\n\u672c\u5408\u540c\u4e00\u5f0f\u5169\u4efd\uff0c\u7532\u3001\u4e59\u96d9\u65b9\u5404\u57f7\u4e00\u4efd\uff0c\u540c\u6642\u5177\u6709\u6cd5\u5f8b\u6548\u61c9\u3002\n\u8f66\u8f86\u4e70\u5356\u5408\u7ea6\uff08\u9999\u6e2f\uff09\n\u7532\u65b9\uff08\u5356\u65b9\uff09\uff1a\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\n\u8054\u7cfb\u4eba\uff1a\u9648\u7115\u660e\n\u8054\u7cfb\u7535\u8bdd\uff1a98702065\n\u4e59\u65b9\uff08\u59d4\u6258\u65b9\uff09\uff1a\n\u80e1\u5c11\u68df\n\u8bc1\u4ef6\u7c7b\u578b\u53ca\u53f7\u7801\uff1a\nF420825(7)\n\u8054\u7cfb\u7535\u8bdd\uff1a\n97857999\n\u7ecf\u53cc\u65b9\u534f\u5546\uff0c\u73b0\u5c31\u4e70\u5356\u4e0b\u8ff0\u8f66\u8f86\u8ba2\u7acb\u672c\u5408\u7ea6\uff0c\u4ee5\u8d44\u5171\u540c\u9075\u5b88\u3002\n\u7b2c\u4e00\u6761\u8f66\u8f86\u8be6\u60c5\n1. \u8f66\u8eab\u5e95\u76d8\u53f7\u7801/\u8f66\u8f86\u8bc6\u522b\u53f7\u7801\uff1a\nGGH30-0016495\n\u7b2c\u4e8c\u6761\u8f66\u8f86\u552e\u4ef7\u4e0e\u652f\u4ed8\n1. \u8be5\u8f66\u8f86\u4e4b\u603b\u552e\u4ef7\u4e3a\u6e2f\u5e01\n\u8d30\u62fe\u4f0d\u4e07\n\u5143\u6574\uff08$ 250000 \uff09\u3002\n2. \u7b2c\u4e00\u671f\uff1a\u4e59\u65b9\u5df2\u4e8e2026 \u5e74\n5\n\u6708\n28\n\u65e5\u652f\u4ed8\u5b9a\u91d1\u6e2f\u5e01\n\u4f0d\u4e07\n\u5143\u6574\n\uff08$50000\n\uff09\u3002\n3. \u5269\u4f59\u8f66\u8f86\u5c3e\u6b3e\u6e2f\u5e01\uff1a\n\u8d30\u62fe\u4e07\n\u5143\u6574\uff08$ 200000\n\uff09\uff0c\u987b\u4e8e\u8be5\u8f66\u8f86\u5b8c\n\u6210\u9999\u6e2f\u8fd0\u8f93\u7f72\u8fc7\u6237\u767b\u8bb0\u624b\u7eed\u5f53\u65e5\uff0c\u7531\u4e59\u65b9\u4e00\u6b21\u6027\u652f\u4ed8\u7532\u65b9\u3002\n\u7b2c\u4e09\u6761\u8f66\u8f86\u73b0\u72b6\u4e0e\u63a5\u6536\n\u4e59\u65b9\u7279\u6b64\u786e\u8ba4\uff0c\u5176\u5df2\u5bf9\u8be5\u8f66\u8f86\u4e4b\u54c1\u724c\u3001\u578b\u53f7\u3001\u5e74\u4efd\u3001\u91cc\u7a0b\u3001\u6027\u80fd\u3001\u5916\u89c2\u3001\u5185\u9970\u3001\n\u673a\u4ef6\u53ca\u4e00\u5207\u73b0\u5b58\u72b6\u51b5\u8fdb\u884c\u4e86\u5145\u5206\u67e5\u9a8c\uff0c\u5e76\u5b8c\u5168\u4e86\u89e3\u4e0e\u63a5\u53d7\u3002\u4e59\u65b9\u540c\u610f\u4ee5\u8be5\u8f66\u8f86\u4e4b\n\u201c\u73b0\u72b6\u201d\u8d2d\u5165\uff0c\u7532\u65b9\u9664\u4fdd\u8bc1\u62e5\u6709\u5408\u6cd5\u6240\u6709\u6743\u5916\uff0c\u4e0d\u5c31\u8f66\u8f86\u4e4b\u8d28\u91cf\u3001\u6027\u80fd\u3001\u7455\u75b5\u6216\n\u9002\u7528\u6027\u4f5c\u51fa\u4efb\u4f55\u5176\u4ed6\u660e\u793a\u6216\u9ed8\u793a\u4e4b\u4fdd\u8bc1\u3002\n\u7b2c\u56db\u6761\u8f66\u8f86\u4ea4\u4ed8\u4e0e\u8d23\u4efb\n1. \u63d0\u8f66\u671f\u9650\uff1a\u4e59\u65b9\u5728\u4ed8\u6e05\u7b2c\u4e8c\u6761\u7ea6\u5b9a\u7684\u5168\u90e8\u5c3e\u6b3e\u540e\uff0c\u987b\u4e8e\u4e09\uff083\uff09\u4e2a\u5de5\u4f5c\u65e5\u5185\uff0c\n\u4eb2\u8d74\u7532\u65b9\u6307\u5b9a\u5730\u70b9\u63d0\u53d6\u8be5\u8f66\u8f86\u3002\n2. \u903e\u671f\u505c\u8f66\u8d39\uff1a\u82e5\u4e59\u65b9\u672a\u80fd\u5728\u4e0a\u8ff0\u7ea6\u5b9a\u671f\u9650\u5185\u63d0\u8d70\u8f66\u8f86\uff0c\u6bcf\u903e\u671f\u4e00\u65e5\uff0c\u987b\u5411\u7532\n\u65b9\u652f\u4ed8\u505c\u8f66\u8d39\u6e2f\u5e01\u58f9\u4f70\u5143\u6574\uff08HK$100\uff09\u3002\u7532\u65b9\u6709\u6743\u5c06\u8f66\u8f86\u79fb\u81f3\u5176\u4ed6\u5730\u70b9\u505c\u653e\uff0c\n\u76f8\u5173\u98ce\u9669\u4e0e\u8d39\u7528\u7531\u4e59\u65b9\u627f\u62c5\u3002\n3. \u98ce\u9669\u8f6c\u79fb\uff1a\u81ea\u8be5\u8f66\u8f86\u4e8e\u8fd0\u8f93\u7f72\u5b8c\u6210\u8fc7\u6237\u767b\u8bb0\u4e4b\u65e5\u8d77\uff0c\u65e0\u8bba\u4e59\u65b9\u662f\u5426\u5df2\u63d0\u8f66\uff0c\n\u8be5\u8f66\u8f86\u4e4b\u4e00\u5207\u98ce\u9669\uff08\u5982\u635f\u6bc1\u3001\u5931\u7a83\uff09\u53ca\u4e00\u5207\u76f8\u5173\u8d39\u7528\u4e0e\u6cd5\u5f8b\u8d23\u4efb\uff08\u5982\u7f5a\u6b3e\u3001\u4e8b\u6545\uff09\n\u5747\u8f6c\u79fb\u7531\u4e59\u65b9\u627f\u62c5\u3002\n\u7b2c\u4e94\u6761\u6587\u4ef6\u4e0e\u8fc7\u6237\n1. \u7532\u65b9\u4fdd\u8bc1\u62e5\u6709\u8be5\u8f66\u8f86\u4e4b\u5408\u6cd5\u6240\u6709\u6743\uff0c\u5e76\u627f\u8bfa\u8be5\u8f66\u8f86\u4e0d\u9644\u5e26\u4efb\u4f55\u62b5\u62bc\u6216\u6cd5\u5f8b\u7ea0\n\u7eb7\u3002\n2. \u7532\u65b9\u5e94\u914d\u5408\u63d0\u4f9b\u529e\u7406\u8fc7\u6237\u6240\u9700\u4e4b\u8f66\u8f86\u767b\u8bb0\u6587\u4ef6\uff08\u724c\u7c3f\uff09\u7b49\u3002\n\n\u660e\u54e5\u4e2d\u6e2f\u724c\n\u672c\u5408\u540c\u4e00\u5f0f\u5169\u4efd\uff0c\u7532\u3001\u4e59\u96d9\u65b9\u5404\u57f7\u4e00\u4efd\uff0c\u540c\u6642\u5177\u6709\u6cd5\u5f8b\u6548\u61c9\u3002\n\u7b2c\u516d\u6761\u4fdd\u9669\n\u4e59\u65b9\u987b\u81ea\u884c\u8d2d\u4e70\u6709\u6548\u7684\u6c7d\u8f66\u4fdd\u9669\u53ca\u724c\u8d39\u3002\n\u7b2c\u4e03\u6761\u8fdd\u7ea6\u8d23\u4efb\n\u82e5\u4e59\u65b9\u672a\u6309\u672c\u5408\u540c\u7ea6\u5b9a\u652f\u4ed8\u5c3e\u6b3e\u6216\u63d0\u53d6\u8f66\u8f86\uff0c\u7532\u65b9\u6709\u6743\u6ca1\u6536\u5b9a\u91d1\uff0c\u5e76\u53ef\u5c06\u8f66\u8f86\u53e6\n\u884c\u51fa\u552e\u3002\n\u7b2c\u516b\u6761\u5176\u4ed6\n1. \u672c\u5408\u7ea6\u53d7\u9999\u6e2f\u7279\u522b\u884c\u653f\u533a\u6cd5\u5f8b\u7ba1\u8f96\u3002\n2. \u4efb\u4f55\u4e89\u8bae\uff0c\u5e94\u63d0\u4ea4\u9999\u6e2f\u6cd5\u9662\u8bc9\u8bbc\u89e3\u51b3\u3002\n3. \u672c\u5408\u7ea6\u4e00\u5f0f\u4e24\u4efd\uff0c\u53cc\u65b9\u5404\u6267\u4e00\u4efd\uff0c\u81ea\u7b7e\u7f72\u4e4b\u65e5\u8d77\u751f\u6548\u3002\n\u7532\u65b9\u7b7e\u7f72\uff1a\n\u516c\u53f8\u540d\u79f0\uff1a\n\u534e\u661f\u8d44\u6e90\u5f00\u53d1\u6709\u9650\u516c\u53f8\n\u65e5\u671f\uff1a\n2026\n\u5e74\n5\n\u6708\n28\n\u65e5\n\u4e59\u65b9\u7b7e\u7f72\uff1a\n\u65e5\u671f\uff1a\n2026\n\u5e74\n5\n\u6708\n28\n\u65e5"}', 0.9500, 'f', 'active', '2026-05-28', '2026-05-28', NULL, NULL, 1, 27, '2026-06-02 06:25:26.06216+00', '2026-06-02 07:25:15.656212+00', 'f', NULL, '车辆业务', '买卖车辆（车身底盘号码/车辆识别号码：GGH30-0016495）', '5月28日17年白外黑内30系埃尔法(10)', 0.00, 0.00, '明哥中港牌
本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。
车辆买卖合约（香港）
甲方（卖方）：华星资源开发有限公司
联系人：陈焕明
联系电话：98702065
乙方（委托方）：
胡少棟
证件类型及号码：
F420825(7)
联系电话：
97857999
经双方协商，现就买卖下述车辆订立本合约，以资共同遵守。
第一条车辆详情
1. 车身底盘号码/车辆识别号码：
GGH30-0016495
第二条车辆售价与支付
1. 该车辆之总售价为港币
贰拾伍万
元整（$ 250000 ）。
2. 第一期：乙方已于2026 年
5
月
28
日支付定金港币
伍万
元整
（$50000
）。
3. 剩余车辆尾款港币：
贰拾万
元整（$ 200000
），须于该车辆完
成香港运输署过户登记手续当日，由乙方一次性支付甲方。
第三条车辆现状与接收
乙方特此确认，其已对该车辆之品牌、型号、年份、里程、性能、外观、内饰、
机件及一切现存状况进行了充分查验，并完全了解与接受。乙方同意以该车辆之
“现状”购入，甲方除保证拥有合法所有权外，不就车辆之质量、性能、瑕疵或
适用性作出任何其他明示或默示之保证。
第四条车辆交付与责任
1. 提车期限：乙方在付清第二条约定的全部尾款后，须于三（3）个工作日内，
亲赴甲方指定地点提取该车辆。
2. 逾期停车费：若乙方未能在上述约定期限内提走车辆，每逾期一日，须向甲
方支付停车费港币壹佰元整（HK$100）。甲方有权将车辆移至其他地点停放，
相关风险与费用由乙方承担。
3. 风险转移：自该车辆于运输署完成过户登记之日起，无论乙方是否已提车，
该车辆之一切风险（如损毁、失窃）及一切相关费用与法律责任（如罚款、事故）
均转移由乙方承担。
第五条文件与过户
1. 甲方保证拥有该车辆之合法所有权，并承诺该车辆不附带任何抵押或法律纠
纷。
2. 甲方应配合提供办理过户所需之车辆登记文件（牌簿）等。

明哥中港牌
本合同一式兩份，甲、乙雙方各執一份，同時具有法律效應。
第六条保险
乙方须自行购买有效的汽车保险及牌费。
第七条违约责任
若乙方未按本合同约定支付尾款或提取车辆，甲方有权没收定金，并可将车辆另
行出售。
第八条其他
1. 本合约受香港特别行政区法律管辖。
2. 任何争议，应提交香港法院诉讼解决。
3. 本合约一式两份，双方各执一份，自签署之日起生效。
甲方签署：
公司名称：
华星资源开发有限公司
日期：
2026
年
5
月
28
日
乙方签署：
日期：
2026
年
5
月
28
日');

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
INSERT INTO "public"."customers" VALUES ('胡少棟', NULL, '97857999', NULL, 'RjQyMDgyNSg3KQ==', NULL, NULL, NULL, NULL, 1, 22, '2026-06-02 06:25:24.852436+00', '2026-06-02 06:25:24.852436+00', 'f', NULL);
INSERT INTO "public"."customers" VALUES ('陈亮坛', NULL, '93499456', NULL, 'TTg2MDY4Mig1KQ==', NULL, NULL, NULL, NULL, 1, 24, '2026-06-03 08:28:59.541314+00', '2026-06-03 08:28:59.541314+00', 'f', NULL);

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
INSERT INTO "public"."payments" VALUES (27, 1, '第一期（定金）', 'HKD', 50000.00, 50000.00, NULL, NULL, NULL, NULL, '2026-05-28', '2026/06/3e2f1aa0-f55e-45b5-9541-9670b1752875.jpg', NULL, NULL, 'cash', 'paid', 'manual', '已提供现金收据凭证，付款人胡少棟，收款人陈焕明，收据编号00000213，备注：30系埃尔法 GGH30-0016495', 1, 19, '2026-06-02 06:25:26.091251+00', '2026-06-02 06:27:00.484801+00', 'f', NULL, 'income', NULL, 'null', 'HT202606021425267CF5 胡少棟 买卖车辆（车身底盘号码/车辆识别号码：GGH30-0016495） 第1期收款');
INSERT INTO "public"."payments" VALUES (28, 1, '定金', 'CNY', 50000.00, 50000.00, NULL, NULL, NULL, NULL, '2026-05-28', '2026/06/cee6426c-5997-41d7-b635-64043c1675eb.jpg', NULL, NULL, 'cash', 'paid', 'manual', '已提供现金收据，付款人胡少棟，收据编号00000215', 1, 20, '2026-06-02 06:28:29.372397+00', '2026-06-02 06:28:29.372397+00', 'f', NULL, 'income', NULL, '{"notes": "深圳湾现牌24万人民币", "amount": 50000, "currency": "CNY", "payee_name": "陈焕明", "payer_name": "胡少栋先生", "document_type": "cash_receipt", "transaction_id": "00000215", "transaction_date": "2026-05-28"}', 'HT202606021427370BC3 胡少棟 购买现牌 粤Z7N80港 深圳湾口岸 第1期收款');

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
SELECT setval('"public"."audit_logs_id_seq"', 68, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."chat_history_id_seq"
OWNED BY "public"."chat_history"."id";
SELECT setval('"public"."chat_history_id_seq"', 811, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."contracts_id_seq"
OWNED BY "public"."contracts"."id";
SELECT setval('"public"."contracts_id_seq"', 29, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."customers_id_seq"
OWNED BY "public"."customers"."id";
SELECT setval('"public"."customers_id_seq"', 24, true);

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
SELECT setval('"public"."payments_id_seq"', 20, true);

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
