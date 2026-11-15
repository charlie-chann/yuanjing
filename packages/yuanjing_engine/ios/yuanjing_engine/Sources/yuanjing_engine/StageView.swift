import Flutter
import MetalKit
import UIKit

/// 七个心愿分类加五种卡点释放方式，各对应着色器里的一场戏。编号要和 shaders/stage.metal 一致。
enum StageScene: Int {
  case wealth = 0, career, looks, health, mood, life, pet
  case relPool, relBalloon, relArrow, relPotion, relDeep

  /// 卡点释放的五场：时间轴按进度写，时长由外面定（轻量和深度两档共用画面）。
  var isRelease: Bool { rawValue >= StageScene.relPool.rawValue }

  static func named(_ name: String) -> StageScene {
    switch name {
    case "career": return .career
    case "looks": return .looks
    case "health": return .health
    case "mood": return .mood
    case "life": return .life
    case "pet": return .pet
    case "release_pool": return .relPool
    case "release_balloon": return .relBalloon
    case "release_arrow": return .relArrow
    case "release_potion": return .relPotion
    case "release_deep": return .relDeep
    default: return .wealth
    }
  }

  /// 仪式时长（秒）。许愿的七场，着色器里的时间轴按这个数写死了节点，改时长要同步改着色器；
  /// 释放的五场这里只是默认值，播放时可以另外指定。
  var duration: Float {
    switch self {
    case .wealth: return 9.2
    case .career: return 9.0
    case .looks: return 8.5
    case .health: return 9.0
    case .mood: return 9.0
    case .life: return 10.0
    case .pet: return 8.0
    case .relPool, .relBalloon, .relArrow, .relPotion, .relDeep: return 30.0
    }
  }

  /// 光线步进的场景按 1.5 倍渲染，其余按 2 倍。
  var renderScale: CGFloat {
    switch self {
    case .wealth, .relPool, .relArrow, .relDeep: return 1.5
    default: return 2.0
    }
  }

  /// 触感提示点：(秒, 样式)，和画面里的落水、呼吸、日出对齐。释放的五场按进度写，再乘上时长。
  func cues(_ duration: Float) -> [(Float, String)] {
    func at(_ list: [(Float, String)]) -> [(Float, String)] { list.map { ($0.0 * duration, $0.1) } }
    switch self {
    case .wealth:
      var list: [(Float, String)] = [(1.3, "tick"), (1.85, "drop"), (6.0, "bloom"), (7.62, "tick")]
      for i in 0..<8 { list.append((StageScene.rainStart(i) + 1.123, "coin")) }
      return list.sorted { $0.0 < $1.0 }
    case .career: return [(0.5, "rise"), (3.3, "drop"), (5.0, "bloom")]
    case .looks: return [(1.2, "tick"), (1.6, "breath"), (2.6, "breath"), (3.6, "breath")]
    case .health: return [(1.7, "breath"), (3.9, "breath"), (6.1, "breath")]
    case .mood: return [(2.2, "drop"), (6.6, "tick")]
    case .life: return [(0.6, "tick"), (1.9, "rise"), (5.0, "bloom")]
    case .pet: return (0..<9).map { (0.5 + Float($0) * 0.42, "tick") } + [(4.9, "drop"), (5.4, "bloom")]
    case .relPool: return at([(0.04, "tick"), (0.78, "bloom")])
    case .relBalloon: return at([(0.14, "rise"), (0.90, "tick")])
    case .relArrow: return at([(0.115, "tick"), (0.20, "drop"), (0.215, "bloom")])
    case .relPotion: return at([(0.06, "tick"), (0.29, "drop"), (0.36, "drop"), (0.43, "drop"), (0.50, "drop"), (0.57, "drop"), (0.75, "bloom")])
    case .relDeep: return at([(0.04, "tick"), (0.80, "bloom")])
    }
  }

  var name: String {
    switch self {
    case .wealth: return "wealth"
    case .career: return "career"
    case .looks: return "looks"
    case .health: return "health"
    case .mood: return "mood"
    case .life: return "life"
    case .pet: return "pet"
    case .relPool: return "rel_pool"
    case .relBalloon: return "rel_balloon"
    case .relArrow: return "rel_arrow"
    case .relPotion: return "rel_potion"
    case .relDeep: return "rel_deep"
    }
  }

