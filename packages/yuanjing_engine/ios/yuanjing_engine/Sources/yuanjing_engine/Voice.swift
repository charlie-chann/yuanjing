import AVFoundation

/// 播放预先生成好的引导语。一次只播一句，新的一句进来时上一句淡出。
final class Voice {
  static let shared = Voice()
  private var player: AVAudioPlayer?

  /// 正在播的这一句有多长（秒）
  var length: Double { player?.duration ?? 0 }

  /// 返回 false 表示文件不存在或打不开（比如还没生成语音），调用方不用处理。
  @discardableResult
  func play(path: String, volume: Float) -> Bool {
    stop()
    guard let next = try? AVAudioPlayer(contentsOf: URL(fileURLWithPath: path)) else { return false }
    next.volume = 0
    next.prepareToPlay()
    next.play()
    next.setVolume(volume, fadeDuration: 0.25)
    AudioDirector.shared.duck(for: next.duration + 0.4)
    player = next
    return true
  }

  func stop() {
    guard let old = player else { return }
    player = nil
    old.setVolume(0, fadeDuration: 0.3)
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { old.stop() }
  }
}
