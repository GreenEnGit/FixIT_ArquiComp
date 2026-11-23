"""Validación y saneo de imágenes subidas por usuarios.

Una imagen subida nunca se guarda tal cual: se comprueba su firma, se
decodifica completa con Pillow (con límite anti "decompression bomb") y se
recodifica desde píxeles a WebP sin metadatos. Así se descarta cualquier
contenido oculto (EXIF, datos anexados, archivos políglotas) y el archivo
servido siempre es .webp, sin importar la extensión que envió el usuario.
"""
import io
import os
import uuid

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 40_000_000
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
PRODUCT_UPLOAD_DIR = os.path.join("static", "uploads", "products")


def _detect_format(data: bytes):
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def _decode(data: bytes) -> Image.Image:
    """Valida firma, estructura y decodificación completa; devuelve la imagen en RGB."""
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("La imagen está vacía o supera los 8 MB.")
    expected = _detect_format(data)
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
    return ImageOps.exif_transpose(img).convert("RGB")


def _to_webp(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, "WEBP", quality=82, method=6)  # sin EXIF/ICC/XMP
    return out.getvalue()


def sanitize_image(data: bytes, max_side: int = 1600) -> bytes:
    """Recibos y fotos de equipos: conserva la proporción, limita el lado mayor."""
    img = _decode(data)
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    return _to_webp(img)


def sanitize_product_image(data: bytes, size: int = 640) -> bytes:
    """Fotos de catálogo: cuadradas sobre fondo blanco para una cuadrícula uniforme."""
    img = _decode(data)
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return _to_webp(canvas)


def write_upload(directory: str, prefix: str, clean_webp: bytes) -> str:
    """Guarda bytes ya saneados con nombre aleatorio .webp; devuelve la ruta pública."""
    os.makedirs(directory, exist_ok=True)
    safe_prefix = "".join(ch for ch in prefix.lower() if ch.isalnum() or ch in "-_")[:40]
    name = f"{safe_prefix}-{uuid.uuid4().hex[:10]}.webp"
    with open(os.path.join(directory, name), "wb") as fh:
        fh.write(clean_webp)
    return "/" + "/".join((directory.replace(os.sep, "/"), name))


def save_product_image(item_id: str, data: bytes) -> str:
    """Sanea la imagen de catálogo, la guarda y devuelve la ruta para products.image_path."""
    return write_upload(PRODUCT_UPLOAD_DIR, item_id, sanitize_product_image(data))
