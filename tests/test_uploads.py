import io

from PIL import Image
from werkzeug.datastructures import FileStorage

from utils.helpers import validate_image, validate_document

IMAGE_EXTS = {"jpg", "jpeg", "png", "webp"}
DOC_EXTS = {"pdf", "jpg", "jpeg", "png"}
MAX_SIZE = 5 * 1024 * 1024


def _real_png(filename="photo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    buf.seek(0)
    return FileStorage(stream=buf, filename=filename, content_type="image/png")


def _fake_pdf(filename="invoice.pdf"):
    return FileStorage(stream=io.BytesIO(b"%PDF-1.4\n%fake pdf content"), filename=filename)


def test_accepts_a_real_image():
    ok, error = validate_image(_real_png(), IMAGE_EXTS, MAX_SIZE)
    assert ok is True
    assert error is None


def test_rejects_disallowed_extension():
    file = FileStorage(stream=io.BytesIO(b"hello"), filename="notes.txt")
    ok, error = validate_image(file, IMAGE_EXTS, MAX_SIZE)
    assert ok is False
    assert "type" in error.lower()


def test_rejects_content_that_doesnt_match_a_renamed_extension():
    """A .png that isn't actually image bytes must fail content
    verification, not just the extension check -- this is the whole
    point of validating content, not trusting the filename."""
    fake_image = FileStorage(stream=io.BytesIO(b"not really an image"), filename="fake.png")
    ok, error = validate_image(fake_image, IMAGE_EXTS, MAX_SIZE)
    assert ok is False


def test_rejects_empty_file():
    file = FileStorage(stream=io.BytesIO(b""), filename="empty.png")
    ok, error = validate_image(file, IMAGE_EXTS, MAX_SIZE)
    assert ok is False
    assert "empty" in error.lower()


def test_rejects_oversized_file():
    big = io.BytesIO(b"0" * (MAX_SIZE + 1))
    file = FileStorage(stream=big, filename="big.png")
    ok, error = validate_image(file, IMAGE_EXTS, MAX_SIZE)
    assert ok is False
    assert "large" in error.lower()


def test_accepts_a_real_pdf_document():
    ok, error = validate_document(_fake_pdf(), DOC_EXTS, MAX_SIZE)
    assert ok is True
    assert error is None


def test_rejects_pdf_without_magic_bytes():
    fake_pdf = FileStorage(stream=io.BytesIO(b"this is not a pdf"), filename="invoice.pdf")
    ok, error = validate_document(fake_pdf, DOC_EXTS, MAX_SIZE)
    assert ok is False
    assert "pdf" in error.lower()


def test_document_accepts_a_real_image_too():
    ok, error = validate_document(_real_png(filename="receipt.png"), DOC_EXTS, MAX_SIZE)
    assert ok is True
    assert error is None
