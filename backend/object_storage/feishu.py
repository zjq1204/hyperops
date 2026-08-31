from dataclasses import dataclass
from urllib.parse import urlencode

import requests

from object_storage.crypto import decrypt_secret


class FeishuProviderError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True)
class FeishuIdentity:
    open_id: str
    union_id: str
    display_name: str
    email: str
    department_ids: tuple[str, ...]
    is_active: bool
    is_eligible: bool = True


class FeishuClient:
    base_url = "https://open.feishu.cn/open-apis"

    def __init__(self, *, timeout=10):
        self.timeout = timeout

    def build_authorization_url(self, *, app_id, state, callback_url):
        return "https://open.feishu.cn/open-apis/authen/v1/authorize?" + urlencode(
            {"app_id": app_id, "redirect_uri": callback_url, "state": state}
        )

    def authenticate(self, *, code, app_config):
        app_secret = decrypt_secret(app_config.app_secret_encrypted)
        tenant_token = self._request_json(
            "POST",
            f"{self.base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_config.app_id, "app_secret": app_secret},
        ).get("tenant_access_token")
        if not tenant_token:
            raise FeishuProviderError("FEISHU_TOKEN_EXCHANGE_FAILED")
        user_token_payload = self._request_json(
            "POST",
            f"{self.base_url}/authen/v1/access_token",
            headers={"Authorization": f"Bearer {tenant_token}"},
            json={"grant_type": "authorization_code", "code": code},
        )
        user_token = (user_token_payload.get("data") or {}).get("access_token")
        if not user_token:
            raise FeishuProviderError("FEISHU_TOKEN_EXCHANGE_FAILED")
        payload = (
            self._request_json(
                "GET",
                f"{self.base_url}/authen/v1/user_info",
                headers={"Authorization": f"Bearer {user_token}"},
            ).get("data")
            or {}
        )
        open_id = str(payload.get("open_id") or "").strip()
        if not open_id:
            raise FeishuProviderError("FEISHU_IDENTITY_INVALID")
        return FeishuIdentity(
            open_id=open_id,
            union_id=str(payload.get("union_id") or ""),
            display_name=str(payload.get("name") or ""),
            email=str(payload.get("email") or ""),
            department_ids=tuple(payload.get("department_ids") or ()),
            is_active=bool(payload.get("is_active", True)),
        )

    def _request_json(self, method, url, **kwargs):
        try:
            response = requests.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise FeishuProviderError("FEISHU_PROVIDER_UNAVAILABLE") from exc
        if payload.get("code") not in (None, 0):
            raise FeishuProviderError("FEISHU_PROVIDER_REJECTED")
        return payload


def get_feishu_client():
    return FeishuClient()
