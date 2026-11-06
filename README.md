# RagKb · 个人知识库问答

上传文档 → 自动解析切块 → 向量化入库 → 语义检索 → 带引用来源的问答。

适合当作个人资料库：把 PDF / Word / 文本 / 图片丢进去，用自然语言提问，答案会标出出自哪个文件、第几页。

## 功能

- **多格式入库**：PDF、Word（.docx）、txt、Markdown、图片（png / jpg）
- **扫描件自动 OCR**：PDF 里没有文字层的页会用本地 RapidOCR 识别，不用联网、不要 API Key
- **语义检索**：本地 bge 模型 + FAISS，问法和原文不一样也能找到
- **带引用回答**：答案里的 `[1][2]` 对应具体文件、页码、原文片段
- **会话历史**：多轮追问、历史回放、刷新页面不丢
- **模型可切换**：任意 OpenAI 兼容接口（本机 Ollama / DeepSeek / 通义 / Kimi）

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + SQLAlchemy(async) |
| 数据库 | MySQL 8 |
| 向量索引 | FAISS（IndexIDMap2 + 内积，向量已归一化） |
| Embedding | `BAAI/bge-small-zh-v1.5`（本地 512 维） |
| OCR | RapidOCR（ONNX，本地 CPU） |
| 大模型 | 任意 OpenAI 兼容接口，默认本机 Ollama |
| 前端 | Vue 3 + Vite + Pinia + Vue Router + axios |

## 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | **3.11 或 3.12** | ⚠️ 不能用 3.13+：RapidOCR 不支持 |
| MySQL | 8.x | 库名默认 `ragkb` |
| Node.js | 18+ | 前端构建 |
| Ollama | 任意较新版本 | 本地跑大模型（或改用云 API） |

## 目录结构

```text
RagKb/
├── backend/
│   ├── app/
│   │   ├── main.py            # 装配：CORS + 路由
│   │   ├── config.py          # 所有可调参数
│   │   ├── db.py              # 异步引擎与会话依赖
│   │   ├── models.py          # 5 张表的 ORM
│   │   ├── vectorstore.py     # FAISS 封装
│   │   ├── retrieval.py       # 问题 → 片段（编码 + 检索 + 回表）
│   │   ├── generator.py       # 拼 prompt + 调大模型
│   │   ├── schemas/           # 接口的请求 / 响应模型
│   │   ├── api/               # health / docs / stats / search / chat
│   │   └── ingest/            # loader → splitter → embedder → pipeline
│   ├── sql/schema.sql         # 建表脚本
│   ├── data/                  # 上传文件与 FAISS 索引（不进版本库）
│   └── models/                # bge 模型目录（不进版本库）
├── frontend/
│   └── src/                   # 对话页、文档库页、stores、api
└── docs/                      # 本地计划与笔记（不进版本库）
```

## 快速开始

### 1. 数据库

```sql
CREATE DATABASE ragkb DEFAULT CHARSET utf8mb4;
```

```bash
mysql -u root -p ragkb < backend/sql/schema.sql
```

⚠️ `schema.sql` 开头会 `DROP TABLE`，重跑会清空所有文档和会话。

### 2. 后端

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

Copy-Item .env.example .env
# 然后编辑 .env：至少填 DB_PASSWORD
```

`requirements.txt` 里包含 torch（约 2.5GB），首次安装会比较久。

### 3. 大模型

默认用本机 Ollama：

```powershell
ollama serve
ollama list          # 确认模型名
```

`.env` 里对应三行：

```ini
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:3b
```

> 显存 8GB 的机器建议用 3B～4B 模型，或给 7B+ 模型固定 4096 上下文，
> 否则加载时会 OOM。详见「常见问题」。

换云 API 只改这三行，代码不用动。

### 4. 启动后端

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

### 5. 前端

```powershell
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173 。开发期 `/api` 由 Vite 代理到 `127.0.0.1:8000`。

