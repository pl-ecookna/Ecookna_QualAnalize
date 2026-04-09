import logging
import aiohttp
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DirectusClient:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify_ssl = verify_ssl
        
    async def get_items(self, collection: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Получает записи из указанной коллекции Directus.
        """
        url = f"{self.base_url}/items/{collection}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Fetching from {url} with params {params}")
            async with session.get(url, headers=headers, params=params, ssl=self.verify_ssl) as response:
                response.raise_for_status()
                data = await response.json()
                return data

    async def get_item_by_id(self, collection: str, item_id: str | int) -> Dict[str, Any]:
        """
        Получает одну запись по ID из коллекции Directus.
        """
        url = f"{self.base_url}/items/{collection}/{item_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Fetching from {url}")
            async with session.get(url, headers=headers, ssl=self.verify_ssl) as response:
                response.raise_for_status()
                data = await response.json()
                return data

    async def find_items(self, collection: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Возвращает список записей Directus по фильтру/параметрам.
        """
        return await self.get_items(collection, params=params)

    async def create_item(self, collection: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создаёт запись в указанной коллекции.
        """
        url = f"{self.base_url}/items/{collection}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            logger.debug("Creating item in %s", collection)
            async with session.post(url, headers=headers, json=payload, ssl=self.verify_ssl) as response:
                response.raise_for_status()
                return await response.json()

    async def update_item(self, collection: str, item_id: str | int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обновляет запись по ID.
        """
        url = f"{self.base_url}/items/{collection}/{item_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            logger.debug("Updating item %s/%s", collection, item_id)
            async with session.patch(url, headers=headers, json=payload, ssl=self.verify_ssl) as response:
                response.raise_for_status()
                return await response.json()

    async def delete_item(self, collection: str, item_id: str | int) -> None:
        """
        Удаляет запись по ID.
        """
        url = f"{self.base_url}/items/{collection}/{item_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            logger.debug("Deleting item %s/%s", collection, item_id)
            async with session.delete(url, headers=headers, ssl=self.verify_ssl) as response:
                response.raise_for_status()
