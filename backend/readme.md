# 后端 backend

> 这是**目标结构**（要搭的），不是现状。当前目录下只有本文件，其余全靠你自己填。

## 整体项目结构

```text
rag-kb-v2/
├── backend/                 # 后端：FastAPI + MySQL + FAISS
└── frontend/                # 前端：Vue 3
```

## backend 目标目录树

```text
backend/
├── readme.md                        # 本文件
├── requirements.txt                 # Python 依赖
├── .env.example                     # 环境变量模板（复制成 .env 后改）
├── sql/
│   └── schema.sql                   # 建表 SQL：document / chunk / conversation / message / citation
├── eval/
│   ├── questions.example.json       # 评测集模板
│   └── questions.json               # 你的 30 条评测题（question + expect_keywords）
├── scripts/
│   └── eval.py                      # 跑命中率 Hit@k
├── data/                            # 运行时生成，不进版本库
│   ├── docs/                        # 上传的原始文件
│   └── index/
│       └── vectors.faiss            # FAISS 索引落盘
└── app/
    ├── __init__.py
    ├── config.py                    # 所有可调参数的唯一来源（CHUNK_SIZE / TOP_K / 模型名）
    ├── db.py                        # MySQL 连接 + session
    ├── models.py                    # 5 张表的 ORM 定义
    ├── vectorstore.py               # FAISS 封装（IndexIDMap + 内积）
    ├── retrieval.py                 # 查询侧入口：问题 → 片段；创新点在这里扩展
    ├── bm25.py                      # 词法检索（jieba + rank-bm25）
    ├── fusion.py                    # RRF 融合：把多路检索结果合并
    ├── generator.py                 # 拼 prompt + 调大模型（流式）
    ├── main.py                      # FastAPI 接口层（7 个路由）
    └── ingest/                      # 入库管线
        ├── __init__.py
        ├── loader.py                # ① 解析 PDF/Word → [{page, text}]
        ├── splitter.py              # ② 递归切分 + 重叠
        ├── embedder.py              # ③ 文本 → 512 维向量
        └── pipeline.py              # ④ 总装：先写 MySQL 拿 id → 再写 FAISS
```

## 路由清单（main.py 要实现的）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/docs/upload` | 上传文档（后台异步处理） |
| GET | `/api/docs` | 文档列表 + 处理状态 |
| DELETE | `/api/docs/{id}` | 删除（两个库一起清） |
| GET | `/api/stats` | 查两库是否同步（chunks == vectors） |
| GET | `/api/search` | 只检索不生成，调参/建评测集用 |
| POST | `/api/chat` | 流式问答（SSE） |
| GET | `/api/conversations/{id}` | 历史消息 + 引用 |

## 关键约定

- **双库靠 id 对齐**：`chunk.id` 就是 FAISS 里的向量 id，所以必须**先写 MySQL、再写 FAISS**。
- **检索与入库用同一个 embedding 模型**，否则向量不在同一坐标系。
- **参数只改 `config.py`**：改了 `CHUNK_SIZE` 等切分参数后，必须**重新上传文档**，旧 chunk 不算数。
- **接口层保持薄**：业务逻辑放 `ingest/`、`retrieval.py`、`generator.py`，别塞回 `main.py`。
- **embedding 是 CPU 密集**，放线程池；**上传走后台任务**；**问答用 SSE 流式**。
