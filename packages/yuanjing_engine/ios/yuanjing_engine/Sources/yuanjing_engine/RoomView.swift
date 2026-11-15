import Combine
import Flutter
import RealityKit
import UIKit
import VRMKit
import VRMRealityKit

/// 我的房间：RealityKit 搭的房间，里面站着一个会眨眼、会呼吸的动漫形象。
/// 现在的素材都是占位：形象是 VRoid 的免费样例，小狗是 Quaternius 的 CC0 模型，家具是代码拼的几何体。
final class RoomViewFactory: NSObject, FlutterPlatformViewFactory {
  private let registrar: FlutterPluginRegistrar
  init(registrar: FlutterPluginRegistrar) { self.registrar = registrar }

  func create(withFrame frame: CGRect, viewIdentifier viewId: Int64, arguments args: Any?) -> FlutterPlatformView {
    RoomView(frame: frame, viewId: viewId, args: args as? [String: Any], registrar: registrar)
  }

  func createArgsCodec() -> FlutterMessageCodec & NSObjectProtocol { FlutterStandardMessageCodec.sharedInstance() }
}

final class RoomView: NSObject, FlutterPlatformView {
  private let container = UIView()
  private let channel: FlutterMethodChannel
  private var scene: AnyObject?

  init(frame: CGRect, viewId: Int64, args: [String: Any]?, registrar: FlutterPluginRegistrar) {
    channel = FlutterMethodChannel(name: "yuanjing/room_\(viewId)", binaryMessenger: registrar.messenger())
    super.init()
    container.frame = frame
    container.backgroundColor = UIColor(red: 0.93, green: 0.88, blue: 0.84, alpha: 1)
    let path: (String) -> String? = { YuanjingEnginePlugin.assetPath($0, registrar) }
    let model = (args?["model"] as? String).flatMap(path)
    let pets = (args?["pets"] as? [String] ?? []).compactMap(path)
    let plush = (args?["plush"] as? String).flatMap(path)
    if #available(iOS 18.0, *) {
      // 平台视图总是在主线程创建
      let decor = Set(args?["decor"] as? [String] ?? [])
      let room = MainActor.assumeIsolated {
        let room = RoomScene(container: container, modelPath: model, petPaths: pets, plushPath: plush)
        room.setDecor(decor)
        return room
      }
      scene = room
      channel.setMethodCallHandler { call, result in
        let name = (call.arguments as? [String: Any])?["name"] as? String ?? ""
        if call.method == "action" { MainActor.assumeIsolated { room.perform(name) } }
        if call.method == "decor" {
          let names = Set((call.arguments as? [String: Any])?["names"] as? [String] ?? [])
          MainActor.assumeIsolated { room.setDecor(names) }
        }
        result(nil)
      }
    }
  }

  func view() -> UIView { container }
}

@available(iOS 18.0, *)
@MainActor
final class RoomScene {
  private let arView: ARView
  private let root = AnchorEntity(world: .zero)
  private let camera = PerspectiveCamera()
  private var girl: VRMEntity?
  private var rest: [HumanoidBone: simd_quatf] = [:]
  private var clock: Float = 0
  private var nextBlink: Float = 2
  private var blink: Float = -1
  private var smile: Float = 0
  private var wave: Float = -1
  private var spin: Float = -1
  private var lights: [ModelEntity] = []
  private var pets: [GLTFEntity] = []
  private var petHolders: [Entity] = []
  private var walkTarget: SIMD3<Float>?
  private var nextWalk: Float = 6
  private var petBusy: Float = 0
  private var tick: Cancellable?
  private var baseYaw: Float = 0
  /// 商城里买的装扮：一件一个组，默认不显示
  private var decor: [String: Entity] = [:]

  init(container: UIView, modelPath: String?, petPaths: [String], plushPath: String?) {
    #if targetEnvironment(simulator)
    arView = ARView(frame: container.bounds)
    #else
    arView = ARView(frame: container.bounds, cameraMode: .nonAR, automaticallyConfigureSession: false)
    #endif
    arView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
    arView.environment.background = .color(UIColor(red: 0.95, green: 0.90, blue: 0.86, alpha: 1))
    container.addSubview(arView)
    arView.scene.addAnchor(root)

    // 竖屏很窄：东西都摆在中间一米多宽的范围里
    camera.camera.fieldOfViewInDegrees = 46
    camera.look(at: [0, 0.70, 0], from: [0, 1.22, 4.3], relativeTo: nil)
    root.addChild(camera)

    buildRoom()
    buildDecor()
    Task { await self.lightRoom() }
    if let modelPath { Task { await self.loadGirl(modelPath) } }
    Task { await self.loadPets(petPaths, plush: plushPath) }
  }

