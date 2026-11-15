import AVFoundation

/// 环境音和音效。
///
/// - 环境音（`assets/audio/amb_<名字>.m4a`）：24 秒的无缝循环，换场景时两条轨道交叉淡入淡出。
/// - 音效（`assets/audio/sfx_<名字>.m4a`）：八个播放器轮流用，可以叠着响。
/// - 引导语说话时，环境音自动压低，说完恢复。
///
/// 所有方法都在主线程调用。文件不存在时静默跳过，所以素材没生成也不影响别的功能。
final class AudioDirector {
  static let shared = AudioDirector()

  /// 把 Flutter 资源路径换成安装包里的真实路径，由插件在注册时设置
  var resolve: ((String) -> String?)?
  var bedVolume: Float = 0.6
  var sfxVolume: Float = 0.85

  private let engine = AVAudioEngine()
  private let format = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 2)!
  private let beds = [AVAudioPlayerNode(), AVAudioPlayerNode()]
  private let voices = (0..<8).map { _ in AVAudioPlayerNode() }
  private var bedIndex = 0
  private var bedName: String?
  private var nextVoice = 0
  private var cache: [String: AVAudioPCMBuffer] = [:]
  private var attached = false
  private var fades: [ObjectIdentifier: Timer] = [:]
  private var duckUntil: Date = .distantPast

  private init() {
    NotificationCenter.default.addObserver(forName: .AVAudioEngineConfigurationChange, object: engine, queue: .main) { [weak self] _ in
      // 耳机插拔之类会让引擎停下：重新启动，把当前的环境音接着放
      guard let self else { return }
      let name = self.bedName
      self.bedName = nil
      self.setBed(name)
    }
  }

  private func start() -> Bool {
    if !attached {
      attached = true
      let session = AVAudioSession.sharedInstance()
      try? session.setCategory(.playback, mode: .default, options: [.mixWithOthers])
      try? session.setActive(true)
      for node in beds + voices {
        engine.attach(node)
        engine.connect(node, to: engine.mainMixerNode, format: format)
      }
    }
    if engine.isRunning { return true }
    engine.prepare()
    do { try engine.start() } catch {
      NSLog("[yuanjing] 音频引擎启动失败：\(error)")
      return false
    }
    return true
  }

  private func buffer(_ file: String, keep: Bool) -> AVAudioPCMBuffer? {
    if let hit = cache[file] { return hit }
    guard let path = resolve?("assets/audio/\(file).m4a"),
          let audio = try? AVAudioFile(forReading: URL(fileURLWithPath: path)),
          audio.processingFormat.sampleRate == format.sampleRate, audio.processingFormat.channelCount == format.channelCount,
          let buf = AVAudioPCMBuffer(pcmFormat: audio.processingFormat, frameCapacity: AVAudioFrameCount(audio.length)),
          (try? audio.read(into: buf)) != nil else {
      NSLog("[yuanjing] 声音素材读不到：\(file)")
      return nil
    }
    #if DEBUG
    NSLog("[yuanjing] 声音已载入：\(file)，\(String(format: "%.1f", Double(buf.frameLength) / format.sampleRate)) 秒")
    #endif
    if keep { cache[file] = buf }
    return buf
  }

  private func fade(_ node: AVAudioPlayerNode, to target: Float, over seconds: TimeInterval, then done: (() -> Void)? = nil) {
    let key = ObjectIdentifier(node)
    fades[key]?.invalidate()
    let from = node.volume
    let begin = Date()
    fades[key] = Timer.scheduledTimer(withTimeInterval: 1.0 / 30, repeats: true) { [weak self] timer in
      let k = Float(min(Date().timeIntervalSince(begin) / max(seconds, 0.01), 1))
      node.volume = from + (target - from) * (k * k * (3 - 2 * k))
      if k >= 1 {
        timer.invalidate()
        self?.fades[key] = nil
        done?()
      }
    }
  }

  /// 换环境音。传 nil 表示淡出到无声。同名重复调用不会重新起播。
  func setBed(_ name: String?) {
    guard name != bedName else { return }
    bedName = name
    guard start() else { return }
    let old = beds[bedIndex]
    fade(old, to: 0, over: 1.4) { old.stop() }
    bedIndex = 1 - bedIndex
    let next = beds[bedIndex]
    guard let name, let buf = buffer("amb_\(name)", keep: false) else { return }
    next.stop()
    next.volume = 0
    next.scheduleBuffer(buf, at: nil, options: .loops)
    next.play()
    fade(next, to: Date() < duckUntil ? bedVolume * 0.4 : bedVolume, over: 1.8)
  }

  /// 播一个音效。
  func play(_ name: String, volume: Float = 1) {
    guard start(), let buf = buffer("sfx_\(name)", keep: true) else { return }
    let node = voices[nextVoice]
    nextVoice = (nextVoice + 1) % voices.count
    node.stop()
    node.volume = sfxVolume * volume
    node.scheduleBuffer(buf, at: nil, options: [])
    node.play()
  }

  /// 引导语说话的这几秒把环境音压低。
  func duck(for seconds: TimeInterval) {
    duckUntil = Date().addingTimeInterval(seconds)
    let bed = beds[bedIndex]
    fade(bed, to: bedVolume * 0.4, over: 0.35)
    DispatchQueue.main.asyncAfter(deadline: .now() + seconds) { [weak self] in
      guard let self, Date() >= self.duckUntil, self.bedName != nil else { return }
      self.fade(self.beds[self.bedIndex], to: self.bedVolume, over: 0.9)
    }
  }
}
