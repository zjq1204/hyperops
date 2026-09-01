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
    status_reason: str = ""


class FeishuClient:
    base_url = "https://open.feishu.cn/open-apis"

    def __init__(self, *, timeout=10):
        self.timeout = timeout

    def build_authorization_url(self, *, app_id, state, callback_url):
        return "https://open.feishu.cn/open-apis/authen/v1/authorize?" + urlencode(
            {"app_id": app_id, "redirect_uri": callback_url, "state": state}
        )

    def authenticate(self, *, code, app_config):
        tenant_token = self._tenant_token(app_config)
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
        return self._identity_from_payload(
            payload, invalid_code="FEISHU_IDENTITY_INVALID"
        )

    def list_visible_users(self, *, app_config):
        """Enumerate users visible to the configured app through Contacts API."""
        tenant_token = self._tenant_token(app_config)
        headers = {"Authorization": f"Bearer {tenant_token}"}
        page_token = ""
        identities = []
        seen_open_ids = set()

        while True:
            params = {
                "department_id": "0",
                "department_id_type": "open_department_id",
                "user_id_type": "open_id",
                "page_size": 50,
            }
            if page_token:
                params["page_token"] = page_token
            try:
                payload = self._request_json(
                    "GET",
                    f"{self.base_url}/contact/v3/users/find_by_department",
                    headers=headers,
                    params=params,
                )
            except FeishuProviderError as exc:
                error_code = {
                    "FEISHU_PROVIDER_UNAVAILABLE": "FEISHU_CONTACTS_UNAVAILABLE",
                    "FEISHU_PROVIDER_REJECTED": "FEISHU_CONTACTS_REQUEST_REJECTED",
                }.get(exc.error_code, exc.error_code)
                raise FeishuProviderError(error_code) from exc
            data = payload.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                raise FeishuProviderError("FEISHU_CONTACTS_RESPONSE_INVALID")
            for item in data["items"]:
                if not isinstance(item, dict):
                    raise FeishuProviderError("FEISHU_CONTACTS_RESPONSE_INVALID")
                identity = self._identity_from_payload(item)
                if identity.open_id in seen_open_ids:
                    raise FeishuProviderError("FEISHU_CONTACTS_RESPONSE_INVALID")
                seen_open_ids.add(identity.open_id)
                identities.append(identity)

            if not data.get("has_more"):
                return identities
            next_page_token = str(data.get("page_token") or "").strip()
            if not next_page_token or next_page_token == page_token:
                raise FeishuProviderError("FEISHU_CONTACTS_RESPONSE_INVALID")
            page_token = next_page_token

    def _identity_from_payload(
        self, payload, *, invalid_code="FEISHU_CONTACTS_RESPONSE_INVALID"
    ):
        open_id = str(payload.get("open_id") or "").strip()
        if not open_id:
            raise FeishuProviderError(invalid_code)
        raw_status = payload.get("status") or {}
        status = raw_status if isinstance(raw_status, dict) else {}
        if payload.get("is_deleted") or status.get("is_deleted"):
            is_active = False
            status_reason = "deleted"
        elif (
            payload.get("is_active") is False
            or status.get("is_frozen")
            or status.get("is_resigned")
            or status.get("is_activated") is False
        ):
            is_active = False
            status_reason = "deactivated"
        else:
            is_active = True
            status_reason = ""
        is_eligible = bool(payload.get("is_eligible", True))
        if not is_eligible and not status_reason:
            status_reason = "outside_scope"
        return FeishuIdentity(
            open_id=open_id,
            union_id=str(payload.get("union_id") or ""),
            display_name=str(payload.get("name") or ""),
            email=str(payload.get("email") or ""),
            department_ids=tuple(payload.get("department_ids") or ()),
            is_active=is_active,
            is_eligible=is_eligible,
            status_reason=status_reason,
        )

    def validate_config(self, app_config):
        self._tenant_token(app_config)
        return {"app_id": app_config.app_id, "authenticated": True}

    def _tenant_token(self, app_config):
        app_secret = decrypt_secret(app_config.app_secret_encrypted)
        tenant_token = self._request_json(
            "POST",
            f"{self.base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_config.app_id, "app_secret": app_secret},
        ).get("tenant_access_token")
        if not tenant_token:
            raise FeishuProviderError("FEISHU_TOKEN_EXCHANGE_FAILED")
        return tenant_token

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
