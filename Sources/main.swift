import AppKit
import CoreGraphics

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let interval: TimeInterval = 13 * 60
    private var statusItem: NSStatusItem!
    private let toggleItem = NSMenuItem()
    private let countdownItem = NSMenuItem()
    private let resultItem = NSMenuItem()
    private var timer: Timer?
    private var nextMove = Date().addingTimeInterval(13 * 60)
    private var running = true
    private var animationTimer: Timer?
    private var displayKeeper: Process?

    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        let menu = NSMenu()
        menu.autoenablesItems = false
        let title = NSMenuItem(title: "IamHere · после 13 минут бездействия", action: nil, keyEquivalent: "")
        title.isEnabled = false
        menu.addItem(title)
        countdownItem.isEnabled = false
        menu.addItem(countdownItem)
        resultItem.title = "Плавное движение · экран не засыпает"
        resultItem.isEnabled = false
        menu.addItem(resultItem)
        menu.addItem(.separator())
        toggleItem.target = self
        toggleItem.action = #selector(toggle)
        menu.addItem(toggleItem)
        let test = NSMenuItem(title: "Двинуть мышь сейчас", action: #selector(testMove), keyEquivalent: "")
        test.target = self
        menu.addItem(test)
        menu.addItem(.separator())
        let quit = NSMenuItem(title: "Выйти из IamHere", action: #selector(quitApp), keyEquivalent: "q")
        quit.target = self
        menu.addItem(quit)
        statusItem.menu = menu

        // A common-mode timer also runs while the status menu is open.
        let timer = Timer(timeInterval: 1, target: self, selector: #selector(tick), userInfo: nil, repeats: true)
        timer.tolerance = 0.2
        RunLoop.main.add(timer, forMode: .common)
        self.timer = timer
        NSWorkspace.shared.notificationCenter.addObserver(self, selector: #selector(didWake), name: NSWorkspace.didWakeNotification, object: nil)
        keepDisplayAwake()
        refreshMenu()
    }

    @objc private func tick() {
        if running && Date() >= nextMove && idleTime >= interval && animationTimer == nil {
            moveCursor()
            nextMove = Date().addingTimeInterval(interval)
        }
        refreshMenu()
    }

    @objc private func toggle() {
        running.toggle()
        if running {
            nextMove = Date().addingTimeInterval(interval)
            keepDisplayAwake()
        } else {
            stopAnimation()
            releaseDisplay()
        }
        refreshMenu()
    }

    @objc private func testMove() {
        moveCursor()
        refreshMenu()
    }

    @objc private func didWake() {
        // Start a fresh interval after sleep, without replaying missed moves.
        nextMove = Date().addingTimeInterval(interval)
        refreshMenu()
    }

    private var idleTime: TimeInterval {
        CGEventSource.secondsSinceLastEventType(.combinedSessionState, eventType: CGEventType(rawValue: UInt32.max)!)
    }

    private func keepDisplayAwake() {
        guard displayKeeper?.isRunning != true else { return }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/caffeinate")
        process.arguments = ["-d", "-w", String(ProcessInfo.processInfo.processIdentifier)]
        do {
            try process.run()
            displayKeeper = process
        } catch {
            resultItem.title = "Не удалось удержать экран от сна"
        }
    }

    private func releaseDisplay() {
        if let process = displayKeeper, process.isRunning { process.terminate() }
        displayKeeper = nil
    }

    private func stopAnimation() {
        animationTimer?.invalidate()
        animationTimer = nil
    }

    private func moveCursor() {
        stopAnimation()
        guard let current = CGEvent(source: nil)?.location else {
            resultItem.title = "Не удалось получить положение курсора"
            return
        }
        var displays = [CGDirectDisplayID](repeating: 0, count: 32)
        var count: UInt32 = 0
        guard CGGetActiveDisplayList(UInt32(displays.count), &displays, &count) == .success,
              let display = displays.prefix(Int(count)).first(where: { CGDisplayBounds($0).contains(current) }) else {
            resultItem.title = "Не удалось определить экран"
            return
        }
        let bounds = CGDisplayBounds(display)
        let points = [current] + (0..<3).map { _ in
            CGPoint(
                x: min(bounds.maxX - 1, max(bounds.minX, current.x + CGFloat.random(in: -45...45))),
                y: min(bounds.maxY - 1, max(bounds.minY, current.y + CGFloat.random(in: -30...30)))
            )
        } + [current]
        let segmentDuration = Double.random(in: 0.22...0.34)
        let started = ProcessInfo.processInfo.systemUptime
        var expected = current
        let timer = Timer(timeInterval: 1.0 / 60, repeats: true) { [weak self] _ in
            guard let self else { return }
            // Stop if the pointer changed externally or new input arrived since the animation began.
            let elapsed = ProcessInfo.processInfo.systemUptime - started
            guard let actual = CGEvent(source: nil)?.location,
                  hypot(actual.x - expected.x, actual.y - expected.y) < 2,
                  self.idleTime + 0.02 >= elapsed else {
                self.stopAnimation()
                self.resultItem.title = "Движение отменено: пользователь активен"
                return
            }
            let progress = elapsed / segmentDuration
            let segment = min(Int(progress), points.count - 2)
            let fraction = min(1, progress - Double(segment))
            let eased = fraction * fraction * (3 - 2 * fraction)
            let from = points[segment]
            let to = points[segment + 1]
            let target = CGPoint(x: from.x + (to.x - from.x) * eased, y: from.y + (to.y - from.y) * eased)
            let result = CGWarpMouseCursorPosition(target)
            guard result == .success else {
                self.stopAnimation()
                self.resultItem.title = "Не удалось сдвинуть курсор (\(result.rawValue))"
                return
            }
            expected = target
            if progress >= Double(points.count - 1) {
                self.stopAnimation()
                let time = DateFormatter.localizedString(from: Date(), dateStyle: .none, timeStyle: .medium)
                self.resultItem.title = "Последнее движение: \(time)"
            }
        }
        animationTimer = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    private func refreshMenu() {
        statusItem.button?.image = NSImage(systemSymbolName: running ? "computermouse.fill" : "pause.circle", accessibilityDescription: "IamHere")
        statusItem.button?.toolTip = running ? "IamHere: таймер включён" : "IamHere: пауза"
        toggleItem.title = running ? "Приостановить" : "Продолжить"
        if running {
            let seconds = max(0, Int(ceil(max(nextMove.timeIntervalSinceNow, interval - idleTime))))
            countdownItem.title = String(format: "Следующее движение через %02d:%02d", seconds / 60, seconds % 60)
        } else {
            countdownItem.title = "Таймер на паузе"
        }
    }

    @objc private func quitApp() {
        NSApplication.shared.terminate(nil)
    }

    func applicationWillTerminate(_ notification: Notification) {
        timer?.invalidate()
        stopAnimation()
        releaseDisplay()
        NSWorkspace.shared.notificationCenter.removeObserver(self)
    }
}

let application = NSApplication.shared
let delegate = AppDelegate()
application.delegate = delegate
application.setActivationPolicy(.accessory)
application.run()
