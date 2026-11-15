// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "yuanjing_engine",
    platforms: [
        .iOS("15.0")
    ],
    products: [
        .library(name: "yuanjing-engine", targets: ["yuanjing_engine"])
    ],
    dependencies: [
        .package(name: "FlutterFramework", path: "../FlutterFramework"),
        // 动漫形象（VRM）的加载和渲染：表情、头发物理、动作重定向。渲染部分要 iOS 18。
        // 本地副本（0.11.0），改了一行让 Xcode 16.4 的 Swift 6.1 能编译。升级到 Xcode 26 后可换回官方仓库。
        .package(name: "VRMKit", path: "ThirdParty/VRMKit"),
    ],
    targets: [
        .target(
            name: "yuanjing_engine",
            dependencies: [
                .product(name: "FlutterFramework", package: "FlutterFramework"),
                .product(name: "VRMKit", package: "VRMKit"),
                .product(name: "VRMRealityKit", package: "VRMKit"),
            ],
            resources: []
        )
    ]
)