  // ───────── 房间 ─────────
  private func mat(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, rough: Float = 0.85) -> PhysicallyBasedMaterial {
    var m = PhysicallyBasedMaterial()
    m.baseColor = .init(tint: UIColor(red: r, green: g, blue: b, alpha: 1))
    m.roughness = .init(floatLiteral: rough)
    m.metallic = .init(floatLiteral: 0)
    return m
  }

  @discardableResult
  private func box(_ size: SIMD3<Float>, at p: SIMD3<Float>, _ m: RealityKit.Material, radius: Float = 0) -> ModelEntity {
    let e = ModelEntity(mesh: .generateBox(width: size.x, height: size.y, depth: size.z, cornerRadius: radius), materials: [m])
    e.position = p
    root.addChild(e)
    return e
  }

  @discardableResult
  private func ball(_ r: Float, at p: SIMD3<Float>, _ m: RealityKit.Material) -> ModelEntity {
    let e = ModelEntity(mesh: .generateSphere(radius: r), materials: [m])
    e.position = p
    root.addChild(e)
    return e
  }

  private func buildRoom() {
    let wall = mat(0.96, 0.91, 0.87), oak = mat(0.78, 0.62, 0.46, rough: 0.5), white = mat(0.98, 0.97, 0.95, rough: 0.7)
    let pink = mat(0.96, 0.74, 0.78), lilac = mat(0.82, 0.76, 0.93), green = mat(0.36, 0.60, 0.42), clay = mat(0.80, 0.52, 0.40)
    box([4.6, 0.06, 4.0], at: [0, -0.03, 0.3], oak)                                   // 地板
    box([4.6, 4.6, 0.08], at: [0, 2.3, -1.55], wall)                                   // 后墙
    box([0.08, 4.6, 4.0], at: [-2.3, 2.3, 0.3], wall)                                  // 左墙
    box([0.08, 4.6, 4.0], at: [2.3, 2.3, 0.3], wall)                                   // 右墙
    box([4.6, 0.12, 0.04], at: [0, 0.06, -1.5], white)                                 // 踢脚线
    let rug = ModelEntity(mesh: .generateCylinder(height: 0.014, radius: 1.05), materials: [mat(0.97, 0.88, 0.86, rough: 1)])
    rug.position = [0, 0.007, 0.45]
    root.addChild(rug)

    // 窗：一块发亮的面，加窗框和窗台
    let wx: Float = 0.62
    box([1.25, 1.5, 0.02], at: [wx, 1.55, -1.5], UnlitMaterial(color: UIColor(red: 1.0, green: 0.97, blue: 0.90, alpha: 1)))
    for (size, pos) in [([1.37, 0.07, 0.06], [wx, 2.33, -1.48]), ([1.37, 0.07, 0.06], [wx, 0.77, -1.48]), ([0.07, 1.6, 0.06], [wx - 0.65, 1.55, -1.48]),
                        ([0.07, 1.6, 0.06], [wx + 0.65, 1.55, -1.48]), ([0.04, 1.5, 0.05], [wx, 1.55, -1.48]), ([1.25, 0.04, 0.05], [wx, 1.55, -1.48])] as [(SIMD3<Float>, SIMD3<Float>)] {
      box(size, at: pos, white)
    }
    box([1.5, 0.05, 0.24], at: [wx, 0.74, -1.40], white, radius: 0.02)

    // 床
    box([1.55, 0.30, 2.05], at: [-1.42, 0.15, -0.45], mat(0.90, 0.82, 0.76), radius: 0.04)
    box([1.50, 0.20, 2.00], at: [-1.42, 0.40, -0.45], white, radius: 0.08)
    box([1.56, 0.95, 0.10], at: [-1.42, 0.62, -1.47], mat(0.93, 0.80, 0.80), radius: 0.05)
    box([1.54, 0.09, 1.15], at: [-1.42, 0.52, -0.02], pink, radius: 0.04)
    box([0.60, 0.15, 0.38], at: [-1.72, 0.57, -1.15], white, radius: 0.07)
    box([0.60, 0.15, 0.38], at: [-1.08, 0.57, -1.15], lilac, radius: 0.07)

    // 床头柜和台灯
    box([0.44, 0.48, 0.40], at: [-0.42, 0.24, -1.25], oak, radius: 0.03)
    let stem = ModelEntity(mesh: .generateCylinder(height: 0.26, radius: 0.012), materials: [mat(0.85, 0.72, 0.45, rough: 0.3)])
    stem.position = [-0.42, 0.61, -1.25]
    root.addChild(stem)
    ball(0.11, at: [-0.42, 0.80, -1.25], UnlitMaterial(color: UIColor(red: 1.0, green: 0.90, blue: 0.70, alpha: 1)))

    // 绿植
    let pot = ModelEntity(mesh: .generateCylinder(height: 0.26, radius: 0.15), materials: [clay])
    pot.position = [1.15, 0.13, -0.9]
    root.addChild(pot)
    for (r, p) in [(0.22, [1.15, 0.52, -0.9]), (0.17, [1.00, 0.72, -0.85]), (0.19, [1.28, 0.76, -0.95]), (0.15, [1.14, 0.95, -0.88]), (0.12, [1.02, 0.44, -0.78])] as [(Float, SIMD3<Float>)] {
      ball(r, at: p, green)
    }

    // 小坐墩、墙上的画、一串小灯
    let pouf = ModelEntity(mesh: .generateCylinder(height: 0.34, radius: 0.27), materials: [lilac])
    pouf.position = [0.95, 0.17, -0.2]
    root.addChild(pouf)
    for (i, c) in [(0.98, 0.80, 0.70), (0.72, 0.84, 0.95), (0.98, 0.86, 0.60)].enumerated() {
      let x = -1.0 + Float(i) * 0.4
      let y: Float = i == 1 ? 1.95 : 1.85
      box([0.36, 0.46, 0.03], at: [x, y, -1.50], white)
      box([0.28, 0.38, 0.03], at: [x, y, -1.492], UnlitMaterial(color: UIColor(red: c.0, green: c.1, blue: c.2, alpha: 1)))
    }
    for i in 0..<14 {
      let u = Float(i) / 13, x = -1.5 + u * 3.0
      let e = ball(0.022, at: [x, 2.75 - 0.25 * sin(u * .pi), -1.49], UnlitMaterial(color: UIColor(red: 1.0, green: 0.86, blue: 0.55, alpha: 1)))
      lights.append(e)
    }
  }

