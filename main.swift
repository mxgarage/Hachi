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

func sailShield(size: CGFloat, badge: Bool) -> NSImage {
    NSImage(size: NSSize(width: size, height: size), flipped: true) { bounds in
        let scale = size / 32
        func point(_ x: CGFloat, _ y: CGFloat) -> NSPoint { NSPoint(x: x * scale, y: y * scale) }
        if badge {
            NSColor(srgbRed: 0.05, green: 0.19, blue: 0.22, alpha: 1).setFill()
            NSBezierPath(roundedRect: bounds.insetBy(dx: 1.5 * scale, dy: 1.5 * scale), xRadius: 7 * scale, yRadius: 7 * scale).fill()
            NSColor(srgbRed: 0.55, green: 0.94, blue: 0.83, alpha: 1).set()
        } else { NSColor.black.set() }
        let shield = NSBezierPath(); shield.lineWidth = 2.1 * scale
        shield.move(to: point(16, 3)); shield.line(to: point(27, 7)); shield.line(to: point(26, 17))
        shield.curve(to: point(16, 29), controlPoint1: point(25, 22), controlPoint2: point(21, 26))
        shield.curve(to: point(6, 17), controlPoint1: point(11, 26), controlPoint2: point(7, 22))
        shield.line(to: point(5, 7)); shield.close(); shield.stroke()
        let sail = NSBezierPath(); sail.move(to: point(16, 8)); sail.line(to: point(22, 18)); sail.line(to: point(16, 18)); sail.close(); sail.fill()
        let jib = NSBezierPath(); jib.move(to: point(14.5, 12)); jib.line(to: point(10, 18)); jib.line(to: point(14.5, 18)); jib.close(); jib.fill()
        let hull = NSBezierPath(); hull.move(to: point(10, 20)); hull.line(to: point(22, 20)); hull.line(to: point(19, 23)); hull.line(to: point(13, 23)); hull.close(); hull.fill()
        return true
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
    func applicationDidFinishLaunching(_ note: Notification) {
        let icon = sailShield(size: 19, badge: false); icon.isTemplate = true
        item.button?.image = icon
        item.button?.toolTip = "AI 出口 · 观察模式（不拦截）"
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
    func applicationWillTerminate(_ notification: Notification) { pathMonitor.cancel() }
    @objc func runCheck(_ sender: NSMenuItem) {
        guard let provider = sender.representedObject as? String else { return }
        sender.isEnabled = false
        item.button?.toolTip = "AI 出口 · 预检中"
        DispatchQueue.global(qos: .userInitiated).async {
            let result = check(provider)
            DispatchQueue.main.async {
                sender.isEnabled = true
                self.item.button?.toolTip = "AI 出口 · 观察模式（不拦截）"
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
    if args.count == 3, args[0] == "--draw-icon", let size = Int(args[1]), (16...1024).contains(size),
       let tiff = sailShield(size: CGFloat(size), badge: true).tiffRepresentation,
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
