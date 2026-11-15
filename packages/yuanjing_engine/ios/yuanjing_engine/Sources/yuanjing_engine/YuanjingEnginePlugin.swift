import CoreText
import Flutter
import UIKit

/// 愿境原生引擎的入口。
/// - `yuanjing/stage`：仪式舞台（Metal 全屏着色器），以 PlatformView 的形式嵌进 Flutter。
/// - `yuanjing/room`：我的房间（RealityKit），里面是动漫形象。
/// - `yuanjing/engine`：不属于某个视图的能力：触感、引导语音、环境音和音效，以及朗读、语音输入、选图、分享（见 Services.swift）。
/// - `yuanjing/speech`：语音输入的识别结果，事件通道。
public class YuanjingEnginePlugin: NSObject, FlutterPlugin {
  private let registrar: FlutterPluginRegistrar

  init(registrar: FlutterPluginRegistrar) { self.registrar = registrar }

  public static func register(with registrar: FlutterPluginRegistrar) {
    // 金币浮雕上的字用思源宋体：把 Flutter 资源里的字体文件注册给原生绘图
    if let font = assetPath("assets/fonts/SourceHanSerifCN-Bold.otf", registrar) {
      CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: font) as CFURL, .process, nil)
    }
    AudioDirector.shared.resolve = { assetPath($0, registrar) }
    registrar.register(StageViewFactory(messenger: registrar.messenger()), withId: "yuanjing/stage")
    registrar.register(RoomViewFactory(registrar: registrar), withId: "yuanjing/room")
    let channel = FlutterMethodChannel(name: "yuanjing/engine", binaryMessenger: registrar.messenger())
    registrar.addMethodCallDelegate(YuanjingEnginePlugin(registrar: registrar), channel: channel)
    FlutterEventChannel(name: "yuanjing/speech", binaryMessenger: registrar.messenger()).setStreamHandler(Dictation.shared)
  }

  /// Flutter 资源在安装包里的真实路径
  static func assetPath(_ asset: String, _ registrar: FlutterPluginRegistrar) -> String? {
    Bundle.main.path(forResource: registrar.lookupKey(forAsset: asset), ofType: nil)
  }

  public func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    switch call.method {
    case "haptic":
      let name = (call.arguments as? [String: Any])?["name"] as? String ?? "tick"
      Haptics.shared.play(name)
      result(nil)
    case "voice":
      let args = call.arguments as? [String: Any]
      guard let asset = args?["asset"] as? String, let path = YuanjingEnginePlugin.assetPath(asset, registrar) else { return result(false) }
      result(Voice.shared.play(path: path, volume: Float(args?["volume"] as? Double ?? 1)))
    case "bed":
      AudioDirector.shared.setBed((call.arguments as? [String: Any])?["name"] as? String)
      result(nil)
    case "sfx":
      let args = call.arguments as? [String: Any]
      AudioDirector.shared.play(args?["name"] as? String ?? "tap", volume: Float(args?["volume"] as? Double ?? 1))
      result(nil)
    case "voiceStop":
      Voice.shared.stop()
      result(nil)
    case "voiceTimed":
      // 和 voice 一样播一句，但返回这一句有多长（秒），冥想那种一句接一句的要靠它排时间
      let args = call.arguments as? [String: Any]
      guard let asset = args?["asset"] as? String, let path = YuanjingEnginePlugin.assetPath(asset, registrar) else { return result(nil) }
      result(Voice.shared.play(path: path, volume: Float(args?["volume"] as? Double ?? 1)) ? Voice.shared.length : nil)
    case "voiceFile":
      // 播放应用文件夹里的一句（服务器下发、缓存到本机的回应语音），返回时长
      let args = call.arguments as? [String: Any]
      guard let path = args?["path"] as? String, FileManager.default.fileExists(atPath: path) else { return result(nil) }
      result(Voice.shared.play(path: path, volume: Float(args?["volume"] as? Double ?? 1)) ? Voice.shared.length : nil)
    case "docsDir":
      result(documentsURL().path)
    case "speak":
      Speaker.shared.speak((call.arguments as? [String: Any])?["text"] as? String ?? "", result: result)
    case "speakStop":
      Speaker.shared.stop()
      result(nil)
    case "speakExport":
      Speaker.shared.export((call.arguments as? [String: Any])?["text"] as? String ?? "") { url in
        if let url { shareFile(url) }
        result(url != nil)
      }
    case "pickPhoto":
      PhotoPicker.shared.pick(result)
    case "listenStart":
      Dictation.shared.start(result)
    case "listenStop":
      Dictation.shared.stop()
      result(nil)
    default:
      result(FlutterMethodNotImplemented)
    }
  }
}
