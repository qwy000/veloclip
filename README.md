# VeloClip · 万能视频下载网站

一个轻量的全平台视频下载与 AI 分析网站：**Python (FastAPI) + yt-dlp** 提供解析与下载，**React + Tailwind** 打造商业化界面。支持粘贴直链或嵌入页链接，在浏览器中完成解析、下载与 DeepSeek 智能总结。

> 核心理念：站在巨人肩膀上，直接封装开源项目 [yt-dlp](https://github.com/yt-dlp/yt-dlp)，不重复造轮子。

**仓库**：https://github.com/qwy000/veloclip

## 功能

### 视频下载

- 全平台视频解析与下载（YouTube / B 站 / 抖音 / TikTok / X 等上千站点）
- **课程/文章页嵌入视频自动识别**（从 HTML 提取 B 站、YouTube 等直链）
- 清晰度自选（**最佳画质标注具体分辨率** / 720p / 480p / … / 仅音频 MP3）
- 实时下载进度（百分比 / 速度 / 剩余时间）
- 高清音视频自动合并（内置 ffmpeg，免手动安装）
- 可选平台 Cookie（`backend/cookies/`，用于需登录的内容）

### AI 视频分析（解析页内嵌）

- 字幕提取（CC / 自动字幕 / B 站弹幕兜底）
- **无字幕元数据降级**（X 等平台：基于标题、简介等继续分析）
- DeepSeek 总结、思维导图（全屏 / 导出 PNG）、AI 提问
- `subtitle_source`：`cc` | `auto` | `danmaku` | `metadata`

### 界面

- 品牌 **VeloClip**，响应式商业化 UI
- 会员定价三档横向紧凑展示（**当前为视觉规划，下载功能免费开放**）
- 「立即免费下载」跳转至页面顶部下载区（`#download`）

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | FastAPI、Uvicorn、yt-dlp、imageio-ffmpeg、DeepSeek API |
| 前端 | Vite、React、TypeScript、TailwindCSS、lucide-react |
| 存储 | 无数据库；内存任务表 + 临时下载目录 |

## 目录结构

```
backend/          FastAPI 后端 + yt-dlp 封装
  app/services/   downloader、transcript、ai_analyzer、bili_patch
  cookies/        各平台 Netscape Cookie（不入库）
  tests/          单元测试
frontend/         Vite + React 前端
docs/             需求分析 / 方案设计
```

## 本地运行

### 1. 启动后端（开发端口 8001）

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

> 前端 Vite 代理指向 **8001**。若 Windows 上 8000 被无法结束的旧 python 进程占用，请改用 8001，或重启电脑后再用 8000。  
> 修改后端代码后需重启 uvicorn；可访问 `GET /health` 查看 `pid` 确认是否为新进程。

复制 `backend/.env.example` 为 `backend/.env` 并填写 `DEEPSEEK_API_KEY` 以启用 AI 分析。

### 2. 启动前端（端口 5173）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 即可使用。

## 测试

```bash
# 字幕与解析单元测试
cd backend && python -m unittest tests.test_transcript -v

# B 站 AI 联调（--analyze 需 DeepSeek Key）
python scripts/test_ai_integration.py --url "https://www.bilibili.com/video/BV1dD42137cz/"
```

## API 摘要

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/info` | 解析视频信息与可选清晰度 |
| POST | `/api/download` | 创建下载任务 |
| GET | `/api/progress/{task_id}` | 查询下载进度 |
| POST | `/api/cancel/{task_id}` | 取消下载 |
| GET | `/api/file/{task_id}` | 下载完成的文件 |
| POST | `/api/ai/analyze` | AI 总结 + 思维导图 |
| POST | `/api/ai/transcript` | 仅提取字幕（严格模式） |
| POST | `/api/ai/chat` | 基于字幕或元数据的问答 |
| GET | `/health` | 健康检查（含 `pid`） |

## 文档

- [需求分析](docs/需求分析.md)
- [方案设计](docs/方案设计.md)

## 免责声明

本工具仅供个人学习与合规使用。请遵守各平台服务条款与版权规定，勿用于侵犯他人版权或违规用途；下载内容的使用责任由用户自行承担。本站不持久存储用户下载的视频文件。
