"""Скачивает снимок каталога со старого сайта prom-products.kz в legacy/."""

import json
import urllib.request
from pathlib import Path

BASE_URL = "https://prom-products.kz/api"
OUT_DIR = Path(__file__).resolve().parent.parent / "legacy"


def fetch(name: str) -> list[dict]:
    request = urllib.request.Request(
        f"{BASE_URL}/{name}", headers={"User-Agent": "promproduct-migration/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for name in ("categories", "products"):
        data = fetch(name)
        path = OUT_DIR / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: {len(data)} записей → {path}")


if __name__ == "__main__":
    main()
