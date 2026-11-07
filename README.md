# RagKb · 个人知识库问答

上传 PDF / Word / 文本 / 图片，自动解析切块、向量化入库，然后用自然语言提问，答案会标注出自哪个文件、第几页。

检索走「向量 + BM25」双路并用 RRF 融合；OCR 和大模型都在本地跑，文档内容不出本机。

## 快速开始

**环境要求**：Python 3.11 / 3.12、MySQL 8、Node 18+、Ollama

### 1. 建库

```sql
CREATE DATABASE ragkb DEFAULT CHARSET utf8mb4;
```

```bash
mysql -u root -p ragkb < backend/sql/schema.sql
```

### 2. 装后端依赖

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置

```powershell
Copy-Item .env.example .env
```

至少改这几项：

```ini
DB_PASSWORD=你的数据库密码

LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:3b
```

### 4. 启动本地大模型

```powershell
ollama serve
ollama list        # 确认模型名和 .env 里一致
```

### 5. 启动后端

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

接口文档：http://127.0.0.1:8000/docs

### 6. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173

### 7. 验证

1. 文档库上传一个 PDF，状态变成「已入库」
2. 传一份扫描件，出现 `OCR N 页` 徽标
3. 对话页提问，答案带 `[1][2]`，点来源能看原文
4. 刷新页面，历史还在

## 未来计划

- **rerank**：向量 + BM25 融合后再用交叉编码器重排，提升 top-1 命中
- **异步入库**：接任务队列（Celery / RQ），上传立刻返回
- **多用户**：登录、权限、按用户隔离文档
- **评测**：评测集 + Hit@k / MRR 脚本，量化检索效果
- **部署**：Docker Compose 一键启动后端、MySQL、前端
- **会话管理**：删除会话、重命名、导出
- **更多格式**：Excel、PPT、网页链接
