# 极速下 · 万能视频下载网站

一个轻量的"万能视频下载"网站：**Python (FastAPI) + yt-dlp** 提供下载能力，**React + Tailwind** 打造商业化界面。全平台、高清无水印、手机电脑随时随地一键下载。

> 核心理念：站在巨人肩膀上，直接封装开源项目 [yt-dlp](https://github.com/yt-dlp/yt-dlp)（十几万 Star），不重复造轮子。

## 功能

- 全平台视频解析与下载（YouTube / B站 / 抖音 / TikTok / X 等上千站点）
- 清晰度自选（最佳 / 1080p / 720p / ... / 仅音频 MP3）
- 实时下载进度（百分比 / 速度 / 剩余时间）
- 高清音视频自动合并（内置 ffmpeg，免手动安装）
- 商业化响应式 UI，含定价区块（视觉展示）

## 技术栈

- 后端：FastAPI + Uvicorn + yt-dlp + imageio-ffmpeg（无数据库，内存任务表）
- 前端：Vite + React + TypeScript + TailwindCSS + lucide-react

## 目录结构

```
backend/    FastAPI 后端 + yt-dlp 封装
frontend/   Vite + React 前端
docs/       需求分析 / 方案设计文档
```

## 本地运行

### 1. 启动后端（端口 8000）

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. 启动前端（端口 5173）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 即可使用。前端 `/api` 请求会自动代理到后端 8000 端口。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/info` | 解析视频信息与可选清晰度 |
| POST | `/api/download` | 创建下载任务，返回 `task_id` |
| GET | `/api/progress/{task_id}` | 查询下载进度 |
| GET | `/api/file/{task_id}` | 下载完成的文件 |

## 文档

- [需求分析](docs/需求分析.md)
- [方案设计](docs/方案设计.md)

## 免责声明

本工具仅供个人学习与合规使用，请勿用于侵犯版权或违反平台服务条款的用途，下载内容的使用责任由用户自行承担。
