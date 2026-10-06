import unittest

from iamhere import INTERVAL, Point, Rect, Size, animate, due


class FakeMac:
    def __init__(self, interrupt=None):
        self.now = 0.0
        self.point = Point(1, 1)
        self.moves = []
        self.interrupt = interrupt

    def position(self):
        if self.interrupt == "mouse" and self.now > 0.1:
            return Point(300, 300)
        return self.point

    def bounds(self, _point):
        return Rect(Point(0, 0), Size(800, 600))

    def idle(self):
        return 0 if self.interrupt == "keyboard" and self.now > 0.1 else 900

    def move(self, point):
        self.moves.append(point)
        self.point = point

    def sleep(self, seconds):
        self.now += seconds

    def run(self):
        return animate(self, clock=lambda: self.now, sleep=self.sleep)


class Tests(unittest.TestCase):
    def test_requires_full_idle_interval_and_schedule(self):
        self.assertFalse(due(INTERVAL - 1, 2000, 1000))
        self.assertFalse(due(INTERVAL, 999, 1000))
        self.assertTrue(due(INTERVAL, 1000, 1000))

    def test_returns_to_origin_and_stays_on_screen(self):
        mac = FakeMac()
        self.assertTrue(mac.run())
        self.assertAlmostEqual(mac.point.x, 1)
        self.assertAlmostEqual(mac.point.y, 1)
        self.assertTrue(all(0 <= p.x < 800 and 0 <= p.y < 600 for p in mac.moves))

    def test_mouse_interrupts_without_return(self):
        mac = FakeMac("mouse")
        self.assertFalse(mac.run())
        self.assertLess(mac.now, 0.2)
        self.assertEqual(mac.position().x, 300)

    def test_keyboard_interrupts(self):
        mac = FakeMac("keyboard")
        self.assertFalse(mac.run())
        self.assertLess(mac.now, 0.2)


if __name__ == "__main__":
    unittest.main()
