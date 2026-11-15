# 本地副本：VRMKit 0.11.0

来源 https://github.com/tattn/VRMKit （MIT）。放本地副本而不是直接依赖官方仓库，是因为官方代码用了 Swift 6.2 的写法，
这台机器的 Xcode 16.4（Swift 6.1）编不过。升级到 Xcode 26 后，可以把 `Package.swift` 里的依赖换回官方仓库，
但第 3 条改动要带过去或者换一个标签正确的形象文件。

相对官方 0.11.0 的改动只有三处：

1. `Sources/VRMRealityKit/Extensions/Entity+VRMRuntimeNode.swift`：`@MainActor` 一致性改成 `@preconcurrency`（Swift 6.1 兼容）。
2. `Sources/VRMRealityKit/Loading/GLTFLoadQueue.swift`：`run` 的闭包参数加 `@MainActor`（Swift 6.1 兼容）。
3. `Sources/VRMKit/MToon/VRM0MToonProperty.swift`：材质的 RenderType 标成 Opaque 但带透明关键字时，以关键字为准。
   不改的话，VRoid 样例形象的虹膜、睫毛层会把眼睛盖成黑色。

另外删掉了 Tests、Example 目录和 `Package.swift` 里的测试目标。
