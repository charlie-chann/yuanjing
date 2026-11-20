using UnityEngine;

/// 和 Flutter 之间收发消息的入口。场景里有一个名叫 "Bridge" 的物体挂着它，
/// Flutter 用 sendToUnity("Bridge", "OnMessage", json) 发过来，这里用 SendToFlutter.Send(json) 发回去。
public class Bridge : MonoBehaviour
{
    public static Bridge Instance { get; private set; }
    public static event System.Action<string> Received;

    void Awake()
    {
        Instance = this;
        // 出错时不要在画面上弹出红字的调试控制台
        Debug.developerConsoleEnabled = false;
        Debug.developerConsoleVisible = false;
        // 斜着看的贴图（地砖、屋瓦）要清楚、走动时不闪：强制打开各向异性过滤，贴图用最高一档。
        // 不切换画质档：每档自带一个抗锯齿倍数，切过去会和渲染设置里的对不上，模拟器上直接报错
        QualitySettings.anisotropicFiltering = AnisotropicFiltering.ForceEnable;
        QualitySettings.globalTextureMipmapLimit = 0;
        if (UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline is UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset urp)
            QualitySettings.antiAliasing = urp.msaaSampleCount > 1 ? urp.msaaSampleCount : 0;
    }

    void Start()
    {
        Send("{\"type\":\"ready\"}");
    }

    // 由 Flutter 调用
    public void OnMessage(string json)
    {
        Received?.Invoke(json);
    }

    /// 发给 Flutter 的每一条（测试里用来看发了什么）
    public static event System.Action<string> Sent;

    public static void Send(string json)
    {
        Sent?.Invoke(json);
        SendToFlutter.Send(json);
    }
}
