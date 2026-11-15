import AVFoundation
import Flutter
import PhotosUI
import Speech
import UIKit

/// 不属于某个画面的系统能力：朗读用户自己写的话、语音输入、从相册选图、分享文件。

private func topController() -> UIViewController? {
  let window = UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.keyWindow }.first
  var top = window?.rootViewController
  while let next = top?.presentedViewController { top = next }
  return top
}

func documentsURL() -> URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }

/// 朗读任意文字。预先生成的引导语走 Voice，这里用系统自带的中文语音，
/// 只给「用户自己写的肯定语」用：内容事先不知道，没法提前生成。音色不如预生成的自然。
final class Speaker: NSObject, AVSpeechSynthesizerDelegate {
  static let shared = Speaker()
  private let synth = AVSpeechSynthesizer()
  private var exporter: AVSpeechSynthesizer?
  private var pending: FlutterResult?

  override init() {
    super.init()
    synth.delegate = self
  }

  private func utterance(_ text: String) -> AVSpeechUtterance {
    let u = AVSpeechUtterance(string: text)
    // 系统里装了哪个中文女声就用音质最好的那个
    let voices = AVSpeechSynthesisVoice.speechVoices().filter { $0.language == "zh-CN" }
    u.voice = voices.max { $0.quality.rawValue < $1.quality.rawValue } ?? AVSpeechSynthesisVoice(language: "zh-CN")
    u.rate = 0.40
    u.pitchMultiplier = 1.04
    u.preUtteranceDelay = 0.2
    u.postUtteranceDelay = 0.5
    return u
  }

  /// 念完（或被打断）时回调：true 表示完整念完。
  func speak(_ text: String, result: @escaping FlutterResult) {
    stop()
    pending = result
    AudioDirector.shared.duck(for: Double(text.count) * 0.32 + 1.5)
    synth.speak(utterance(text))
  }

  func stop() {
    if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }
    pending?(false)
    pending = nil
  }

  func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
    pending?(true)
    pending = nil
  }

  /// 把朗读结果存成音频文件，给会员导出用。
  func export(_ text: String, completion: @escaping (URL?) -> Void) {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("愿境肯定语-\(Int(Date().timeIntervalSince1970)).caf")
    var file: AVAudioFile?
    let writer = AVSpeechSynthesizer()
    exporter = writer
    writer.write(utterance(text)) { [weak self] buffer in
      guard let pcm = buffer as? AVAudioPCMBuffer else { return }
      if pcm.frameLength == 0 {
        // 空的一块表示写完了
        let done = file != nil
        file = nil
        DispatchQueue.main.async {
          self?.exporter = nil
          completion(done ? url : nil)
        }
        return
      }
      if file == nil {
        file = try? AVAudioFile(forWriting: url, settings: pcm.format.settings, commonFormat: pcm.format.commonFormat, interleaved: pcm.format.isInterleaved)
      }
      try? file?.write(from: pcm)
    }
  }
}

/// 语音输入：边说边出字。识别结果从 `yuanjing/speech` 这条事件通道推给 Flutter。
final class Dictation: NSObject, FlutterStreamHandler {
  static let shared = Dictation()
  private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "zh-CN"))
  private let engine = AVAudioEngine()
  private var request: SFSpeechAudioBufferRecognitionRequest?
  private var task: SFSpeechRecognitionTask?
  private var sink: FlutterEventSink?

  func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
    sink = events
    return nil
  }

  func onCancel(withArguments arguments: Any?) -> FlutterError? {
    sink = nil
    return nil
  }

  /// 开始听。成功回 nil，失败回一句给用户看的原因。
  func start(_ result: @escaping FlutterResult) {
    SFSpeechRecognizer.requestAuthorization { status in
      guard status == .authorized else {
        return DispatchQueue.main.async { result("没有语音识别权限，请到系统设置里打开") }
      }
      AVAudioSession.sharedInstance().requestRecordPermission { ok in
        DispatchQueue.main.async { result(ok ? self.begin() : "没有麦克风权限，请到系统设置里打开") }
      }
    }
  }

  private func begin() -> String? {
    finish()
    guard let recognizer, recognizer.isAvailable else { return "这台设备现在用不了语音识别" }
    let session = AVAudioSession.sharedInstance()
    do {
      try session.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker, .mixWithOthers, .allowBluetooth])
      try session.setActive(true)
    } catch {
      return "麦克风打不开"
    }
    let req = SFSpeechAudioBufferRecognitionRequest()
    req.shouldReportPartialResults = true
    request = req
    let input = engine.inputNode
    let format = input.outputFormat(forBus: 0)
    guard format.sampleRate > 0, format.channelCount > 0 else { return "麦克风打不开" }
    input.removeTap(onBus: 0)
    input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in req.append(buffer) }
    engine.prepare()
    do { try engine.start() } catch { return "麦克风打不开" }
    task = recognizer.recognitionTask(with: req) { [weak self] res, err in
      DispatchQueue.main.async {
        if let res { self?.sink?(["text": res.bestTranscription.formattedString, "final": res.isFinal]) }
        if err != nil || res?.isFinal == true { self?.finish() }
      }
    }
    return nil
  }

  func stop() {
    request?.endAudio()
    finish()
  }

  private func finish() {
    guard request != nil || engine.isRunning else { return }
    if engine.isRunning {
      engine.stop()
      engine.inputNode.removeTap(onBus: 0)
    }
    task?.cancel()
    task = nil
    request = nil
    sink?(["text": "", "final": true, "ended": true])
    // 把音频会话还给播放
    try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [.mixWithOthers])
  }
}

/// 从相册选一张图，缩小后存进应用自己的文件夹，返回相对路径（photos/xxx.jpg）。
final class PhotoPicker: NSObject, PHPickerViewControllerDelegate {
  static let shared = PhotoPicker()
  private var pending: FlutterResult?

  func pick(_ result: @escaping FlutterResult) {
    pending?(nil)
    pending = result
    var config = PHPickerConfiguration()
    config.filter = .images
    config.selectionLimit = 1
    let picker = PHPickerViewController(configuration: config)
    picker.delegate = self
    guard let top = topController() else { result(nil); pending = nil; return }
    top.present(picker, animated: true)
  }

  func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
    picker.dismiss(animated: true)
    guard let item = results.first?.itemProvider, item.canLoadObject(ofClass: UIImage.self) else {
      pending?(nil)
      pending = nil
      return
    }
    item.loadObject(ofClass: UIImage.self) { [weak self] object, _ in
      var path: String?
      if let image = object as? UIImage {
        let scale = min(1, 1400 / max(image.size.width, image.size.height))
        let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let small = UIGraphicsImageRenderer(size: size, format: format).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        let dir = documentsURL().appendingPathComponent("photos")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let name = UUID().uuidString + ".jpg"
        if let data = small.jpegData(compressionQuality: 0.86), (try? data.write(to: dir.appendingPathComponent(name))) != nil {
          path = "photos/" + name
        }
      }
      DispatchQueue.main.async {
        self?.pending?(path)
        self?.pending = nil
      }
    }
  }
}

/// 系统分享面板：导出音频用。
func shareFile(_ url: URL) {
  guard let top = topController() else { return }
  let sheet = UIActivityViewController(activityItems: [url], applicationActivities: nil)
  sheet.popoverPresentationController?.sourceView = top.view
  top.present(sheet, animated: true)
}
