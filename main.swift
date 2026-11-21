import AppKit
import Foundation
import Network

func labProbe(_ rawURL: String, expected: String) -> String? {
    guard let parts = URLComponents(string: rawURL), parts.scheme == "http",
          parts.host == "127.0.0.1", let port = parts.port, (1...65535).contains(port),
          parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil,
          !expected.isEmpty, let url = parts.url else { return nil }
    let process = Process(); let output = Pipe()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/curl")
    process.arguments = ["-q", "-fsS", "--noproxy", "*", "--proto", "=http", "--max-filesize", "1024", "--max-time", "3", "--write-out", "\n%{http_code}", "--", url.absoluteString]
    process.standardOutput = output; process.standardError = FileHandle.nullDevice
    do {
        try process.run()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0, data.suffix(4) == Data("\n200".utf8),
              let d = try JSONSerialization.jsonObject(with: Data(data.dropLast(4))) as? [String: String],
              let route = d["route"], !route.isEmpty else { return "unknown" }
        return route == expected ? "matched" : "mismatch"
    } catch { return "unknown" }
}

private let wagPeriod: TimeInterval = 0.9
private let frameInterval: TimeInterval = 1.0 / 30
private let maximumWagAngle = 16

func wagPose(elapsed: TimeInterval, reduced: Bool) -> Int {
    guard !reduced, elapsed.isFinite, elapsed >= 0 else { return 0 }
    let progress = elapsed.truncatingRemainder(dividingBy: wagPeriod) / wagPeriod
    let angle = Double(maximumWagAngle) * sin(2 * .pi * progress)
    return Int(angle.rounded())
}

