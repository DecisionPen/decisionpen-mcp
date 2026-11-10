"""S3 access for Edge MCP using boto3 default credential chain / profile / keys."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from decisionpen_mcp.config import EdgeConfig


class S3EdgeClient:
    def __init__(self, cfg: EdgeConfig):
        try:
            import boto3
        except ImportError as e:
            raise ImportError(
                "boto3 is required for Edge MCP S3. pip install boto3"
            ) from e

        session_kwargs: Dict[str, Any] = {}
        if cfg.aws_profile:
            session_kwargs["profile_name"] = cfg.aws_profile
        session = boto3.Session(**session_kwargs)

        client_kwargs: Dict[str, Any] = {}
        if cfg.region:
            client_kwargs["region_name"] = cfg.region
        if cfg.aws_access_key_id and cfg.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = cfg.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = cfg.aws_secret_access_key
            if cfg.region:
                client_kwargs["region_name"] = cfg.region

        self._client = session.client("s3", **client_kwargs)
        self._cfg = cfg

    def list_level(
        self,
        prefix: str,
        *,
        max_keys: int,
        continuation_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List immediate children (Delimiter=/) under prefix."""
        kwargs: Dict[str, Any] = {
            "Bucket": self._cfg.bucket,
            "Prefix": prefix or "",
            "Delimiter": "/",
            "MaxKeys": max_keys,
        }
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        return self._client.list_objects_v2(**kwargs)

    def list_recursive(
        self,
        prefix: str,
        *,
        max_keys: int,
    ) -> List[Dict[str, Any]]:
        """Flat list of objects under prefix (no delimiter), capped at max_keys."""
        items: List[Dict[str, Any]] = []
        token: Optional[str] = None
        while len(items) < max_keys:
            page_size = min(100, max_keys - len(items))
            kwargs: Dict[str, Any] = {
                "Bucket": self._cfg.bucket,
                "Prefix": prefix or "",
                "MaxKeys": page_size,
            }
            if token:
                kwargs["ContinuationToken"] = token
            resp = self._client.list_objects_v2(**kwargs)
            for obj in resp.get("Contents") or []:
                key = obj.get("Key") or ""
                if not key or key.endswith("/"):
                    continue
                items.append(obj)
                if len(items) >= max_keys:
                    break
            token = resp.get("NextContinuationToken")
            if not token:
                break
        return items

    def head(self, key: str) -> Dict[str, Any]:
        return self._client.head_object(Bucket=self._cfg.bucket, Key=key)

    def get_bytes(self, key: str) -> Tuple[bytes, Dict[str, Any]]:
        resp = self._client.get_object(Bucket=self._cfg.bucket, Key=key)
        body = resp.get("Body")
        if body is None:
            raise ValueError("S3 GetObject returned no body")
        data = body.read()
        meta = {
            "content_type": resp.get("ContentType"),
            "content_length": resp.get("ContentLength") or len(data),
            "etag": (resp.get("ETag") or "").strip('"'),
            "last_modified": _iso(resp.get("LastModified")),
        }
        return data, meta


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def object_to_item(obj: Dict[str, Any], bucket: str) -> Dict[str, Any]:
    key = obj.get("Key") or ""
    name = key.rsplit("/", 1)[-1]
    last_modified = _iso(obj.get("LastModified"))
    return {
        "item_id": key,
        "name": name,
        "size": int(obj.get("Size") or 0),
        "last_modified": last_modified,
        "uri": f"s3://{bucket}/{key}",
        "source_system": "s3",
    }
