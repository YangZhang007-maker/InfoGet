"""Detect login pages, captchas, and common access-control responses."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class AccessAssessment:
    blocked: bool = False
    login_required: bool = False
    captcha_detected: bool = False
    warnings: list[str] = field(default_factory=list)


LOGIN_MARKERS = ("password", "登录", "登陆", "sign in", "log in", "institutional access")
CAPTCHA_MARKERS = ("captcha", "recaptcha", "hcaptcha", "验证码", "verify you are human")


def assess_access(status_code: int, html: str) -> AccessAssessment:
    lowered = (html or "").casefold()
    login_form = bool(re.search(r"<input[^>]+type=[\"']password", lowered))
    login_text = any(marker in lowered for marker in LOGIN_MARKERS)
    title_login = bool(re.search(
        r"<title[^>]*>[^<]*(登录|登陆|sign\s*in|log\s*in)[^<]*</title>", lowered
    ))
    captcha = any(marker in lowered for marker in CAPTCHA_MARKERS)
    assessment = AccessAssessment(
        blocked=status_code in {401, 403} or captcha or (login_form and login_text) or title_login,
        login_required=login_form or title_login,
        captcha_detected=captcha,
    )
    if status_code in {401, 403}:
        assessment.warnings.append(f"目标网站返回 HTTP {status_code}，需要授权或启用了访问保护。")
    if assessment.login_required:
        assessment.warnings.append("检测到登录/机构访问要求，已终止抓取。")
    if assessment.captcha_detected:
        assessment.warnings.append("检测到验证码或人机验证，已终止抓取。")
    return assessment
