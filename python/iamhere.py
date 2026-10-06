#!/usr/bin/env python3
"""macOS mouse movement after 13 idle minutes; Python standard library only."""

import argparse
import ctypes as C
import math
import os
import random
import signal
import subprocess
import sys
import time

INTERVAL = 13 * 60


class Point(C.Structure):
    _fields_ = [("x", C.c_double), ("y", C.c_double)]


class Size(C.Structure):
    _fields_ = [("width", C.c_double), ("height", C.c_double)]


class Rect(C.Structure):
    _fields_ = [("origin", Point), ("size", Size)]


class Mac:
    def __init__(self):
        self.cg = C.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        self.cf = C.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        signatures = {
            "CGEventSourceSecondsSinceLastEventType": ([C.c_int32, C.c_uint32], C.c_double),
            "CGEventSourceButtonState": ([C.c_int32, C.c_uint32], C.c_bool),
            "CGEventSourceKeyState": ([C.c_int32, C.c_uint16], C.c_bool),
            "CGEventCreate": ([C.c_void_p], C.c_void_p),
            "CGEventGetLocation": ([C.c_void_p], Point),
            "CGWarpMouseCursorPosition": ([Point], C.c_int32),
            "CGGetActiveDisplayList": ([C.c_uint32, C.POINTER(C.c_uint32), C.POINTER(C.c_uint32)], C.c_int32),
            "CGDisplayBounds": ([C.c_uint32], Rect),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.cg, name)
            function.argtypes = args
            function.restype = result
        self.cf.CFRelease.argtypes = [C.c_void_p]
        self.cf.CFRelease.restype = None

    def idle(self):
        # Combined session includes keyboard, pointer, scrolling and tablet input.
        if any(self.cg.CGEventSourceButtonState(0, button) for button in range(32)):
            return 0.0
        if any(self.cg.CGEventSourceKeyState(0, key) for key in range(128)):
            return 0.0
        value = self.cg.CGEventSourceSecondsSinceLastEventType(0, 0xFFFFFFFF)
        if not math.isfinite(value) or value < 0:
            raise RuntimeError("macOS не вернула время бездействия")
        return value

    def position(self):
        event = self.cg.CGEventCreate(None)
        if not event:
            raise RuntimeError("Нет доступа к положению курсора")
        try:
            return self.cg.CGEventGetLocation(event)
        finally:
            self.cf.CFRelease(event)

    def bounds(self, point):
        displays = (C.c_uint32 * 32)()
        count = C.c_uint32()
        if self.cg.CGGetActiveDisplayList(32, displays, C.byref(count)) != 0:
            raise RuntimeError("Не удалось получить список экранов")
        for display in displays[:count.value]:
            rect = self.cg.CGDisplayBounds(display)
            if (rect.origin.x <= point.x < rect.origin.x + rect.size.width
                    and rect.origin.y <= point.y < rect.origin.y + rect.size.height):
                return rect
        raise RuntimeError("Экран с курсором не найден")

    def move(self, point):
        error = self.cg.CGWarpMouseCursorPosition(point)
        if error:
            raise RuntimeError("macOS отклонила движение курсора (код {})".format(error))


def animate(mac, clock=time.monotonic, sleep=time.sleep):
    origin = mac.position()
    rect = mac.bounds(origin)
    points = [origin]
    for _ in range(3):
        points.append(Point(
            min(rect.origin.x + rect.size.width - 1, max(rect.origin.x, origin.x + random.uniform(-45, 45))),
            min(rect.origin.y + rect.size.height - 1, max(rect.origin.y, origin.y + random.uniform(-30, 30))),
        ))
    points.append(origin)
    expected = origin
    started = clock()
    duration = random.uniform(0.22, 0.34)
    while True:
        elapsed = clock() - started
        actual = mac.position()
        # A warp generates no input event; any fresh input cancels the gesture.
        if (math.hypot(actual.x - expected.x, actual.y - expected.y) >= 2
                or mac.idle() <= elapsed + 0.02):
            return False
        progress = elapsed / duration
        segment = min(int(progress), len(points) - 2)
        fraction = min(1.0, progress - segment)
        smooth = fraction * fraction * (3 - 2 * fraction)
        a, b = points[segment:segment + 2]
        expected = Point(a.x + (b.x - a.x) * smooth, a.y + (b.y - a.y) * smooth)
        mac.move(expected)
        if progress >= len(points) - 1:
            return True
        sleep(1 / 60)


def due(idle, now, next_move):
    return idle >= INTERVAL and now >= next_move


def stop(_signal, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description="Движение мыши после 13 минут без ввода, без установки библиотек.")
    parser.add_argument("--check", action="store_true", help="проверить доступ к macOS без движения и удержания экрана")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Этот скрипт предназначен только для macOS")
    keeper = None
    try:
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGHUP, stop)
        mac = Mac()
        point = mac.position()
        mac.bounds(point)
        idle = mac.idle()
        if args.check:
            print("Доступ к macOS работает. Без ввода: {:.1f} с. Курсор: {:.0f}, {:.0f}.".format(idle, point.x, point.y))
            return 0
        keeper = subprocess.Popen(["/usr/bin/caffeinate", "-d", "-w", str(os.getpid())])
        print("IamHere: экран не засыпает. Движение после 13 минут без ввода. Остановка: Ctrl+C.", flush=True)
        next_move = time.monotonic() + INTERVAL
        previous_wall = time.time()
        while True:
            if keeper.poll() is not None:
                raise RuntimeError("Системная утилита caffeinate завершилась")
            wall = time.time()
            now = time.monotonic()
            # Start a fresh interval after sleep or a long suspension.
            if wall - previous_wall > 5 or wall < previous_wall:
                next_move = now + INTERVAL
            previous_wall = wall
            if due(mac.idle(), now, next_move):
                completed = animate(mac)
                print(time.strftime("%H:%M:%S"), "Курсор подвинут." if completed else "Отменено: пользователь активен.", flush=True)
                next_move = time.monotonic() + INTERVAL
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nIamHere остановлен.")
        return 0
    except (OSError, RuntimeError) as error:
        print("Ошибка: {}".format(error), file=sys.stderr)
        return 1
    finally:
        if keeper is not None and keeper.poll() is None:
            keeper.terminate()
            try:
                keeper.wait(timeout=3)
            except subprocess.TimeoutExpired:
                keeper.kill()
                keeper.wait()


if __name__ == "__main__":
    sys.exit(main())
