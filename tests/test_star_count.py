"""Star counting must ignore bright card art and accept pale-blue Ld stars."""
import unittest

try:
    import cv2  # noqa: F401
    from PIL import Image, ImageDraw
    HAVE_VISION = True
except ImportError:
    HAVE_VISION = False

from urban_rivals.vision import CanvasReader, RecognitionError


def board(lit, colour=(250, 190, 20), art=True, empty=1):
    image = Image.new("RGB", (1318, 744), (60, 120, 130))
    draw = ImageDraw.Draw(image)
    x, y = int(.406 * 1318), int(.335 * 744)
    if art:  # tall yellow card art right beside the bar
        draw.rectangle((x - 66, y - 18, x - 58, y + 6), fill=(250, 220, 40))
    draw.rounded_rectangle((x - 45, y - 9, x + 45, y + 9), 8, fill=(30, 30, 32))
    start = x - 12 * (lit + empty) // 2
    for i in range(lit + empty):
        cx = start + 12 * i + 5
        fill = colour if i < lit else (70, 70, 72)
        draw.polygon([(cx, y - 5), (cx + 5, y + 4), (cx - 5, y + 4)], fill=fill)
    return image


@unittest.skipUnless(HAVE_VISION, "vision extras not installed")
class StarCountTests(unittest.TestCase):
    def test_gold_stars_beside_bright_art(self):
        for lit in (1, 2, 3, 4, 5):
            with self.subTest(lit=lit):
                self.assertEqual(CanvasReader.stars(CanvasReader.__new__(CanvasReader),
                                                    board(lit), .406, .335), lit)

    def test_pale_blue_limited_star(self):
        self.assertEqual(CanvasReader.stars(CanvasReader.__new__(CanvasReader),
                                            board(1, (170, 225, 250)), .406, .335), 1)

    def test_no_lit_star_raises(self):
        with self.assertRaises(RecognitionError):
            CanvasReader.stars(CanvasReader.__new__(CanvasReader), board(0, empty=3), .406, .335)


if __name__ == "__main__":
    unittest.main()
