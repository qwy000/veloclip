"""Bilibili 反爬绕过补丁（不修改 yt-dlp 源码，仅运行时 monkeypatch）。

背景：B 站对 `/video/*` 页面做了 WAF 风控，未登录的脚本请求会返回 HTTP 412
（无论 TLS 指纹 / 请求头 / buvid / bili_ticket 如何都拦截）。但 B 站的开放 API
`https://api.bilibili.com/x/web-interface/view` 无需 cookie 即可返回 200，且包含
yt-dlp 提取器所需的全部字段。

yt-dlp 的 BilibiliIE 仅在第一步"下载视频页 HTML"用到网页（为了读取 window.__INITIAL_STATE__），
之后取流(playurl)、防盗链 Referer 都走 API 且工作正常。因此本补丁拦截该网页请求：
当 `/video/` 页面失败时，用 view API 数据合成一段含 __INITIAL_STATE__ 的 HTML 返回，
使后续流程照常工作。
"""
from __future__ import annotations

import json
import re
import types
import urllib.parse

from yt_dlp.extractor.bilibili import BiliBiliIE

_VIEW_API = "https://api.bilibili.com/x/web-interface/view"
_applied = False

# 桌面浏览器 UA。B 站 playurl 取流接口对非浏览器 UA 直接 412，必须强制带上。
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _bvid_query_from_url(url: str, video_id: str) -> dict:
    m = re.search(r"/video/(BV[0-9A-Za-z]+|av\d+|AV\d+)", url)
    if m:
        token = m.group(1)
        if token.lower().startswith("bv"):
            return {"bvid": token}
        return {"aid": token[2:]}
    # 回退：按提取器匹配到的 id 还原
    if str(video_id).lower().startswith("bv"):
        return {"bvid": video_id}
    return {"bvid": f"BV{video_id}"}


def _synthesize_initial_state(ie: "BiliBiliIE", url: str, video_id: str):
    """用 view API 数据合成含 __INITIAL_STATE__ 的网页。失败返回 None。"""
    query = _bvid_query_from_url(url, video_id)
    view = ie._download_json(
        _VIEW_API,
        video_id,
        query=query,
        note="通过开放 API 获取视频信息（绕过网页风控）",
        errnote="开放 API 获取失败",
        fatal=False,
    )
    data = (view or {}).get("data")
    if not isinstance(data, dict):
        return None

    owner = data.get("owner") or {}
    initial_state = {
        "videoData": data,
        "upData": {"name": owner.get("name"), "mid": owner.get("mid")},
    }
    payload = json.dumps(initial_state, ensure_ascii=False)
    return (
        "<!DOCTYPE html><html><head></head><body><script>"
        f"window.__INITIAL_STATE__={payload};"
        "</script></body></html>"
    )


def apply_patch() -> None:
    global _applied
    if _applied:
        return

    original = BiliBiliIE._download_webpage_handle

    def patched(self, url_or_request, video_id, *args, **kwargs):
        url = url_or_request if isinstance(url_or_request, str) else getattr(url_or_request, "url", "")
        if "/video/" not in url:
            return original(self, url_or_request, video_id, *args, **kwargs)
        try:
            webpage, urlh = original(self, url_or_request, video_id, *args, **kwargs)
            # 即使返回 200，若是风控页则没有 __INITIAL_STATE__，也走 API 合成
            if "__INITIAL_STATE__" in (webpage or ""):
                return webpage, urlh
        except Exception:
            pass
        synthetic = _synthesize_initial_state(self, url, video_id)
        if synthetic:
            return synthetic, types.SimpleNamespace(url=url)
        # 兜底：仍按原始行为抛错
        return original(self, url_or_request, video_id, *args, **kwargs)

    BiliBiliIE._download_webpage_handle = patched

    # 确保 B 站所有 API 请求都带浏览器 UA：_real_extract 用 geo_verification_headers()
    # 取请求头（基类默认为空、不含 UA），这里注入桌面 UA 作为兜底。
    _original_geo = BiliBiliIE.geo_verification_headers

    def patched_geo(self):
        headers = _original_geo(self) or {}
        headers.setdefault("User-Agent", _DESKTOP_UA)
        return headers

    BiliBiliIE.geo_verification_headers = patched_geo

    # 关键修复：playurl 取流接口 412 的真正根因（实测定位，两点缺一不可）：
    #   1) yt-dlp 原始实现把"已签名的 query 字典"再交给网络层用 update_url_query 二次
    #      编码，破坏了 w_rid 签名 -> 改为自行拼成完整 URL，不再用 query= 二次编码；
    #   2) Referer 指向被 WAF 风控的 /video/ 页面会被拦 412 -> 改用站点首页作为 Referer。
    # 修复后仍走 yt-dlp 网络层，保留 cookie / 代理 / UA 等能力。免 Cookie 实测可取流。
    def patched_download_playinfo(
        self,
        bvid,
        cid,
        headers=None,
        query=None,
        *args,
        fatal=True,
        **kwargs,
    ):
        params = {"bvid": bvid, "cid": cid, "fnval": 4048, **(query or {})}
        if self.is_logged_in:
            params.pop("try_look", None)
        if qn := params.get("qn"):
            note = f"Downloading video format {qn} for cid {cid}"
        else:
            note = f"Downloading video formats for cid {cid}"
        signed = self._sign_wbi(params, bvid)
        full_url = (
            "https://api.bilibili.com/x/player/wbi/playurl?"
            + urllib.parse.urlencode(signed)
        )
        req_headers = dict(headers or {})
        req_headers["User-Agent"] = _DESKTOP_UA
        req_headers["Referer"] = "https://www.bilibili.com/"
        result = self._download_json(
            full_url,
            bvid,
            headers=req_headers,
            note=note,
            fatal=fatal,
        )
        return (result or {}).get("data")

    BiliBiliIE._download_playinfo = patched_download_playinfo
    _applied = True