  /// 音效提示点：(秒, 音效名, 音量)，和画面里的落水、登顶、呼吸对齐。每一场都用同一个完成音收尾。
  func sounds(_ duration: Float) -> [(Float, String, Float)] {
    func at(_ list: [(Float, String, Float)]) -> [(Float, String, Float)] { list.map { ($0.0 * duration, $0.1, $0.2) } }
    var list: [(Float, String, Float)]
    switch self {
    case .wealth:
      list = [(1.25, "whoosh", 0.7), (1.85, "drop", 1), (3.4, "bloom", 0.8), (7.62, "chime", 0.7)]
      for i in 0..<8 { list.append((StageScene.rainStart(i) + 1.123, "coin_\(i % 3 + 1)", 0.8)) }
    case .career:
      list = [(0.5, "rise", 0.8), (3.3, "chime_hi", 0.9), (3.4, "sparkle", 0.7), (4.4, "bloom", 0.9)]
    case .looks:
      list = [(0.3, "whoosh", 0.5), (1.6, "chime", 0.7), (2.2, "sparkle", 0.6), (2.6, "chime_hi", 0.6), (3.6, "chime", 0.5)]
    case .health:
      list = [(0.6, "breath_in", 1), (1.7, "breath_out", 1), (1.7, "bowl", 0.8), (2.8, "breath_in", 1), (3.9, "breath_out", 1),
              (3.9, "chime", 0.5), (5.0, "breath_in", 1), (6.1, "breath_out", 1), (6.1, "chime_hi", 0.5)]
    case .mood:
      list = [(1.1, "whoosh", 0.4), (2.2, "drop", 1), (3.4, "sparkle", 0.5), (6.6, "star", 1)]
    case .life:
      list = [(0.6, "light", 1), (1.9, "rise", 0.7), (3.0, "sparkle", 0.6), (4.4, "sparkle", 0.6), (5.2, "bloom", 0.8)]
    case .pet:
      list = (0..<9).map { (0.5 + Float($0) * 0.42, "step_\($0 + 1)", 0.8) } + [(4.9, "chime_hi", 0.8), (4.95, "sparkle", 0.7), (5.3, "heart", 1)]
    case .relPool:
      list = at([(0.04, "whoosh", 0.4), (0.05, "drop", 0.6), (0.42, "chime", 0.45), (0.76, "sparkle", 0.8), (0.80, "chime_hi", 0.6), (0.88, "bloom", 0.6)])
    case .relBalloon:
      list = at([(0.03, "whoosh", 0.5), (0.14, "light", 0.9), (0.16, "rise", 0.7), (0.50, "chime", 0.45), (0.70, "sparkle", 0.5), (0.90, "chime_hi", 0.5)])
    case .relArrow:
      list = at([(0.04, "rise", 0.5), (0.115, "whoosh", 0.9), (0.20, "snap", 1), (0.205, "chime_hi", 0.8), (0.23, "sparkle", 0.8), (0.30, "bloom", 0.7), (0.60, "chime", 0.4)])
    case .relPotion:
      list = at([(0.06, "pour", 1), (0.29, "drop", 0.6), (0.30, "bubbles", 0.7), (0.36, "drop", 0.6), (0.43, "drop", 0.6), (0.50, "drop", 0.6), (0.55, "bubbles", 0.8),
                 (0.57, "drop", 0.6), (0.62, "sparkle", 0.6), (0.75, "chime", 0.6), (0.88, "bloom", 0.6)])
    case .relDeep:
      list = at([(0.04, "whoosh", 0.4), (0.05, "bubbles", 0.6), (0.30, "chime", 0.4), (0.50, "bubbles", 0.5), (0.66, "sparkle", 0.6), (0.78, "star", 0.8), (0.86, "bloom", 0.6)])
    }
    list.append((duration - 1.5, "done", 0.9))
    return list.sorted { $0.0 < $1.0 }
  }

  // 和着色器里的 hash11 / rainStart 同一套算法，金币落水的触感才能对上画面。
  private static func hash11(_ x: Float) -> Float {
    var p = (x * 0.1031).truncatingRemainder(dividingBy: 1)
    p *= p + 33.33
    p *= p + p
    return p - p.rounded(.down)
  }

  static func rainStart(_ i: Int) -> Float { 2.4 + 0.52 * Float(i) + 0.25 * hash11(Float(i) * 3.7) }
}

final class StageViewFactory: NSObject, FlutterPlatformViewFactory {
  private let messenger: FlutterBinaryMessenger
  init(messenger: FlutterBinaryMessenger) { self.messenger = messenger }

  func create(withFrame frame: CGRect, viewIdentifier viewId: Int64, arguments args: Any?) -> FlutterPlatformView {
    StageView(frame: frame, viewId: viewId, args: args as? [String: Any], messenger: messenger)
  }

  func createArgsCodec() -> FlutterMessageCodec & NSObjectProtocol { FlutterStandardMessageCodec.sharedInstance() }
}