func hachiIcon(size: CGFloat, badge: Bool, pose: Int = 0) -> NSImage {
    NSImage(size: NSSize(width: size, height: size), flipped: true) { bounds in
        let s = size / 32
        func p(_ x: CGFloat, _ y: CGFloat) -> NSPoint { NSPoint(x: x * s, y: y * s) }
        func r(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> NSRect { NSRect(x: x*s, y: y*s, width: w*s, height: h*s) }
        let fur = NSColor(srgbRed: 0.96, green: 0.68, blue: 0.37, alpha: 1)
        let cream = NSColor(srgbRed: 1, green: 0.90, blue: 0.73, alpha: 1)
        let dark = NSColor(srgbRed: 0.19, green: 0.13, blue: 0.14, alpha: 1)
        func shape(_ color: NSColor, _ draw: (NSBezierPath) -> Void) {
            let path = NSBezierPath(); draw(path); path.close(); color.setFill(); path.fill()
        }
        func oval(_ rect: NSRect, _ color: NSColor) { color.setFill(); NSBezierPath(ovalIn: rect).fill() }
        func cut(_ draw: () -> Void) {
            guard let cg = NSGraphicsContext.current?.cgContext else { return }
            cg.saveGState(); cg.setBlendMode(.clear); draw(); cg.restoreGState()
        }
        if badge {
            NSColor(srgbRed: 0.13, green: 0.28, blue: 0.27, alpha: 1).setFill()
            NSBezierPath(roundedRect: bounds.insetBy(dx: s, dy: s), xRadius: 7*s, yRadius: 7*s).fill()
        }
        let silhouette = badge ? fur : .black
        // Keep the root and the shape of the tail fixed; rotate the whole curve about the root.
        let angle = CGFloat(pose) * .pi / 180
        let pivot = p(21, 25)
        func tailPoint(_ x: CGFloat, _ y: CGFloat) -> NSPoint {
            let dx = (x - 21) * s, dy = (y - 25) * s
            return NSPoint(x: pivot.x + dx*cos(angle) - dy*sin(angle), y: pivot.y + dx*sin(angle) + dy*cos(angle))
        }
        let tail = NSBezierPath(); tail.lineWidth = (badge ? 3.3 : 4.1)*s; tail.lineCapStyle = .round
        tail.move(to: pivot)
        if badge { tail.curve(to: tailPoint(28, 18), controlPoint1: tailPoint(27, 27), controlPoint2: tailPoint(31, 22)) }
        else { tail.curve(to: tailPoint(28.5, 21.5), controlPoint1: tailPoint(25, 27), controlPoint2: tailPoint(28, 25)) }
        silhouette.setStroke(); tail.stroke()
        if !badge {
            // Profile: blunt snout, one long ear, upright foreleg and seated haunch.
            shape(silhouette) { q in
                q.move(to: p(2.4, 10.8)); q.line(to: p(8, 10.8)); q.line(to: p(9.5, 6.6))
                q.curve(to: p(19.6, 5.7), controlPoint1: p(11, 3.6), controlPoint2: p(17, 3.5))
                q.curve(to: p(21.7, 14.4), controlPoint1: p(22.2, 7.2), controlPoint2: p(22.5, 11.8))
                q.curve(to: p(25, 24.5), controlPoint1: p(22.7, 18.8), controlPoint2: p(25.6, 20.5))
                q.quad(to: p(20.1, 28.3), control: p(24.6, 28.3)); q.line(to: p(16.2, 28.3))
                q.line(to: p(16.2, 23)); q.line(to: p(14.9, 23)); q.line(to: p(13.6, 27.5))
                q.quad(to: p(11.7, 28.3), control: p(13.2, 28.3)); q.line(to: p(8.7, 28.3))
                q.quad(to: p(8.2, 25.8), control: p(7, 27.7)); q.line(to: p(10.5, 24.8)); q.line(to: p(10.8, 16.6))
                q.line(to: p(6.4, 16.6)); q.quad(to: p(2.4, 14), control: p(3.1, 16.2))
            }
            cut {
                oval(r(11.3, 8.4, 2.35, 2.45), dark)
                let ear = NSBezierPath(); ear.lineWidth = 1.65*s; ear.lineCapStyle = .round
                ear.move(to: p(16.2, 7.4)); ear.curve(to: p(17.3, 15.2), controlPoint1: p(15.1, 11), controlPoint2: p(15.4, 14.7))
                ear.quad(to: p(19.8, 12.4), control: p(19.1, 16.1)); ear.stroke()
                let mouth = NSBezierPath(); mouth.lineWidth = 1.05*s; mouth.lineCapStyle = .round
                mouth.move(to: p(3.5, 14)); mouth.quad(to: p(8.7, 14.2), control: p(6, 15)); mouth.stroke()
            }
            silhouette.setFill()
            NSBezierPath(roundedRect: r(6.8, 15.8, 2.05, 2.4), xRadius: 1*s, yRadius: 1*s).fill()
            return true
        }
        oval(r(9, 14, 14, 14), silhouette)
        oval(r(8, 24, 8, 4.5), silhouette); oval(r(16, 24, 8, 4.5), silhouette)
        shape(silhouette) { q in
            q.move(to: p(7, 10)); q.line(to: p(7.8, 3.5)); q.quad(to: p(9.2, 3.4), control: p(8, 2.3)); q.line(to: p(13, 7))
            q.quad(to: p(19, 7), control: p(16, 5.7)); q.line(to: p(23, 3.4)); q.quad(to: p(24.3, 3.5), control: p(24.2, 2.5))
            q.line(to: p(25, 10)); q.quad(to: p(25.7, 13.4), control: p(25.7, 11.5)); q.quad(to: p(16, 20), control: p(25.7, 20));
            q.quad(to: p(6.3, 13.4), control: p(6.3, 20)); q.quad(to: p(7, 10), control: p(6.3, 11.5))
        }
        oval(r(10, 12.6, 12, 6.5), cream); oval(r(12, 20.5, 8, 5.5), cream)
        oval(r(10.8, 10.5, 1.9, 2.3), dark); oval(r(19.3, 10.5, 1.9, 2.3), dark)
        oval(r(13.4, 15, 5.2, 3.5), dark); oval(r(14.4, 13, 3.2, 1.75), dark)
        let tongue = r(14.6, 17.2, 2.8, 3.5)
        NSColor(srgbRed: 0.98, green: 0.41, blue: 0.48, alpha: 1).setFill()
        let radius = 1.35 * s
        NSBezierPath(roundedRect: tongue, xRadius: radius, yRadius: radius).fill()
        return true
    }
}

private extension NSBezierPath {
    func quad(to end: NSPoint, control: NSPoint) {
        let start = currentPoint
        func towards(_ p: NSPoint) -> NSPoint { NSPoint(x: p.x + (control.x-p.x)*2/3, y: p.y + (control.y-p.y)*2/3) }
        curve(to: end, controlPoint1: towards(start), controlPoint2: towards(end))
    }
}

struct Result: Codable {
    let provider: String
    let status: String
    let evidence: String
    let mode = "preflight_only"
    let browserOAuth = "not_covered"
    let mcp = "not_covered"
    enum CodingKeys: String, CodingKey { case provider, status, evidence, mode, browserOAuth, mcp }
    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(provider, forKey: .provider); try c.encode(status, forKey: .status)
        try c.encode(evidence, forKey: .evidence); try c.encode(mode, forKey: .mode)
        try c.encode(browserOAuth, forKey: .browserOAuth); try c.encode(mcp, forKey: .mcp)
    }
    init(provider: String, status: String, evidence: String) {
        self.provider = provider; self.status = status; self.evidence = evidence
    }
}

