import logging
from pathlib import Path
from typing import Optional

import requests


class TelegramNotifier:
    """
    Lightweight wrapper around the Telegram Bot HTTP API.
    Uses simple POST requests so we do not need extra dependencies.
    """

    def __init__(self, bot_token: str, chat_id: str, request_timeout: int = 30):
        if not bot_token:
            raise ValueError("Telegram bot token is required")
        if not chat_id:
            raise ValueError("Telegram chat id is required")

        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.chat_id = chat_id
        self.timeout = request_timeout
        self._log = logging.getLogger(__name__)

    def _post(self, method: str, data: dict, files: Optional[dict] = None) -> bool:
        url = f"{self.base_url}/{method}"
        try:
            response = requests.post(url, data=data, files=files, timeout=self.timeout)
            if not response.ok:
                self._log.error("Telegram API call failed (%s): %s", response.status_code, response.text)
            return response.ok
        except Exception as exc:
            self._log.error("Telegram API call raised: %s", exc)
            return False

    def send_message(self, text: str, parse_mode: str | None = None) -> bool:
        payload = {"chat_id": self.chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._post("sendMessage", payload)

    def send_photo(self, photo_path: Path, caption: Optional[str] = None) -> bool:
        photo_path = Path(photo_path)
        if not photo_path.exists():
            self._log.error("Photo path does not exist: %s", photo_path)
            return False

        with photo_path.open("rb") as img_file:
            files = {"photo": img_file}
            data = {"chat_id": self.chat_id}
            if caption:
                data["caption"] = caption
            return self._post("sendPhoto", data=data, files=files)

    def send_document(self, file_path: Path, caption: Optional[str] = None) -> bool:
        file_path = Path(file_path)
        if not file_path.exists():
            self._log.error("Document path does not exist: %s", file_path)
            return False

        with file_path.open("rb") as doc_file:
            files = {"document": doc_file}
            data = {"chat_id": self.chat_id}
            if caption:
                data["caption"] = caption
            return self._post("sendDocument", data=data, files=files)
