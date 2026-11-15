using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

/// 工程的一次性设置，全部从命令行执行，不需要打开编辑器：
///   Unity -batchmode -quit -projectPath <工程> -buildTarget iOS -executeMethod SanctuarySetup.Setup
public static class SanctuarySetup
{
    const string SettingsDir = "Assets/Settings";

    [MenuItem("Yuanjing/1 工程设置")]
    public static void Setup()
    {
        Directory.CreateDirectory(SettingsDir);
        Directory.CreateDirectory("Assets/Scenes");

        // 渲染管线：URP
        var urpPath = SettingsDir + "/URP.asset";
        var urp = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(urpPath);
        if (urp == null)
        {
            var rendererData = ScriptableObject.CreateInstance<UniversalRendererData>();
            AssetDatabase.CreateAsset(rendererData, SettingsDir + "/Renderer.asset");
            rendererData.postProcessData = AssetDatabase.LoadAssetAtPath<PostProcessData>("Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset");
            if (rendererData.postProcessData == null) Debug.LogError("[yuanjing] 找不到后期处理的默认数据");
            EditorUtility.SetDirty(rendererData);
            urp = UniversalRenderPipelineAsset.Create(rendererData);
            AssetDatabase.CreateAsset(urp, urpPath);
        }
        GraphicsSettings.defaultRenderPipeline = urp;
        for (int i = 0; i < QualitySettings.names.Length; i++)
        {
            QualitySettings.SetQualityLevel(i, false);
            QualitySettings.renderPipeline = urp;
        }

        // 播放器设置
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.companyName = "Yuanjing";
        PlayerSettings.productName = "Sanctuary";
        PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.iOS, "app.yuanjing.sanctuary");
        PlayerSettings.SetScriptingBackend(NamedBuildTarget.iOS, ScriptingImplementation.IL2CPP);
        PlayerSettings.iOS.targetOSVersionString = "15.0";
        ApplySdk();

        AssetDatabase.SaveAssets();
        Debug.Log("[yuanjing] 工程设置完成，渲染管线：" + GraphicsSettings.defaultRenderPipeline);
    }

    /// 命令行带 -simulator 就按模拟器导出，否则按真机
    static void ApplySdk()
    {
        bool sim = System.Array.IndexOf(System.Environment.GetCommandLineArgs(), "-simulator") >= 0;
        PlayerSettings.iOS.sdkVersion = sim ? iOSSdkVersion.SimulatorSDK : iOSSdkVersion.DeviceSDK;
        // 苹果芯片的 Mac 上，模拟器要 arm64 的库
        PlayerSettings.iOS.simulatorSdkArchitecture = AppleMobileArchitectureSimulator.Universal;
        // 正式的包：不带调试控制台
        EditorUserBuildSettings.development = false;
        // 不裁引擎代码：裁掉以后人物动画在手机上会丢
        PlayerSettings.stripEngineCode = false;
        // 人物蒙皮用显卡算（默认）
        PlayerSettings.meshDeformation = MeshDeformation.GPU;
        // 着色器版本严格匹配：缺了就显示成报错的颜色，不要悄悄换成一个「差不多」的版本
        PlayerSettings.strictShaderVariantMatching = true;
        // 开发阶段：代码生成选体积小、编译快的
        PlayerSettings.SetIl2CppCodeGeneration(NamedBuildTarget.iOS, Il2CppCodeGeneration.OptimizeSize);
    }

    [MenuItem("Yuanjing/2 生成测试场景")]
    public static void BuildTestScene()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var camGo = new GameObject("Main Camera");
        camGo.tag = "MainCamera";
        var cam = camGo.AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0.05f, 0.06f, 0.10f);
        camGo.transform.position = new Vector3(0, 1.2f, -4f);
        camGo.transform.LookAt(Vector3.zero);
        camGo.AddComponent<UniversalAdditionalCameraData>();

        var lightGo = new GameObject("Sun");
        var light = lightGo.AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1.4f;
        light.color = new Color(1f, 0.92f, 0.8f);
        lightGo.transform.rotation = Quaternion.Euler(40f, -30f, 0f);

        var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cube.name = "TestCube";
        cube.AddComponent<Spin>();
        var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
        mat.SetColor("_BaseColor", new Color(0.95f, 0.72f, 0.3f));
        mat.SetFloat("_Metallic", 0.8f);
        mat.SetFloat("_Smoothness", 0.7f);
        Directory.CreateDirectory("Assets/Materials");
        AssetDatabase.CreateAsset(mat, "Assets/Materials/Test.mat");
        cube.GetComponent<MeshRenderer>().sharedMaterial = mat;

        new GameObject("Bridge").AddComponent<Bridge>();

        const string path = "Assets/Scenes/Main.unity";
        EditorSceneManager.SaveScene(scene, path);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(path, true) };
        AssetDatabase.SaveAssets();
        Debug.Log("[yuanjing] 测试场景已生成");
    }

    /// 设置 + 测试场景 + 导出到 Flutter 工程（-exportPath 指向 ios/unityLibrary）
    public static void SetupAndExportTest()
    {
        Setup();
        BuildTestScene();
        ApplySdk();
        ProjectExporterBatchmode.ExportProjectIos();
    }
}