func check(_ provider: String) -> Result {
    let process = Process()
    process.executableURL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".local/bin/\(provider)-safe")
    process.arguments = ["--check-only"]
    let output = Pipe()
    process.standardOutput = output; process.standardError = output
    do {
        try process.run()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        return Result(provider: provider, status: process.terminationStatus == 0 ? "passed" : "blocked",
                      evidence: String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines))
    } catch {
        return Result(provider: provider, status: "blocked", evidence: "无法运行预检入口：\(error.localizedDescription)")
    }
}

final class MenuAgent: NSObject, NSApplicationDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let pathMonitor = NWPathMonitor()
    let pathStatus = NSMenuItem(title: "系统网络：等待状态", action: nil, keyEquivalent: "")
    let startedAt = ProcessInfo.processInfo.systemUptime
    var wagTimer: Timer?
    var motionObserver: NSObjectProtocol?
    var frames: [Int: NSImage] = [:]
    var currentPose = 0
    func applicationDidFinishLaunching(_ note: Notification) {
        showTail(pose: 0)
        item.button?.toolTip = "Hachi · 观察模式（不拦截）"
        item.button?.setAccessibilityLabel("Hachi 小八")
        motionObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.accessibilityDisplayOptionsDidChangeNotification, object: nil, queue: .main
        ) { [weak self] _ in self?.updateTailAnimation() }
        updateTailAnimation()
        let menu = NSMenu()
        let scope = NSMenuItem(title: "观察模式 · 不拦截运行中流量", action: nil, keyEquivalent: "")
        let uncovered = NSMenuItem(title: "浏览器授权 / MCP：未覆盖", action: nil, keyEquivalent: "")
        menu.addItem(scope); menu.addItem(pathStatus); menu.addItem(uncovered); menu.addItem(.separator())
        for (label, provider) in [("Claude", "claude"), ("Codex", "codex")] {
            let row = NSMenuItem(title: "检查 \(label) 出口", action: #selector(runCheck(_:)), keyEquivalent: "")
            row.representedObject = provider; row.target = self; menu.addItem(row)
        }
        menu.addItem(.separator())
        menu.addItem(withTitle: "退出", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.menu = menu
        pathMonitor.pathUpdateHandler = { [weak self] path in
            let text = path.status == .satisfied ? "可用（不是出口验证）" : "不可用或待建立"
            DispatchQueue.main.async { [weak self] in self?.pathStatus.title = "系统网络：\(text)" }
        }
        pathMonitor.start(queue: DispatchQueue(label: "app.egress.path-observer"))
    }
    private func updateTailAnimation() {
        wagTimer?.invalidate()
        wagTimer = nil
        refreshTail()
        guard !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion else { return }
        let timer = Timer(timeInterval: frameInterval, repeats: true) { [weak self] _ in self?.refreshTail() }
        timer.tolerance = 0.003
        wagTimer = timer
        RunLoop.main.add(timer, forMode: .common)
    }
    private func refreshTail() {
        let elapsed = ProcessInfo.processInfo.systemUptime - startedAt
        let reduced = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        let pose = wagPose(elapsed: elapsed, reduced: reduced)
        if pose != currentPose { showTail(pose: pose) }

    }
    private func showTail(pose: Int) {
        if frames[pose] == nil {
            let icon = hachiIcon(size: 19, badge: false, pose: pose)
            icon.isTemplate = true; frames[pose] = icon
        }
        currentPose = pose; item.button?.image = frames[pose]
    }
    func applicationWillTerminate(_ notification: Notification) {
        wagTimer?.invalidate()
        if let observer = motionObserver { NSWorkspace.shared.notificationCenter.removeObserver(observer) }
        pathMonitor.cancel()
    }
    @objc func runCheck(_ sender: NSMenuItem) {
        guard let provider = sender.representedObject as? String else { return }
        sender.isEnabled = false
        item.button?.toolTip = "Hachi · 预检中"
        DispatchQueue.global(qos: .userInitiated).async {
            let result = check(provider)
            DispatchQueue.main.async {
                sender.isEnabled = true
                self.item.button?.toolTip = "Hachi · 观察模式（不拦截）"
                let alert = NSAlert()
                alert.messageText = "\(provider.capitalized)：\(result.status == "passed" ? "预检通过" : "预检未通过")"
                alert.informativeText = result.evidence + "\n\n未启动客户端。浏览器 OAuth、MCP 和运行中拦截未覆盖。"
                NSApp.activate(ignoringOtherApps: true)
                alert.runModal()
            }
        }
    }
}

