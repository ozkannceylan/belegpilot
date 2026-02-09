"""Image preprocessing with OpenCV to improve extraction quality."""

import base64
import io

import cv2
import numpy as np
import structlog
from PIL import Image

logger = structlog.get_logger()


class ImagePreprocessor:
    """Preprocesses receipt/invoice images for better extraction."""

    SUPPORTED_TYPES = {"image/jpeg", "image/png", "application/pdf"}
    MAX_DIMENSION = 2048  # Resize if larger

    async def preprocess(
        self, file_bytes: bytes, content_type: str
    ) -> tuple[bytes, str]:
        """Preprocess image and return (jpeg_bytes, base64_string).

        Args:
            file_bytes: Raw uploaded file bytes
            content_type: MIME type of the file

        Returns:
            Tuple of (processed JPEG bytes, base64-encoded string)

        Raises:
            ValueError: If content type is not supported
        """
        if content_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type: {content_type}")

        # Convert PDF to image
        if content_type == "application/pdf":
            img = self._pdf_to_image(file_bytes)
        else:
            img = self._bytes_to_cv2(file_bytes)

        # Preprocessing pipeline
        img = self._resize_if_needed(img)
        img = self._to_grayscale(img)
        img = self._denoise(img)
        img = self._enhance_contrast(img)
        img = self._deskew(img)

        # Encode as JPEG
        jpeg_bytes = self._cv2_to_jpeg_bytes(img)
        b64_string = base64.b64encode(jpeg_bytes).decode("utf-8")

        logger.info(
            "Image preprocessed",
            original_size=len(file_bytes),
            processed_size=len(jpeg_bytes),
            content_type=content_type,
        )

        return jpeg_bytes, b64_string

    def _bytes_to_cv2(self, file_bytes: bytes) -> np.ndarray:
        """Convert raw bytes to OpenCV image array."""
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image")
        return img

    def _pdf_to_image(self, file_bytes: bytes) -> np.ndarray:
        """Extract first page of PDF as image.

        Uses Pillow to open PDF first page. For complex PDFs,
        consider pdf2image (poppler) but Pillow is lighter.
        """
        # Pillow can read simple PDFs; for complex ones, use pdf2image
        try:
            pil_image = Image.open(io.BytesIO(file_bytes))
            pil_image = pil_image.convert("RGB")
            return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        except Exception as e:
            raise ValueError(f"Failed to process PDF: {e}") from e

    def _resize_if_needed(self, img: np.ndarray) -> np.ndarray:
        """Resize image if any dimension exceeds MAX_DIMENSION."""
        h, w = img.shape[:2]
        if max(h, w) > self.MAX_DIMENSION:
            scale = self.MAX_DIMENSION / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.debug("Image resized", original=(w, h), new=(new_w, new_h))
        return img

    def _to_grayscale(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _denoise(self, img: np.ndarray) -> np.ndarray:
        return cv2.fastNlMeansDenoising(img, h=10)

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(img)

    def _deskew(self, img: np.ndarray) -> np.ndarray:
        """Deskew image by detecting text angle."""
        coords = np.column_stack(np.where(img > 0))
        if len(coords) < 100:
            return img
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.5:  # Skip if nearly straight
            return img
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            img, rotation_matrix, (w, h),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
        )

    def _cv2_to_jpeg_bytes(self, img: np.ndarray) -> bytes:
        """Convert OpenCV image to JPEG bytes."""
        # If grayscale, convert back to BGR for JPEG encoding
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        success, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            raise ValueError("Failed to encode image as JPEG")
        return buffer.tobytes()