## 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 探活 |
| GET | `/api/stats` | 两库一致性（chunks 是否等于 vectors） |
| POST | `/api/docs/upload` | 上传文档，同步入库，返回块数与 OCR 页数 |
| GET | `/api/docs` | 文档列表，支持 `status` / `keyword` / 分页 |
| GET | `/api/docs/{id}` | 单个文档详情 |
| GET | `/api/docs/{id}/chunks` | 查看切块结果（调参用） |
| PATCH | `/api/docs/{id}` | 改展示名 |
| DELETE | `/api/docs/{id}` | 删除：向量 + 数据行 + 原文件 |
| GET | `/api/search?q=&top_k=` | 只检索不生成，调试召回用 |
| POST | `/api/chat` | 问答，返回答案 + 引用来源 |
| GET | `/api/conversations` | 会话列表 |
| GET | `/api/conversations/{id}` | 会话详情（消息 + 引用） |

## 入库与检索流程

```text
写入：文件 → loader 抽文字（扫描页走 OCR）→ splitter 切块（500 字 / 80 重叠）
      → bge 编码 → 先写 MySQL 拿自增 id → 再用同一批 id 写 FAISS

读取：问题 → bge 编码 → FAISS 找 top-k 相似片段 → 按 id 回 MySQL 取原文
      → 拼进 prompt → 大模型生成 → 答案与 citation 落库
```

**双库靠 id 对齐**：`chunk.id` 就是 FAISS 的向量 id，所以必须先从 MySQL 拿到 id。

## OCR 说明

- 只对**没有文字层**的页触发，文字版 PDF 完全不受影响
- 中英文混排基本可用；手写体、严重倾斜、低分辨率扫描件效果有限
- 默认 200 DPI；字太小可调到 300（更准但更慢）
- 单份文档默认最多 OCR 30 页，超过会报错，避免几百页扫描件跑十分钟
- 置信度低于 `OCR_MIN_SCORE`（默认 0.5）的识别行会被丢弃

文档列表里出现紫色 **`OCR N 页`** 徽标，表示这份文档有 N 页是识别出来的。

## 可调参数（`backend/.env`）

| 参数 | 默认 | 说明 |
|---|---|---|
| `CHUNK_SIZE` | 500 | 切块字数，改后需重新上传文档 |
| `CHUNK_OVERLAP` | 80 | 块间重叠 |
| `TOP_K` | 5 | 检索返回条数 |
| `OCR_ENABLED` | true | 是否启用 OCR |
| `OCR_DPI` | 200 | PDF 渲染分辨率 |
| `OCR_MAX_PAGES` | 30 | 单份最多 OCR 页数 |
| `OCR_MIN_SCORE` | 0.5 | OCR 置信度阈值 |
| `LLM_*` | — | 模型地址、Key、模型名、温度、长度 |

## 常见问题

**`/api/stats` 显示 `synced: false`**
说明 `chunk` 数和 FAISS 向量数不一致，通常是入库中途失败或删除没清干净。删掉那份文档重新上传即可。

**问答提示「连不上大模型接口」**
Ollama 没启动。运行 `ollama serve`，或检查 `.env` 里的 `LLM_BASE_URL`。

**Ollama 报 `cudaMalloc failed: out of memory`**
显存不够。办法：换更小的模型、或给模型固定 4K 上下文（`PARAMETER num_ctx 4096`），或关掉其他占显存/内存的程序。

**`pip install` 报 `UnicodeDecodeError: 'gbk' codec`**
`requirements.txt` 里有非 ASCII 字符。本仓库已改成纯英文，如果自己加注释请用英文。

**`rapidocr-onnxruntime` 装不上**
Python 版本过高（3.13+ 不支持）。用 Python 3.11 或 3.12 建虚拟环境。

**上传后一直 `processing`**
看后端日志；扫描件没有文字层且 OCR 未启用时会直接失败并写明原因。

**换了 embedding 模型后报维度不一致**
删掉 `backend/data/faiss.index`，清空 `document` / `chunk` 表，重新上传。

## 已知限制

- **单进程**：FAISS 索引在进程内，`--workers > 1` 会导致检索不全
- **上传是同步的**：大文件会让请求等十几秒，未接任务队列
- **单用户**：没有登录与权限隔离
- **会话删除**：只提供读取，未做删除接口

## 说明

- `.env` 含数据库密码，已在 `.gitignore` 中
- `data/`（上传文件、FAISS 索引）和 `models/`（bge 模型）都不进版本库，换机器需单独拷贝或重新生成
