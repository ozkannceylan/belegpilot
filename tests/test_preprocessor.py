"""Preprocessor tests."""

import io

import pytest
from PIL import Image

from app.core.preprocessor import ImagePreprocessor


@pytest.fixture
def preprocessor():
    return ImagePreprocessor()


@pytest.mark.asyncio
async def test_preprocess_jpeg(preprocessor, sample_receipt_bytes):
    jpeg_bytes, b64 = await preprocessor.preprocess(sample_receipt_bytes, "image/jpeg")
    assert len(jpeg_bytes) > 0
    assert len(b64) > 0


@pytest.mark.asyncio
async def test_preprocess_rejects_unsupported(preprocessor):
    with pytest.raises(ValueError, match="Unsupported"):
        await preprocessor.preprocess(b"data", "text/plain")


@pytest.mark.asyncio
async def test_preprocess_png(preprocessor):
    """PNG preprocessing produces output."""
    img = Image.new("RGB", (200, 300), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    jpeg_bytes, b64 = await preprocessor.preprocess(buf.getvalue(), "image/png")
    assert len(jpeg_bytes) > 0
    assert len(b64) > 0


@pytest.mark.asyncio
async def test_preprocess_small_image(preprocessor):
    """Very small image (1x1) should not crash."""
    img = Image.new("RGB", (1, 1), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_bytes, b64 = await preprocessor.preprocess(buf.getvalue(), "image/jpeg")
    assert len(jpeg_bytes) > 0


@pytest.mark.asyncio
async def test_preprocess_large_image_resized(preprocessor):
    """Large image should be resized to MAX_DIMENSION."""
    img = Image.new("RGB", (4000, 6000), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_bytes, b64 = await preprocessor.preprocess(buf.getvalue(), "image/jpeg")
    assert len(jpeg_bytes) > 0
    # Verify the output image is resized
    result_img = Image.open(io.BytesIO(jpeg_bytes))
    assert max(result_img.size) <= preprocessor.MAX_DIMENSION + 1  # +1 for rounding