final class StageView: NSObject, FlutterPlatformView, MTKViewDelegate {
  private let container = UIView()
  private let mtk: MTKView
  private let channel: FlutterMethodChannel
  private var queue: MTLCommandQueue?
  private var pipeline: StagePipeline?
  private var coinTexture: MTLTexture?

  private var scene: StageScene
  private var pendingScene: StageScene?
  private var pendingPlay = false
  private var pendingReset = false
  private var fade: Float = 0
  private var glow: [StageScene: Float] = [:]
  private var touch: SIMD2<Float> = .zero
  private let t0 = CACurrentMediaTime()
  private var last = CACurrentMediaTime()
  private var ceremonyStart: CFTimeInterval?
  private var nextCue = 0
  private var nextSound = 0
  /// 这一次仪式的时长、触感和音效提示点，开始时定下来
  private var duration: Float = 9
  private var requestedDuration: Float?
  private var activeCues: [(Float, String)] = []
  private var activeSounds: [(Float, String, Float)] = []

  init(frame: CGRect, viewId: Int64, args: [String: Any]?, messenger: FlutterBinaryMessenger) {
    scene = StageScene.named(args?["scene"] as? String ?? "wealth")
    let device = MTLCreateSystemDefaultDevice()
    mtk = MTKView(frame: frame, device: device)
    channel = FlutterMethodChannel(name: "yuanjing/stage_\(viewId)", binaryMessenger: messenger)
    super.init()

    container.backgroundColor = .black
    mtk.frame = container.bounds
    mtk.autoresizingMask = [.flexibleWidth, .flexibleHeight]
    mtk.colorPixelFormat = .bgra8Unorm
    mtk.framebufferOnly = true
    mtk.preferredFramesPerSecond = 60
    mtk.isOpaque = true
    mtk.contentScaleFactor = scene.renderScale
    mtk.delegate = self
    container.addSubview(mtk)

    if let device { build(device) }
    AudioDirector.shared.setBed(scene.name)
    channel.setMethodCallHandler { [weak self] call, result in self?.handle(call, result) }
    let center = NotificationCenter.default
    center.addObserver(self, selector: #selector(pause), name: UIApplication.willResignActiveNotification, object: nil)
    center.addObserver(self, selector: #selector(resume), name: UIApplication.didBecomeActiveNotification, object: nil)
  }

  deinit { NotificationCenter.default.removeObserver(self) }

  func view() -> UIView { container }

  @objc private func pause() { mtk.isPaused = true }
  @objc private func resume() { last = CACurrentMediaTime(); mtk.isPaused = false }

  private func build(_ device: MTLDevice) {
    queue = device.makeCommandQueue()
    do {
      pipeline = try StagePipeline(device: device, source: stageShaderSource, outputFormat: mtk.colorPixelFormat)
    } catch {
      NSLog("[yuanjing] 着色器编译失败：\(error)")
    }
    coinTexture = StageView.makeCoinTexture(device)
  }

  /// 方孔钱的浮雕高度图：外缘、方孔边和「心想事成」四个字。
  private static func makeCoinTexture(_ device: MTLDevice) -> MTLTexture? {
    let size = 512
    guard let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: size,
                              space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return nil }
    ctx.setFillColor(gray: 0.32, alpha: 1)
    ctx.fill(CGRect(x: 0, y: 0, width: size, height: size))
    ctx.translateBy(x: 0, y: CGFloat(size))
    ctx.scaleBy(x: 1, y: -1)
    ctx.setShadow(offset: .zero, blur: 7, color: UIColor.white.cgColor)
    ctx.setStrokeColor(gray: 1, alpha: 1)
    ctx.setLineWidth(36)
    ctx.strokeEllipse(in: CGRect(x: 22, y: 22, width: 468, height: 468))
    ctx.setLineWidth(22)
    ctx.stroke(CGRect(x: 182, y: 182, width: 148, height: 148))
    UIGraphicsPushContext(ctx)
    let font = ["SourceHanSerifCN-Bold", "STSongti-SC-Black", "PingFangSC-Semibold"].lazy.compactMap { UIFont(name: $0, size: 106) }.first
      ?? UIFont.systemFont(ofSize: 106, weight: .bold)
    let attrs: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: UIColor.white]
    for (text, x, y) in [("心", 256, 112), ("想", 256, 404), ("事", 402, 258), ("成", 110, 258)] {
      let str = text as NSString
      let sz = str.size(withAttributes: attrs)
      str.draw(at: CGPoint(x: CGFloat(x) - sz.width / 2, y: CGFloat(y) - sz.height / 2), withAttributes: attrs)
    }
    UIGraphicsPopContext()
    guard let data = ctx.data else { return nil }
    let desc = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .r8Unorm, width: size, height: size, mipmapped: false)
    let tex = device.makeTexture(descriptor: desc)
    tex?.replace(region: MTLRegionMake2D(0, 0, size, size), mipmapLevel: 0, withBytes: data, bytesPerRow: ctx.bytesPerRow)
    return tex
  }

  private func handle(_ call: FlutterMethodCall, _ result: FlutterResult) {
    let args = call.arguments as? [String: Any]
    switch call.method {
    case "setScene":
      let next = StageScene.named(args?["scene"] as? String ?? "wealth")
      if next != scene, ceremonyStart == nil {
        pendingScene = next
        AudioDirector.shared.setBed(next.name)
      }
      result(nil)
    case "play":
      let target = pendingScene ?? scene
      guard ceremonyStart == nil, !pendingPlay else { return result(Double(ceremonyStart != nil ? duration : requestedDuration ?? target.duration)) }
      // 只有释放的五场可以另外指定时长
      requestedDuration = target.isRelease ? (args?["duration"] as? Double).map { Float(max($0, 8)) } : nil
      if (glow[target] ?? 0) > 0 { pendingPlay = true } else if pendingScene != nil { pendingPlay = true } else { startCeremony() }
      result(Double(requestedDuration ?? target.duration))
    case "stop":
      // 中途结束：不发完成通知，画面暗一下回到开始前的样子
      if ceremonyStart != nil { ceremonyStart = nil; pendingReset = true }
      pendingPlay = false
      result(nil)
    case "reset":
      // 把放完之后的余韵清掉，回到开始前的样子
      if ceremonyStart == nil { pendingReset = true }
      result(nil)
    case "setPaused":
      let paused = args?["paused"] as? Bool ?? false
      if !paused { last = CACurrentMediaTime() }
      mtk.isPaused = paused
      result(nil)
    case "setTouch":
      touch = SIMD2(Float(args?["x"] as? Double ?? 0), Float(args?["y"] as? Double ?? 0))
      result(nil)
    default:
      result(FlutterMethodNotImplemented)
    }
  }

  private func startCeremony() {
    glow[scene] = 0
    nextCue = 0
    nextSound = 0
    duration = requestedDuration ?? scene.duration
    activeCues = scene.cues(duration)
    activeSounds = scene.sounds(duration)
    ceremonyStart = CACurrentMediaTime()
  }

  func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {}

  func draw(in view: MTKView) {
    let now = CACurrentMediaTime()
    let dt = Float(min(now - last, 0.1))
    last = now

    // 切场景、或在余韵里再许一次愿：先暗下去，换好再亮起来
    let leaving = pendingScene != nil || pendingReset || (pendingPlay && fade > 0 && ceremonyStart == nil)
    if leaving {
      fade = max(0, fade - dt / 0.26)
      if fade <= 0 {
        if let next = pendingScene { scene = next; pendingScene = nil; mtk.contentScaleFactor = scene.renderScale }
        if pendingReset { pendingReset = false; glow[scene] = 0 }
        if pendingPlay { pendingPlay = false; startCeremony() }
      }
    } else {
      fade = min(1, fade + dt / 0.5)
    }

    var prog: Float = -1
    if let start = ceremonyStart {
      let ts = Float(now - start)
      prog = ts / duration
      while nextCue < activeCues.count, activeCues[nextCue].0 <= ts { Haptics.shared.play(activeCues[nextCue].1); nextCue += 1 }
      while nextSound < activeSounds.count, activeSounds[nextSound].0 <= ts { AudioDirector.shared.play(activeSounds[nextSound].1, volume: activeSounds[nextSound].2); nextSound += 1 }
      if prog >= 1 {
        prog = -1
        ceremonyStart = nil
        glow[scene] = 1
        channel.invokeMethod("done", arguments: nil)
      }
    }

    guard let pipeline, let queue, let drawable = view.currentDrawable, let pass = view.currentRenderPassDescriptor,
          let cmd = queue.makeCommandBuffer() else { return }
    var u = StageUniforms()
    u.time = Float(now - t0)
    u.prog = prog
    u.scene = Float(scene.rawValue)
    u.fade = fade * fade * (3 - 2 * fade)
    u.dur = ceremonyStart != nil ? duration : scene.duration
    u.glow = glow[scene] ?? 0
    u.touch = touch
    pipeline.draw(cmd, uniforms: u, coin: coinTexture, output: pass, width: Int(view.drawableSize.width), height: Int(view.drawableSize.height))
    cmd.present(drawable)
    cmd.commit()
  }
}
