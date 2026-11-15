import CoreHaptics
import UIKit

/// 仪式里的触感。模拟器和不支持的机型上什么都不做。
final class Haptics {
  static let shared = Haptics()
  private var engine: CHHapticEngine?

  private init() {
    guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else { return }
    engine = try? CHHapticEngine()
    engine?.isAutoShutdownEnabled = true
    engine?.resetHandler = { [weak self] in try? self?.engine?.start() }
  }

  private func transient(_ t: TimeInterval, _ intensity: Float, _ sharpness: Float) -> CHHapticEvent {
    CHHapticEvent(eventType: .hapticTransient, parameters: [
      .init(parameterID: .hapticIntensity, value: intensity), .init(parameterID: .hapticSharpness, value: sharpness),
    ], relativeTime: t)
  }

  private func continuous(_ t: TimeInterval, _ duration: TimeInterval, _ intensity: Float, _ sharpness: Float) -> CHHapticEvent {
    CHHapticEvent(eventType: .hapticContinuous, parameters: [
      .init(parameterID: .hapticIntensity, value: intensity), .init(parameterID: .hapticSharpness, value: sharpness),
    ], relativeTime: t, duration: duration)
  }

  func play(_ name: String) {
    guard let engine else { return }
    let events: [CHHapticEvent]
    switch name {
    case "drop": events = [transient(0, 1.0, 0.35), continuous(0.02, 0.35, 0.45, 0.1)]
    case "coin": events = [transient(0, 0.7, 0.9)]
    case "bloom": events = [continuous(0, 0.5, 0.3, 0.15), continuous(0.5, 0.6, 0.6, 0.2), transient(1.1, 0.8, 0.4)]
    case "breath": events = [continuous(0, 0.9, 0.22, 0.05), continuous(0.9, 0.9, 0.4, 0.08)]
    case "rise": events = [transient(0, 0.35, 0.5), transient(0.12, 0.5, 0.6), transient(0.24, 0.7, 0.7)]
    default: events = [transient(0, 0.5, 0.6)]
    }
    do {
      try engine.start()
      let player = try engine.makePlayer(with: CHHapticPattern(events: events, parameters: []))
      try player.start(atTime: CHHapticTimeImmediate)
    } catch {}
  }
}
