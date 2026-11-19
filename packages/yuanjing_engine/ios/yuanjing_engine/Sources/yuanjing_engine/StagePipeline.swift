import Metal
import simd

/// 场景着色器的参数。字段顺序要和 shaders/stage.metal 里的 Uniforms 一致。
struct StageUniforms {
  var res: SIMD2<Float> = .zero
  var time: Float = 0
  var prog: Float = -1
  var scene: Float = 0
  var fade: Float = 0
  var dur: Float = 9
  var glow: Float = 0
  var touch: SIMD2<Float> = .zero
  var tap: SIMD2<Float> = .zero
  /// 小游戏：开着没有、这一轮的进度、能量、离上一次点过了几秒
  var game: SIMD4<Float> = .zero
  /// 小游戏：奖励动画的进度（-1 还没到）、第几轮
  var game2: SIMD4<Float> = SIMD4(-1, 0, 0, 0)
}

/// 后期着色器的参数，对应 shaders/stage.metal 里的 Post。
struct PostUniforms {
  var texel: SIMD2<Float> = .zero
  var threshold: Float = 1
  var intensity: Float = 1
  var time: Float = 0
  var first: Float = 0
  var pad: SIMD2<Float> = .zero
}

/// 仪式舞台的渲染管线，只依赖 Metal，iOS 的视图和 Mac 上的离屏预览工具共用这一份。
///
/// 每帧四步：场景画进一张高动态范围的贴图；把亮部逐级缩小并模糊；再逐级放大叠回去，得到辉光；
/// 最后合成：场景加辉光，过色调映射、暗角和颗粒，输出到屏幕。
final class StagePipeline {
  static let bloomLevels = 5
  /// 辉光只取亮过这个值的部分；辉光叠回去的强度
  var bloomThreshold: Float = 0.9
  var bloomIntensity: Float = 0.55

  private let device: MTLDevice
  private let scenePSO: MTLRenderPipelineState
  private let downPSO: MTLRenderPipelineState
  private let upPSO: MTLRenderPipelineState
  private let compositePSO: MTLRenderPipelineState
  private let sampler: MTLSamplerState
  private var sceneTex: MTLTexture?
  private var mips: [MTLTexture] = []

  init(device: MTLDevice, source: String, outputFormat: MTLPixelFormat) throws {
    self.device = device
    let lib = try device.makeLibrary(source: source, options: nil)
    func pso(_ vertex: String, _ fragment: String, _ format: MTLPixelFormat, additive: Bool = false) throws -> MTLRenderPipelineState {
      let d = MTLRenderPipelineDescriptor()
      d.vertexFunction = lib.makeFunction(name: vertex)
      d.fragmentFunction = lib.makeFunction(name: fragment)
      let a = d.colorAttachments[0]!
      a.pixelFormat = format
      if additive {
        a.isBlendingEnabled = true
        a.rgbBlendOperation = .add
        a.sourceRGBBlendFactor = .one
        a.destinationRGBBlendFactor = .one
        a.sourceAlphaBlendFactor = .one
        a.destinationAlphaBlendFactor = .one
      }
      return try device.makeRenderPipelineState(descriptor: d)
    }
    scenePSO = try pso("stage_vertex", "stage_fragment", .rgba16Float)
    downPSO = try pso("post_vertex", "bloom_down", .rgba16Float)
    upPSO = try pso("post_vertex", "bloom_up", .rgba16Float, additive: true)
    compositePSO = try pso("post_vertex", "stage_composite", outputFormat)
    let s = MTLSamplerDescriptor()
    s.minFilter = .linear
    s.magFilter = .linear
    s.sAddressMode = .clampToEdge
    s.tAddressMode = .clampToEdge
    guard let sampler = device.makeSamplerState(descriptor: s) else { throw NSError(domain: "yuanjing", code: 1) }
    self.sampler = sampler
  }

  private func target(_ w: Int, _ h: Int) -> MTLTexture? {
    let d = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .rgba16Float, width: max(w, 1), height: max(h, 1), mipmapped: false)
    d.usage = [.renderTarget, .shaderRead]
    d.storageMode = .private
    return device.makeTexture(descriptor: d)
  }

  private func resize(_ w: Int, _ h: Int) {
    if let t = sceneTex, t.width == w, t.height == h { return }
    sceneTex = target(w, h)
    mips = (1...StagePipeline.bloomLevels).compactMap { target(w >> $0, h >> $0) }
  }

  private func pass(_ cmd: MTLCommandBuffer, to texture: MTLTexture, load: MTLLoadAction = .dontCare, _ body: (MTLRenderCommandEncoder) -> Void) {
    let d = MTLRenderPassDescriptor()
    d.colorAttachments[0].texture = texture
    d.colorAttachments[0].loadAction = load
    d.colorAttachments[0].storeAction = .store
    guard let enc = cmd.makeRenderCommandEncoder(descriptor: d) else { return }
    enc.setFragmentSamplerState(sampler, index: 0)
    body(enc)
    enc.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3)
    enc.endEncoding()
  }

  /// 画一帧。`output` 是最终要写入的那一遍（屏幕或离屏贴图），宽高是场景的渲染尺寸。
  func draw(_ cmd: MTLCommandBuffer, uniforms: StageUniforms, coin: MTLTexture?, output: MTLRenderPassDescriptor, width: Int, height: Int) {
    resize(width, height)
    guard let sceneTex, mips.count == StagePipeline.bloomLevels else { return }
    var u = uniforms
    u.res = SIMD2(Float(width), Float(height))
    pass(cmd, to: sceneTex) { enc in
      enc.setRenderPipelineState(scenePSO)
      enc.setFragmentBytes(&u, length: MemoryLayout<StageUniforms>.stride, index: 0)
      enc.setFragmentTexture(coin, index: 0)
    }
    var post = PostUniforms(threshold: bloomThreshold, intensity: bloomIntensity, time: uniforms.time)
    var source = sceneTex
    for (i, mip) in mips.enumerated() {
      post.texel = SIMD2(1 / Float(source.width), 1 / Float(source.height))
      post.first = i == 0 ? 1 : 0
      pass(cmd, to: mip) { enc in
        enc.setRenderPipelineState(downPSO)
        enc.setFragmentBytes(&post, length: MemoryLayout<PostUniforms>.stride, index: 0)
        enc.setFragmentTexture(source, index: 0)
      }
      source = mip
    }
    for i in stride(from: mips.count - 2, through: 0, by: -1) {
      let small = mips[i + 1]
      post.texel = SIMD2(1 / Float(small.width), 1 / Float(small.height))
      pass(cmd, to: mips[i], load: .load) { enc in
        enc.setRenderPipelineState(upPSO)
        enc.setFragmentBytes(&post, length: MemoryLayout<PostUniforms>.stride, index: 0)
        enc.setFragmentTexture(small, index: 0)
      }
    }
    post.texel = SIMD2(1 / Float(width), 1 / Float(height))
    guard let enc = cmd.makeRenderCommandEncoder(descriptor: output) else { return }
    enc.setRenderPipelineState(compositePSO)
    enc.setFragmentSamplerState(sampler, index: 0)
    enc.setFragmentBytes(&post, length: MemoryLayout<PostUniforms>.stride, index: 0)
    enc.setFragmentTexture(sceneTex, index: 0)
    enc.setFragmentTexture(mips[0], index: 1)
    enc.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3)
    enc.endEncoding()
  }
}
