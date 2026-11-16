"""Render the app icon (installer/ArtegraEnhancer.ico) from the brand kit's three-block brandmark.

The white brandmark (ui/qml/creative/assets/brand/SA_BRANDMARK-02.svg) is drawn on the app's ink colour at every
Windows icon size. Run with the project's environment: python tools/make_icon.py. The result is pinned in
asset-hashes.json; rebuild and re-pin it only when the brandmark changes.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ui" / "qml" / "creative" / "assets" / "brand" / "SA_BRANDMARK-02.svg"
OUTPUT = ROOT / "installer" / "ArtegraEnhancer.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 256)
INK = (0x18, 0x18, 0x18, 255)


def render(size: int):
    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(QColor(*INK))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    # The mark fills the middle of the square, as on the brand kit's app tiles.
    QSvgRenderer(str(SOURCE)).render(painter, QRectF(0, 0, size, size))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    return Image.open(io.BytesIO(bytes(data))).convert("RGBA")


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication([])
    images = [render(size) for size in SIZES]
    images[-1].save(OUTPUT, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    del app
    print(OUTPUT.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
