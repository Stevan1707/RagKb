# 前端 frontend

> 这是**目标结构**（要搭的），不是现状。当前目录下只有本文件，其余全靠你自己填。
> 默认按 **Vue 3 + Vite + TypeScript** 规划；想用 JS 就去掉 `tsconfig.json` 和 `.ts` 后缀，目录树结构不变。

## 整体项目结构

```text
rag-kb-v2/
├── backend/                 # 后端：FastAPI + MySQL + FAISS
└── frontend/                # 前端：Vue 3
```

## frontend 目标目录树

```text
frontend/
├── readme.md                        # 本文件
├── package.json                     # 依赖与脚本（dev / build）
├── vite.config.ts                   # Vite 配置（含 /api 代理到后端）
├── tsconfig.json                    # TS 配置（用 JS 可删）
├── index.html                       # 页面入口
├── .env.example                     # VITE_API_BASE=http://127.0.0.1:8000
├── public/
│   └── favicon.ico
└── src/
    ├── main.ts                      # 入口：挂载 App + router + pinia
    ├── App.vue                      # 根组件 / 布局
    ├── api/
    │   ├── http.ts                  # fetch/axios 封装 + 统一错误处理
    │   ├── docs.ts                  # 文档接口：上传 / 列表 / 删除 / stats
    │   └── chat.ts                  # 问答接口：SSE 流式接收 + 历史记录
    ├── router/
    │   └── index.ts                 # 路由表
    ├── stores/
    │   ├── docs.ts                  # 文档列表与处理状态
    │   └── chat.ts                  # 会话 / 消息 / 流式接收状态
    ├── views/
    │   ├── ChatView.vue             # 对话主界面
    │   └── DocsView.vue             # 文档管理
    ├── components/
    │   ├── UploadPanel.vue          # 上传 + 状态轮询
    │   ├── ChatMessage.vue          # 单条消息（打字机效果）
    │   └── SourceList.vue           # 引用来源 [1][2] → 文档 + 页码
    ├── types/
    │   └── api.ts                   # 与后端契约对应的类型定义
    └── assets/
        └── styles/
            └── main.css             # 全局样式
```

## 要对接的后端接口

| 方法 | 路径 | 前端对应位置 |
|---|---|---|
| POST | `/api/docs/upload` | `api/docs.ts` + `UploadPanel.vue` |
| GET | `/api/docs` | `api/docs.ts` + `stores/docs.ts` |
| DELETE | `/api/docs/{id}` | `api/docs.ts` + `DocsView.vue` |
| GET | `/api/stats` | `api/docs.ts`（两库同步徽标） |
| GET | `/api/search` | `api/docs.ts`（调试用，可选） |
| POST | `/api/chat` | `api/chat.ts` + `ChatView.vue` |
| GET | `/api/conversations/{id}` | `api/chat.ts` + `stores/chat.ts` |

## 关键约定

- **`/api/chat` 是 SSE 流式**：不能用普通 JSON 请求承接，要用 `fetch` + `ReadableStream` 逐块读取（或 `EventSource`，注意它只支持 GET）。收到 `type: "delta"` 追加上屏，收到 `type: "sources"` 记下引用。
- **上传是后台异步**：`/api/docs/upload` 立刻返回 `doc_id`，之后要轮询 `/api/docs` 直到 `status == "done"`。
- **引用溯源**：答案里的 `[1][2]` 对应 `sources` 数组的 `rank`，用 `doc_name` + `page` 渲染来源。
- **开发期跨域**：在 `vite.config.ts` 里把 `/api` 代理到 `http://127.0.0.1:8000`，或后端开 CORS。
