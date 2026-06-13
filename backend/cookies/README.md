# Cookies 配置说明（突破 YouTube / B站 等平台风控）

YouTube、哔哩哔哩等平台对未登录的自动化请求有强风控（YouTube 的"确认你不是机器人"、B 站视频页 WAF 返回 412）。
业界通用解法是：携带**已登录浏览器导出的 Cookie**。本目录用于存放这些 Cookie 文件（Netscape 格式）。

> 本目录下的 `*.txt` 不会被提交到 git（见根目录 `.gitignore`），请放心存放。

## 一、如何导出 Cookie（推荐：浏览器扩展）

1. 在你的浏览器安装扩展 **「Get cookies.txt LOCALLY」**（Chrome/Edge 应用商店搜索即可，开源、本地导出、不上传）。
2. 登录目标平台（如 youtube.com、bilibili.com）。
3. 打开该平台页面，点击扩展图标 → Export，得到一个 `cookies.txt`。

## 二、放到这里

按平台命名放入本目录（后端会按域名自动匹配）：

| 平台 | 文件名 |
| --- | --- |
| YouTube | `youtube.txt` |
| 哔哩哔哩 | `bilibili.txt` |
| 抖音 | `douyin.txt`（通常无需，抖音多数可直接下载） |
| TikTok | `tiktok.txt`（通常无需，可直接下载） |
| Instagram | `instagram.txt` |
| X / Twitter | `twitter.txt` |
| 快手 | `kuaishou.txt` |
| 西瓜/今日头条 | `ixigua.txt` |
| 微博 | `weibo.txt` |

也可以放一个**全局** `cookies.txt`，作为所有平台的兜底。

## 三、其他方式（可选）

- 环境变量指定单一文件：`set YTDLP_COOKIES=D:\path\to\cookies.txt`
- 直接从浏览器读取（需浏览器**已完全关闭**，且新版 Chrome/Edge 的应用绑定加密可能导致失败）：
  `set YTDLP_COOKIES_FROM_BROWSER=edge`（可选 chrome/edge/firefox）

## 四、安全提示

Cookie 等同于你的登录态，请勿分享或提交到代码仓库。本目录已被 git 忽略。
