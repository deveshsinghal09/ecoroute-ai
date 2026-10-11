"""Server-only Gemini transport; only approved statement IDs can reach the UI."""
import json
import re

import httpx


class GeminiUnavailable(Exception):
    """Allowlisted diagnostics only; never includes provider text or credentials."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Gemini:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client

    def key(self):
        value = self.settings.gemini_api_key.get_secret_value()
        if value:
            return value
        if not self.settings.gemini_secret_arn:
            raise ValueError("gemini_key_missing")
        from ecoroute.advisory.notifications import aws_client
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            response = aws_client(self.settings, "secretsmanager").get_secret_value(
                SecretId=self.settings.gemini_secret_arn)
            value = response["SecretString"].strip()
            if value.startswith(("{", "[", '"')):
                value = json.loads(value)["api_key"]
        except (BotoCoreError, ClientError):
            raise GeminiUnavailable("gemini_secret_unavailable") from None
        except (ValueError, KeyError, TypeError):
            raise GeminiUnavailable("gemini_secret_invalid") from None
        if not isinstance(value, str) or not value or any(c.isspace() for c in value):
            raise ValueError("gemini_key_missing")
        return value

    def arrange(self, system, facts, statements):
        model = self.settings.gemini_model_id
        if not re.fullmatch(r"gemini-[a-zA-Z0-9.-]{1,100}", model):
            raise ValueError("gemini_model_invalid")
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps({
                "facts": facts, "approved_statements": statements})}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 512,
                "responseMimeType": "application/json", "responseSchema": {
                    "type": "OBJECT", "properties": {"statement_ids": {
                        "type": "ARRAY", "items": {"type": "STRING", "enum": list(statements)}}},
                    "required": ["statement_ids"]}},
        }
        if model == "gemini-2.5-flash":
            # This bounded statement-ordering task needs no hidden reasoning budget.
            payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
        def send(client):
            with client.stream("POST", "https://generativelanguage.googleapis.com/v1beta/models/"
                               + model + ":generateContent", json=payload,
                               headers={"x-goog-api-key": self.key()}) as response:
                if response.status_code != 200:
                    raise GeminiUnavailable({400: "gemini_request_rejected", 401: "gemini_access_denied",
                        403: "gemini_access_denied", 404: "gemini_model_unavailable",
                        429: "gemini_provider_quota"}.get(response.status_code, "gemini_provider_unavailable"))
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 65536:
                        raise ValueError("gemini_response_too_large")
                    chunks.append(chunk)
                result = json.loads(b"".join(chunks))
            candidates = result.get("candidates", [])
            if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
                raise GeminiUnavailable("gemini_incomplete_or_blocked")
            parts = candidates[0]["content"]["parts"]
            if len(parts) != 1 or "text" not in parts[0] or set(parts[0]) - {"text", "thoughtSignature"}:
                raise ValueError("gemini_invalid_content")
            # Signature metadata is never returned/stored; only validated statement IDs are used.
            usage = result.get("usageMetadata", {})
            usage = {k: v for k, v in usage.items() if k in {
                "promptTokenCount", "candidatesTokenCount", "totalTokenCount"}
                and type(v) is int and v >= 0}
            return json.loads(parts[0]["text"]), usage
        if self.client is not None:
            return send(self.client)
        with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
            return send(client)