  // ───────── 商城里的装扮 ─────────
  // 竖屏很窄：后墙上能看到的范围是左右各一米，地毯前沿只有左右各六十厘米，装扮都摆在这个范围里。
  private func group(_ name: String, _ build: (Entity) -> Void) {
    let g = Entity()
    g.isEnabled = false
    build(g)
    root.addChild(g)
    decor[name] = g
  }

  private func buildDecor() {
    group("balloons") { g in
      for (i, c) in [(0.98, 0.62, 0.70), (0.72, 0.80, 0.98), (1.0, 0.86, 0.55)].enumerated() {
        let b = ModelEntity(mesh: .generateSphere(radius: 0.15), materials: [mat(c.0, c.1, c.2, rough: 0.25)])
        b.position = [0.46 + Float(i) * 0.17, 2.25 + (i == 1 ? 0.24 : 0), -1.2 + Float(i) * 0.06]
        b.scale = [1, 1.16, 1]
        g.addChild(b)
        let s = ModelEntity(mesh: .generateCylinder(height: 1.5, radius: 0.003), materials: [mat(0.92, 0.92, 0.92)])
        s.position = b.position - SIMD3<Float>(0, 0.92, 0)
        g.addChild(s)
      }
    }
    group("wall_stars") { g in
      let gold = UnlitMaterial(color: UIColor(red: 1.0, green: 0.84, blue: 0.45, alpha: 1))
      for (x, y, r) in [(-0.34, 1.30, 0.035), (-0.22, 1.62, 0.022), (-0.38, 1.90, 0.028), (-0.16, 2.18, 0.036), (-0.30, 2.40, 0.02), (-0.12, 1.42, 0.018), (-0.42, 1.60, 0.016)] as [(Float, Float, Float)] {
        let s = ModelEntity(mesh: .generateBox(size: r * 2, cornerRadius: r * 0.2), materials: [gold])
        s.position = [x, y, -1.49]
        s.orientation = simd_quatf(angle: .pi / 4, axis: [0, 0, 1])
        s.scale = [1, 1, 0.2]
        g.addChild(s)
      }
    }
    group("moon_lamp") { g in
      let moon = ModelEntity(mesh: .generateSphere(radius: 0.13), materials: [UnlitMaterial(color: UIColor(red: 1.0, green: 0.95, blue: 0.82, alpha: 1))])
      moon.position = [0.36, 0.93, -1.38]
      g.addChild(moon)
      let base = ModelEntity(mesh: .generateCylinder(height: 0.04, radius: 0.07), materials: [mat(0.78, 0.62, 0.46, rough: 0.5)])
      base.position = [0.36, 0.785, -1.38]
      g.addChild(base)
      let glow = PointLight()
      glow.light.intensity = 2600
      glow.light.color = UIColor(red: 1.0, green: 0.90, blue: 0.72, alpha: 1)
      glow.light.attenuationRadius = 2.2
      glow.position = [0.36, 0.95, -1.2]
      g.addChild(glow)
    }
    group("pet_bed") { g in
      let rim = ModelEntity(mesh: .generateCylinder(height: 0.10, radius: 0.27), materials: [mat(0.96, 0.74, 0.78, rough: 1)])
      rim.position = [-0.36, 0.05, 1.12]
      g.addChild(rim)
      let pad = ModelEntity(mesh: .generateCylinder(height: 0.11, radius: 0.21), materials: [mat(0.99, 0.95, 0.92, rough: 1)])
      pad.position = [-0.36, 0.055, 1.12]
      g.addChild(pad)
    }
    group("pet_bowl") { g in
      let bowl = ModelEntity(mesh: .generateCylinder(height: 0.05, radius: 0.08), materials: [mat(0.72, 0.84, 0.95, rough: 0.3)])
      bowl.position = [0.10, 0.025, 1.36]
      g.addChild(bowl)
      let food = ModelEntity(mesh: .generateCylinder(height: 0.052, radius: 0.062), materials: [mat(0.62, 0.42, 0.26)])
      food.position = [0.10, 0.026, 1.36]
      g.addChild(food)
    }
    group("pet_ball") { g in
      let ball = ModelEntity(mesh: .generateSphere(radius: 0.055), materials: [mat(0.95, 0.38, 0.36, rough: 0.4)])
      ball.position = [0.42, 0.055, 1.38]
      g.addChild(ball)
    }
  }

