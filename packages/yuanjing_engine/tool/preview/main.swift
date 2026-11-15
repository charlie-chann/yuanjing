// 在 Mac 上离屏渲染仪式舞台的画面，用来调着色器，不用开模拟器。
// 编译：swiftc -O tool/preview/main.swift ios/yuanjing_engine/Sources/yuanjing_engine/StagePipeline.swift -o /tmp/render_preview
// 用法：render_preview <stage.metal> <输出目录> <场景:进度:余韵:时间> ...
//   场景 0 财富 1 事业 2 外貌 3 健康 4 情绪 5 生活 6 宠物；7 池 8 热气球 9 箭 10 魔药 11 深海；进度 -1 表示待机
import AppKit
import Metal

let durations: [Float] = [9.2, 9.0, 8.5, 9.0, 9.0, 10.0, 8.0, 30, 30, 30, 30, 30]
let args = CommandLine.arguments
guard args.count >= 4, let device = MTLCreateSystemDefaultDevice() else { print("usage: render_preview shader outDir specs..."); exit(1) }
let W = 590, H = 1278

// 金币上的字用工程里的思源宋体：只在这个进程里注册，不装进系统
let fontURL = URL(fileURLWithPath: args[1]).deletingLastPathComponent().appendingPathComponent("../../../assets/fonts/SourceHanSerifCN-Bold.otf").standardized
CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)

func coinTexture() -> MTLTexture? {
  let s = 512
  guard let ctx = CGContext(data: nil, width: s, height: s, bitsPerComponent: 8, bytesPerRow: s, space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return nil }
  ctx.setFillColor(gray: 0.32, alpha: 1); ctx.fill(CGRect(x: 0, y: 0, width: s, height: s))
  ctx.translateBy(x: 0, y: CGFloat(s)); ctx.scaleBy(x: 1, y: -1)
  ctx.setShadow(offset: .zero, blur: 7, color: NSColor.white.cgColor)
  ctx.setStrokeColor(gray: 1, alpha: 1)
  ctx.setLineWidth(36); ctx.strokeEllipse(in: CGRect(x: 22, y: 22, width: 468, height: 468))
  ctx.setLineWidth(22); ctx.stroke(CGRect(x: 182, y: 182, width: 148, height: 148))
  NSGraphicsContext.saveGraphicsState()
  NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: true)
  let font = NSFont(name: "SourceHanSerifCN-Bold", size: 106) ?? NSFont(name: "STSongti-SC-Black", size: 106) ?? NSFont.boldSystemFont(ofSize: 106)
  let attrs: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: NSColor.white]
  for (text, x, y) in [("心", 256, 112), ("想", 256, 404), ("事", 402, 258), ("成", 110, 258)] {
    let str = text as NSString; let sz = str.size(withAttributes: attrs)
    str.draw(at: CGPoint(x: CGFloat(x) - sz.width / 2, y: CGFloat(y) - sz.height / 2), withAttributes: attrs)
  }
  NSGraphicsContext.restoreGraphicsState()
  let d = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .r8Unorm, width: s, height: s, mipmapped: false)
  let t = device.makeTexture(descriptor: d)
  t?.replace(region: MTLRegionMake2D(0, 0, s, s), mipmapLevel: 0, withBytes: ctx.data!, bytesPerRow: ctx.bytesPerRow)
  return t
}

do {
  let pipeline = try StagePipeline(device: device, source: try String(contentsOfFile: args[1], encoding: .utf8), outputFormat: .bgra8Unorm)
  let td = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .bgra8Unorm, width: W, height: H, mipmapped: false)
  td.usage = [.renderTarget, .shaderRead]; td.storageMode = .shared
  let target = device.makeTexture(descriptor: td)!
  let coin = coinTexture()
  let queue = device.makeCommandQueue()!
  for (n, spec) in args[3...].enumerated() {
    let p = spec.split(separator: ":").map { Float($0) ?? 0 }
    let scene = Int(p[0])
    var u = StageUniforms()
    u.time = p.count > 3 ? p[3] : 12.3; u.prog = p[1]; u.scene = p[0]; u.fade = 1; u.dur = durations[scene]; u.glow = p.count > 2 ? p[2] : 0
    let pass = MTLRenderPassDescriptor()
    pass.colorAttachments[0].texture = target; pass.colorAttachments[0].loadAction = .dontCare; pass.colorAttachments[0].storeAction = .store
    let cmd = queue.makeCommandBuffer()!
    pipeline.draw(cmd, uniforms: u, coin: coin, output: pass, width: W, height: H)
    cmd.commit(); cmd.waitUntilCompleted()
    var bytes = [UInt8](repeating: 0, count: W * H * 4)
    target.getBytes(&bytes, bytesPerRow: W * 4, from: MTLRegionMake2D(0, 0, W, H), mipmapLevel: 0)
    let ctx = CGContext(data: &bytes, width: W, height: H, bitsPerComponent: 8, bytesPerRow: W * 4, space: CGColorSpaceCreateDeviceRGB(),
                        bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue)!
    let rep = NSBitmapImageRep(cgImage: ctx.makeImage()!)
    try rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(args[2])/f\(String(format: "%02d", n)).png"))
  }
  print("rendered \(args.count - 3) frames")
} catch { print("ERROR: \(error)"); exit(1) }
