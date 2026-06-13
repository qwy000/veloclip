# Cookies 配置说明（服务端运维可选，非用户使用路径）

> 产品设计为：**用户直接粘贴链接即可解析下载**，无需手动配置 Cookie。
> 本节仅供服务端运维人员在特殊平台（如 YouTube 人机验证）需要时使用。

YouTube 等平台对未登录的自动化请求有强风控。若需突破，可在服务端放置 Cookie 文件或设置环境变量（用户无感知）。

> 本目录下的 `*.txt` 不会被提交到 git（见根目录 `.gitignore`）。

## 方式一：按平台放置文件

| 平台 | 文件名 |
| --- | --- |
| YouTube | `youtube.txt` |
| 哔哩哔哩 | `bilibili.txt` |
| 爱奇艺 | `iqiyi.txt` |
| 抖音 | `douyin.txt` |
| TikTok | `tiktok.txt` |
| Instagram | `instagram.txt` |
| X / Twitter | `twitter.txt` |
| 快手 | `kuaishou.txt` |
| 西瓜/今日头条 | `ixigua.txt` |
| 微博 | `weibo.txt` |

也可放置全局 `cookies.txt` 作为兜底。

## 方式二：环境变量

- `YTDLP_COOKIES=D:\path\to\cookies.txt`
- `YTDLP_COOKIES_FROM_BROWSER=edge`（需浏览器已关闭）

## 安全提示

Cookie 等同于登录态，请勿分享或提交到代码仓库。
