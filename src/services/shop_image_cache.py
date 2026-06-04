"""
Shop image cache
=================

A tiny in-memory cache for sprites pulled from the Omninet shop endpoints
(module icons / logos, cosmetic previews, etc).  The cache survives
view-rebuilds inside SceneConnect so navigating between menus does not
re-fetch the same sprite over and over (the issue that caused module
icons to "stop loading" after a few back-and-forth navigations was the
absence of any persistence — each new ShopModulesView started with empty
icon refs and the network races would frequently drop the response).

Usage:

    from services.shop_image_cache import shop_image_cache
    surf = shop_image_cache.get(module_id, 'icon')
    if surf is None:
        surf = omninet_service.get_module_sprite(module_id, 'icon')
        if surf is not None:
            shop_image_cache.put(module_id, 'icon', surf)

The cache stores up to ``max_entries`` surfaces; the oldest entries are
evicted when full.  Keys are arbitrary strings — the convention for shop
sprites is ``"<kind>:<item_id>:<variant>"`` so the same item can have
multiple cached variants without colliding.
"""
from collections import OrderedDict
from threading import Lock


class _ShopImageCache:
    def __init__(self, max_entries: int = 128):
        self._entries: "OrderedDict[str, object]" = OrderedDict()
        self._max = max_entries
        self._lock = Lock()

    @staticmethod
    def _key(item_id: str, variant: str, kind: str = "module") -> str:
        return f"{kind}:{item_id}:{variant}"

    def get(self, item_id: str, variant: str, kind: str = "module"):
        if not item_id:
            return None
        k = self._key(item_id, variant, kind)
        with self._lock:
            surface = self._entries.get(k)
            if surface is not None:
                # Touch for LRU ordering
                self._entries.move_to_end(k)
            return surface

    def put(self, item_id: str, variant: str, surface, kind: str = "module"):
        if not item_id or surface is None:
            return
        k = self._key(item_id, variant, kind)
        with self._lock:
            self._entries[k] = surface
            self._entries.move_to_end(k)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)

    def clear(self):
        with self._lock:
            self._entries.clear()

    def __len__(self):
        with self._lock:
            return len(self._entries)


# Process-wide singleton.
shop_image_cache = _ShopImageCache()
