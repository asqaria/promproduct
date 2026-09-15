from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

FULL_MAX_SIDE = 1600
THUMB_MAX_SIDE = 400
WEBP_QUALITY = 82


def _encode(image: Image.Image, max_side: int) -> ContentFile:
    copy = image.copy()
    copy.thumbnail((max_side, max_side))
    buffer = BytesIO()
    copy.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
    return ContentFile(buffer.getvalue())


def to_webp(file) -> tuple[ContentFile, ContentFile]:
    """Возвращает (полное изображение ≤1600 px, миниатюру ≤400 px) в WebP."""
    if hasattr(file, "seek"):
        file.seek(0)
    with Image.open(file) as source:
        image = ImageOps.exif_transpose(source)
        has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
        image = image.convert("RGBA" if has_alpha else "RGB")
        return _encode(image, FULL_MAX_SIDE), _encode(image, THUMB_MAX_SIDE)
