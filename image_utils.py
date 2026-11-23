"""Validación y saneo de imágenes de producto subidas por usuarios.

Una imagen subida nunca se guarda tal cual: se comprueba su firma, se
decodifica completa con Pillow (con límite anti "decompression bomb") y se
recodifica desde píxeles a WebP sin metadatos. Así se descarta cualquier
contenido oculto (EXIF, datos anexados, archivos políglotas).
"""
import io
import os
import uuid

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 40_000_000
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
PRODUCT_UPLOAD_DIR = os.path.join("static", "uploads", "products")
_SIGNATURES = {b"\xff\xd8\xff": "JPEG", b"\x89PNG\r\n\x1a\n": "PNG", b"RIFF": "WEBP"}


def sanitize_product_image(data: bytes, size: int = 640) -> bytes:
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("La imagen está vacía o supera los 8 MB.")
    expected = next((fmt for sig, fmt in _SIGNATURES.items() if data.startswith(sig)), None)
    if expected is None:
        raise ValueError("Formato no permitido: solo JPEG, PNG o WebP.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format != expected:
                raise ValueError("El contenido no coincide con el tipo de imagen.")
            probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except ValueError:
        raise
    except Exception as exc:  # imagen corrupta, truncada o bomba de descompresión
        raise ValueError("La imagen está dañada o no es válida.") from exc

    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    out = io.BytesIO()
    canvas.save(out, "WEBP", quality=82, method=6)
    return out.getvalue()


def save_product_image(item_id: str, data: bytes) -> str:
    """Sanea la imagen, la guarda y devuelve la ruta pública para inventory.image_path."""
    clean = sanitize_product_image(data)
    os.makedirs(PRODUCT_UPLOAD_DIR, exist_ok=True)
    name = f"{item_id.lower()}-{uuid.uuid4().hex[:8]}.webp"
    with open(os.path.join(PRODUCT_UPLOAD_DIR, name), "wb") as fh:
        fh.write(clean)
    return "/" + "/".join((PRODUCT_UPLOAD_DIR.replace(os.sep, "/"), name))