  /// 只显示传进来的这几件装扮
  func setDecor(_ names: Set<String>) {
    for (name, g) in decor { g.isEnabled = names.contains(name) }
  }

  private func lightRoom() async {
    let sun = DirectionalLight()
    sun.light.intensity = 2400
    sun.light.color = UIColor(red: 1.0, green: 0.93, blue: 0.82, alpha: 1)
    sun.shadow = DirectionalLightComponent.Shadow(maximumDistance: 9, depthBias: 3)
    sun.look(at: [0, 0.6, 0.2], from: [2.4, 3.4, 2.2], relativeTo: nil)
    root.addChild(sun)
    let lamp = PointLight()
    lamp.light.intensity = 9000
    lamp.light.attenuationRadius = 3.5
    lamp.light.color = UIColor(red: 1.0, green: 0.80, blue: 0.55, alpha: 1)
    lamp.position = [-0.42, 0.95, -1.05]
    root.addChild(lamp)
    // 环境光：一张代码画的暖色全景图
    let size = CGSize(width: 256, height: 128)
    let img = UIGraphicsImageRenderer(size: size).image { ctx in
      let colors = [UIColor(red: 1.0, green: 0.97, blue: 0.93, alpha: 1).cgColor, UIColor(red: 0.96, green: 0.88, blue: 0.82, alpha: 1).cgColor, UIColor(red: 0.74, green: 0.62, blue: 0.52, alpha: 1).cgColor] as CFArray
      let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 0.5, 1])!
      ctx.cgContext.drawLinearGradient(g, start: .zero, end: CGPoint(x: 0, y: size.height), options: [])
    }
    if let cg = img.cgImage, let env = try? await EnvironmentResource(equirectangular: cg, withName: "room") {
      arView.environment.lighting.resource = env
      arView.environment.lighting.intensityExponent = 0.6
    }
  }

  // ───────── 形象 ─────────
  private func loadGirl(_ path: String) async {
    do {
      let loader = try VRMEntityLoader(withURL: URL(fileURLWithPath: path))
      let model = try await loader.loadEntity()
      model.position = [0, 0, 0.35]
      // VRM 0.x 的模型背对 +Z，转过来面向镜头
      baseYaw = model.frontDirection.z < 0 ? .pi : 0
      model.orientation = simd_quatf(angle: baseYaw, axis: [0, 1, 0])
      root.addChild(model)
      girl = model
      for bone in [HumanoidBone.leftUpperArm, .rightUpperArm, .leftLowerArm, .rightLowerArm, .spine, .chest, .neck, .head, .hips] {
        if let node = model.humanoid.node(for: bone) { rest[bone] = node.orientation }
      }
      model.lookAtTarget = .position(camera.position(relativeTo: nil))
      tick = arView.scene.subscribe(to: SceneEvents.Update.self) { [weak self] event in self?.animate(Float(event.deltaTime)) }
    } catch {
      NSLog("[yuanjing] 形象加载失败：\(error)")
    }
  }

  // ───────── 宠物 ─────────
  /// 小狗是带骨骼动画的普通 GLB，循环播放待机动作；贵宾是静态模型，当玩偶放在床上。
  private func loadPets(_ paths: [String], plush: String?) async {
    let spots: [(SIMD3<Float>, Float)] = [([0.48, 0, 0.75], -0.45), ([-0.5, 0, 0.6], 0.5)]
    for (i, path) in paths.prefix(spots.count).enumerated() {
      guard let pet = try? await GLTFEntityLoader(withURL: URL(fileURLWithPath: path)).loadEntity() else { continue }
      let holder = Entity()
      holder.position = spots[i].0
      holder.orientation = simd_quatf(angle: spots[i].1, axis: [0, 1, 0])
      holder.scale = SIMD3<Float>(repeating: 0.105)
      holder.addChild(pet)
      root.addChild(holder)
      pets.append(pet)
      petHolders.append(holder)
      playPet(pet, i == 0 ? "Idle" : "Idle_2")
    }
    if let plush, let toy = try? await GLTFEntityLoader(withURL: URL(fileURLWithPath: plush)).loadEntity() {
      let holder = Entity()
      holder.position = [-0.95, 0.83, -0.35]
      holder.orientation = simd_quatf(angle: 0.5, axis: [0, 1, 0])
      holder.scale = SIMD3<Float>(repeating: 0.0042)
      holder.addChild(toy)
      root.addChild(holder)
    }
  }

  /// 柴犬隔一会儿在地毯上换个位置：转向目标、走过去、停下继续待机。
  private func wander(_ dt: Float, _ t: Float) {
    guard let dog = petHolders.first, let pet = pets.first else { return }
    petBusy = max(0, petBusy - dt)
    if let target = walkTarget {
      let delta = target - dog.position
      let dist = simd_length(delta)
      if dist < 0.03 {
        walkTarget = nil
        nextWalk = t + Float.random(in: 5...10)
        playPet(pet, Bool.random() ? "Idle" : "Idle_2")
        // 停下后转回来看镜头
        dog.move(to: Transform(scale: dog.scale, rotation: simd_quatf(angle: Float.random(in: -0.5...0.5), axis: [0, 1, 0]), translation: dog.position), relativeTo: dog.parent, duration: 0.6)
      } else {
        let step = min(dist, 0.32 * dt)
        dog.position += delta / dist * step
        let yaw = atan2(delta.x, delta.z)
        dog.orientation = simd_slerp(dog.orientation, simd_quatf(angle: yaw, axis: [0, 1, 0]), min(1, dt * 6))
      }
    } else if t > nextWalk, petBusy <= 0 {
      // 只在形象右前方的地毯上活动：不穿过她，也不走出竖屏的画面
      walkTarget = [Float.random(in: 0.22...0.58), 0, Float.random(in: 0.7...1.15)]
      playPet(pet, "Walk")
    }
  }

  private func playPet(_ pet: GLTFEntity, _ name: String, loops: Bool = true) {
    guard let index = pet.animations.firstIndex(where: { $0.name == name }) else { return }
    pet.stopAnimations()
    _ = try? pet.playAnimation(at: index, loops: loops)
  }

  private func set(_ bone: HumanoidBone, _ delta: simd_quatf) {
    guard let node = girl?.humanoid.node(for: bone), let base = rest[bone] else { return }
    node.orientation = base * delta
  }

  private func q(_ deg: Float, _ axis: SIMD3<Float>) -> simd_quatf { simd_quatf(angle: deg * .pi / 180, axis: axis) }

  /// 每帧摆姿势：手臂放下、呼吸、重心轻晃、眨眼，再叠加挥手和转圈。
  private func animate(_ dt: Float) {
    guard let model = girl else { return }
    clock += dt
    let t = clock
    let breath = sin(t * 1.5)
    set(.hips, q(2.2 * sin(t * 0.6), [0, 0, 1]) * q(3 * sin(t * 0.23), [0, 1, 0]))
    set(.spine, q(1.2 * breath, [1, 0, 0]))
    set(.chest, q(1.0 * breath + 1, [1, 0, 0]))
    set(.neck, q(3 * sin(t * 0.45), [0, 0, 1]))
    set(.head, q(2.5 * sin(t * 0.7 + 1), [1, 0, 0]) * q(4 * sin(t * 0.33), [0, 1, 0]))

    var rightUp: Float = 0, rightBend: Float = 0
    if wave >= 0 {
      wave += dt
      let k = min(wave / 0.4, 1) * (1 - max(0, min((wave - 2.0) / 0.5, 1)))
      rightUp = 150 * k
      rightBend = (40 + 28 * sin(wave * 11)) * k
      if wave > 2.5 { wave = -1 }
    }
    // 手臂自然垂下：略向前收、手肘微弯，左右不完全对称，随呼吸轻轻动
    let sway = sin(t * 0.6)
    set(.leftUpperArm, q(74 + 1.5 * breath + sway, [0, 0, 1]) * q(10, [0, 1, 0]))
    set(.rightUpperArm, q(-(71 + 1.5 * breath - sway) + rightUp, [0, 0, 1]) * q(-12, [0, 1, 0]))
    set(.leftLowerArm, q(22 + 3 * sin(t * 0.8), [0, 1, 0]))
    set(.rightLowerArm, q(-16 - 3 * sin(t * 0.7 + 1) - rightBend, [0, 1, 0]))

    if blink < 0, t > nextBlink { blink = 0 }
    if blink >= 0 {
      blink += dt
      let v = sin(min(blink / 0.16, 1) * .pi)
      model.setExpression(value: CGFloat(v), for: .preset(.blink))
      if blink > 0.16 { blink = -1; nextBlink = t + Float.random(in: 2.2...5.0) }
    }
    // 平时不挂表情（这个模型的「开心」是眯眼笑，常挂着像没睡醒），做动作时才笑
    smile = max(0, smile - dt * 0.45)
    model.setExpression(value: CGFloat(min(smile, 1)), for: .preset(.happy))

    if spin >= 0 {
      spin += dt
      let k = min(spin / 1.4, 1), e = k * k * (3 - 2 * k)
      model.orientation = simd_quatf(angle: baseYaw + e * 2 * .pi, axis: [0, 1, 0])
      if spin > 1.4 { spin = -1; model.orientation = simd_quatf(angle: baseYaw, axis: [0, 1, 0]) }
    }
    model.invalidateSkinPose()
    wander(dt, t)
    for (i, e) in lights.enumerated() {
      e.scale = SIMD3<Float>(repeating: 1 + 0.25 * sin(t * 2.2 + Float(i) * 0.9))
    }
  }

  func perform(_ name: String) {
    switch name {
    case "wave": wave = 0; smile = 1.6; AudioDirector.shared.play("sparkle", volume: 0.5)
    case "smile": smile = 1
    case "spin": spin = 0; smile = 1.2; AudioDirector.shared.play("whoosh", volume: 0.5)
    case "pet":
      smile = 1.6
      AudioDirector.shared.play("step_5", volume: 0.8)
      DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) { AudioDirector.shared.play("step_7", volume: 0.8) }
      walkTarget = nil
      petBusy = 3
      nextWalk = clock + 6
      for (i, pet) in pets.enumerated() {
        playPet(pet, i == 0 ? "Jump_ToIdle" : "Eating", loops: false)
        DispatchQueue.main.asyncAfter(deadline: .now() + (i == 0 ? 1.4 : 2.7)) { [weak self] in self?.playPet(pet, i == 0 ? "Idle" : "Idle_2") }
      }
    default: break
    }
    Haptics.shared.play("tick")
  }
}