let args = Array(CommandLine.arguments.dropFirst())
if !args.isEmpty {
    if args.count == 3, args[0] == "--lab-probe" {
        guard let status = labProbe(args[1], expected: args[2]) else { exit(2) }
        let data = try JSONEncoder().encode(["status": status, "mode": "synthetic_probe_only"])
        print(String(decoding: data, as: UTF8.self)); exit(0)
    }
    if args.count == 3, args[0] == "--wag-frame", let elapsed = Double(args[1]), let reduced = Bool(args[2]) {
        let data = try JSONEncoder().encode(["pose": wagPose(elapsed: elapsed, reduced: reduced)])
        print(String(decoding: data, as: UTF8.self)); exit(0)
    }
    if (args.count == 3 || args.count == 4), ["--draw-icon", "--draw-menu-icon"].contains(args[0]),
       let size = Int(args[1]), (16...1024).contains(size),
       let pose = args.count == 4 ? Int(args[3]) : 0, (-maximumWagAngle...maximumWagAngle).contains(pose),
       let tiff = hachiIcon(size: CGFloat(size), badge: args[0] == "--draw-icon", pose: pose).tiffRepresentation,
       let bitmap = NSBitmapImageRep(data: tiff), let png = bitmap.representation(using: .png, properties: [:]) {
        try png.write(to: URL(fileURLWithPath: args[2])); exit(0)
    }
    guard args.count == 2, args[0] == "--check", ["claude", "codex"].contains(args[1]) else { exit(2) }
    let result = check(args[1]); let data = try JSONEncoder().encode(result)
    print(String(decoding: data, as: UTF8.self)); exit(0)
}
let app = NSApplication.shared
let delegate = MenuAgent()
app.setActivationPolicy(.accessory)
app.delegate = delegate
app.run()
