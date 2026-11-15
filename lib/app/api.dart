import 'dart:async';
import 'dart:convert';
import 'dart:io';

/// 后端地址。模拟器连本机：http://127.0.0.1:8787；真机或上线时编译加 --dart-define=YJ_API=https://...
const apiBase = String.fromEnvironment('YJ_API', defaultValue: 'http://127.0.0.1:8787');

/// 接口出错：[message] 可以直接给用户看；[status] 为 0 表示连不上服务器。
class ApiError implements Exception {
  final int status;
  final String message;
  const ApiError(this.status, this.message);

  bool get offline => status == 0;

  @override
  String toString() => message;
}

/// 和后端说话。只用 dart:io，不引第三方包。返回解析好的 JSON。
class Api {
  String? token;
  final _http = HttpClient()..connectionTimeout = const Duration(seconds: 6);

  /// 图片地址：服务器上的（/files/...）补全成完整地址
  static String fileUrl(String path) => path.startsWith('http') ? path : '$apiBase$path';

  Future<dynamic> get(String path) => _send('GET', path);
  Future<dynamic> post(String path, [Object? body]) => _send('POST', path, body);
  Future<dynamic> put(String path, [Object? body]) => _send('PUT', path, body);
  Future<dynamic> patch(String path, [Object? body]) => _send('PATCH', path, body);
  Future<dynamic> delete(String path) => _send('DELETE', path);

  Future<dynamic> _send(String method, String path, [Object? body]) async {
    try {
      final req = await _http.openUrl(method, Uri.parse('$apiBase$path')).timeout(const Duration(seconds: 8));
      if (token != null) req.headers.set('Authorization', 'Bearer $token');
      if (body != null) {
        req.headers.contentType = ContentType.json;
        req.add(utf8.encode(jsonEncode(body)));
      }
      return await _read(await req.close().timeout(const Duration(seconds: 25)));
    } on ApiError {
      rethrow;
    } on SocketException {
      throw const ApiError(0, '连不上服务器，检查一下网络');
    } on TimeoutException {
      throw const ApiError(0, '服务器没有回应，稍后再试');
    } on HttpException {
      throw const ApiError(0, '连不上服务器，检查一下网络');
    }
  }

  Future<dynamic> _read(HttpClientResponse res) async {
    final text = await utf8.decodeStream(res);
    final data = text.isEmpty ? null : jsonDecode(text);
    if (res.statusCode >= 400) {
      final detail = data is Map ? data['detail'] : null;
      throw ApiError(res.statusCode, detail is String ? detail : '出了点问题（${res.statusCode}）');
    }
    return data;
  }

  /// 把服务器上的一个文件下载到本机路径（已存在就不下）
  Future<void> download(String url, String path) async {
    final file = File(path);
    if (file.existsSync() && file.lengthSync() > 0) return;
    try {
      final req = await _http.getUrl(Uri.parse(fileUrl(url))).timeout(const Duration(seconds: 8));
      final res = await req.close().timeout(const Duration(seconds: 20));
      if (res.statusCode != 200) throw ApiError(res.statusCode, '下载失败');
      file.parent.createSync(recursive: true);
      final tmp = File('$path.part');
      await res.pipe(tmp.openWrite());
      tmp.renameSync(path);
    } on SocketException {
      throw const ApiError(0, '连不上服务器');
    } on TimeoutException {
      throw const ApiError(0, '服务器没有回应');
    }
  }

  /// 上传一张图片，返回服务器上的地址（/files/...）
  Future<String> upload(String filePath) async {
    try {
      final bytes = await File(filePath).readAsBytes();
      const boundary = '----yuanjing-boundary';
      final req = await _http.postUrl(Uri.parse('$apiBase/files')).timeout(const Duration(seconds: 8));
      if (token != null) req.headers.set('Authorization', 'Bearer $token');
      req.headers.set('Content-Type', 'multipart/form-data; boundary=$boundary');
      req.add(utf8.encode('--$boundary\r\nContent-Disposition: form-data; name="file"; filename="photo.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'));
      req.add(bytes);
      req.add(utf8.encode('\r\n--$boundary--\r\n'));
      final data = await _read(await req.close().timeout(const Duration(seconds: 60)));
      return (data as Map)['url'] as String;
    } on ApiError {
      rethrow;
    } on SocketException {
      throw const ApiError(0, '图片没传上去，检查一下网络');
    } on TimeoutException {
      throw const ApiError(0, '图片没传上去，稍后再试');
    }
  }
}
