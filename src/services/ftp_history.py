"""
ЕФРСБ исторические архивы — загрузчик через HTTPS.

Сервер: https://download.fedresurs.ru/export_messages/
Auth:   HTTP Basic (demowebuser / Ax!761BN)

Архивы — ZIP-файлы с XML внутри. Скачиваем только новые (по ETag/Last-Modified).
"""

import asyncio
import hashlib
import logging
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------
ARCHIVE_BASE_URL = "https://download.fedresurs.ru/export_messages/"
ARCHIVE_AUTH = httpx.BasicAuth("demowebuser", "Ax!761BN")
DOWNLOAD_DIR = Path("/tmp/efrsb_archives")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Максимальный размер одного архива для скачивания (МБ)
MAX_ARCHIVE_MB = 200

# ---------------------------------------------------------------------------
# Клиент
# ---------------------------------------------------------------------------


class EfrsbArchiveClient:
    """Асинхронный клиент для скачивания ZIP-архивов ЕФРСБ по HTTPS."""

    def __init__(
        self,
        base_url: str = ARCHIVE_BASE_URL,
        auth: httpx.BasicAuth = ARCHIVE_AUTH,
        download_dir: Path = DOWNLOAD_DIR,
        max_archive_mb: int = MAX_ARCHIVE_MB,
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.auth = auth
        self.download_dir = download_dir
        self.max_archive_mb = max_archive_mb
        self._client = httpx.AsyncClient(
            auth=self.auth,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "FedresursPro/1.0"},
        )

    async def __aenter__(self) -> "EfrsbArchiveClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Листинг файлов
    # ------------------------------------------------------------------

    async def list_archives(self) -> List[dict]:
        """
        Возвращает список архивов из HTML-директории.
        Каждый элемент: {"name": str, "size": int, "last_modified": str}
        """
        resp = await self._client.get(self.base_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        archives = []

        for link in soup.find_all("a", href=True):
            href: str = link["href"]
            if not href.endswith(".zip"):
                continue

            name = href.split("/")[-1]
            # Пробуем найти размер в тексте рядом
            size_bytes = 0
            last_modified = ""

            # Некоторые Apache-style листинги дают размер в соседних td
            row = link.find_parent("tr")
            if row:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    last_modified = cells[1].get_text(strip=True)
                    size_str = cells[2].get_text(strip=True).replace(",", "").replace(" ", "")
                    try:
                        size_bytes = int(size_str)
                    except ValueError:
                        pass

            archives.append(
                {
                    "name": name,
                    "url": self.base_url + name,
                    "size_bytes": size_bytes,
                    "last_modified": last_modified,
                }
            )

        logger.info("Найдено архивов на сервере: %d", len(archives))
        return archives

    # ------------------------------------------------------------------
    # Проверка нового файла через HEAD
    # ------------------------------------------------------------------

    async def get_remote_meta(self, archive_name: str) -> dict:
        """HEAD-запрос: получить ETag, Content-Length, Last-Modified."""
        url = self.base_url + archive_name
        resp = await self._client.head(url)
        resp.raise_for_status()
        return {
            "etag": resp.headers.get("etag", ""),
            "content_length": int(resp.headers.get("content-length", 0)),
            "last_modified": resp.headers.get("last-modified", ""),
        }

    # ------------------------------------------------------------------
    # Скачивание
    # ------------------------------------------------------------------

    async def download_archive(self, archive_name: str, dest_dir: Optional[Path] = None) -> Path:
        """
        Скачивает ZIP-архив в dest_dir (по умолчанию self.download_dir).
        Возвращает путь к скачанному файлу.
        Пропускает, если файл уже существует и совпадает по размеру.
        """
        dest_dir = dest_dir or self.download_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / archive_name

        url = self.base_url + archive_name

        # Проверяем размер через HEAD
        try:
            meta = await self.get_remote_meta(archive_name)
            remote_size = meta["content_length"]
        except Exception as e:
            logger.warning("HEAD для %s не удался: %s — скачиваем вслепую", archive_name, e)
            remote_size = 0

        if remote_size > self.max_archive_mb * 1024 * 1024:
            logger.warning(
                "Архив %s слишком большой (%d МБ > лимит %d МБ), пропускаем",
                archive_name,
                remote_size // 1024 // 1024,
                self.max_archive_mb,
            )
            raise ValueError(f"Архив {archive_name} превышает лимит {self.max_archive_mb} МБ")

        # Если файл уже скачан и размер совпадает — пропускаем
        if dest_path.exists() and remote_size > 0 and dest_path.stat().st_size == remote_size:
            logger.info("Архив %s уже скачан (размер совпадает), пропускаем", archive_name)
            return dest_path

        logger.info("Скачиваем %s (%d байт)...", archive_name, remote_size)
        tmp_path = dest_path.with_suffix(".tmp")

        try:
            async with self._client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)

            tmp_path.rename(dest_path)
            logger.info("Скачан: %s (%d байт)", archive_name, dest_path.stat().st_size)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        return dest_path

    # ------------------------------------------------------------------
    # Распаковка
    # ------------------------------------------------------------------

    def extract_archive(self, zip_path: Path, extract_dir: Optional[Path] = None) -> List[Path]:
        """
        Распаковывает ZIP-архив. Возвращает список путей к XML-файлам.
        """
        extract_dir = extract_dir or zip_path.parent / zip_path.stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        xml_files: List[Path] = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if member.endswith(".xml"):
                    zf.extract(member, extract_dir)
                    xml_files.append(extract_dir / member)

        logger.info("Распаковано %d XML из %s", len(xml_files), zip_path.name)
        return xml_files

    # ------------------------------------------------------------------
    # Проверка доступности сервера
    # ------------------------------------------------------------------

    async def check_connection(self) -> bool:
        """Проверяет доступность сервера. Возвращает True если OK."""
        try:
            resp = await self._client.head(self.base_url, timeout=10.0)
            ok = resp.status_code < 400
            if ok:
                logger.info("Сервер архивов доступен: %s (HTTP %d)", self.base_url, resp.status_code)
            else:
                logger.warning("Сервер вернул HTTP %d", resp.status_code)
            return ok
        except Exception as e:
            logger.error("Сервер архивов недоступен: %s", e)
            return False


# ---------------------------------------------------------------------------
# Быстрая проверка из командной строки
# ---------------------------------------------------------------------------


async def _smoke_test() -> None:
    async with EfrsbArchiveClient() as client:
        ok = await client.check_connection()
        if not ok:
            print("ОШИБКА: сервер недоступен")
            return

        archives = await client.list_archives()
        if not archives:
            print("Архивов не найдено (или нет прав на листинг)")
            return

        print(f"Найдено архивов: {len(archives)}")
        for a in archives[:5]:
            print(f"  {a['name']}  {a['size_bytes']:,} байт  {a['last_modified']}")

        # Скачиваем первый архив
        first = archives[0]
        print(f"\nСкачиваем {first['name']}...")
        path = await client.download_archive(first["name"])
        print(f"Сохранён: {path}")

        # Распаковываем
        xml_files = client.extract_archive(path)
        print(f"XML файлов: {len(xml_files)}")
        if xml_files:
            print(f"Первый XML: {xml_files[0]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(_smoke_test())
