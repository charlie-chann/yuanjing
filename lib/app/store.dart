import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/widgets.dart';
import 'package:yuanjing_engine/yuanjing_engine.dart';

import 'api.dart';
import 'skin.dart';

export 'api.dart' show ApiError;

/// 一条金币流水
class CoinEntry {
  final int amount;
  final String what;
  final int ts;
  const CoinEntry(this.amount, this.what, this.ts);
}

/// 金币奖励规则：(每次多少, 每天最多几次, 流水里写什么)。只用来显示，发放以服务端 server/app/catalog.py 为准。
const coinRules = <String, (int, int, String)>{
  'checkin': (10, 1, '每日签到'),
  'wish': (5, 1, '完成今日许愿'),
  'post': (5, 1, '发布朋友圈'),
  'diary': (5, 1, '写感恩日记'),
  'friend': (2, 5, '添加好友'),
  'like': (1, 10, '给别人点赞'),
  'praise': (2, 5, '给别人夸夸'),
  'liked': (2, 10, '被点赞'),
  'praised': (2, 10, '被夸夸'),
};

/// 全应用的数据。
///
/// 以服务器为准：启动时用设备号登录，拉一遍全部数据；之后每个改动都调接口，用返回的结果更新。
/// 本机的 yuanjing.json 是缓存：没网时先显示上次的样子。
/// 没网时也能做的事（许愿、写终点密码、愿景板关键词、肯定语、宠物、改资料）先记在本机，
/// 放进「待上传」，下次连上服务器时按顺序补发；金币、商城、广场、好友必须在线。
class AppStore extends ChangeNotifier {
  final api = Api();
  String? dir;
  bool ready = false;

  /// 现在连得上服务器
  bool online = false;
  String? deviceId;

  int userId = 0;
  int coins = 0;
  final List<CoinEntry> coinLog = [];
  int streak = 0;
  bool checkedIn = false;
  bool member = false;
  String skinId = 'gold';
  String name = '愿境旅人';
  String sign = '我正在路上。';
  String? avatar;
  String title = '把日子过成喜欢样子的人';
  String titleLine = '我过着自己选择的生活。';

  /// 形象模式：q、anime、real、self；相貌是固定原生的，还是跟着外貌肯定语动态显化
  String lookMode = 'anime';
  bool lookDynamic = false;

  /// 心愿 {id, scene, text, ts}，新的在前
  final List<Map<String, dynamic>> wishes = [];

  /// 愿景板 {id, text, scene, photo}
  final List<Map<String, dynamic>> vision = [];

  /// 终点密码：分类 → 一段话
  final Map<String, String> destiny = {};
  int destinyTs = 0;

  /// 我自己写的肯定语 {id, text}
  final List<Map<String, dynamic>> affirmations = [];

  /// 宠物 {id, name, kind, photo}
  final List<Map<String, dynamic>> pets = [];
  final Set<String> owned = {};
  final Set<String> equipped = {};

  /// 湖心小寺的背包：钓的鱼、买的口粮、小动物送的收藏品
  /// {id, kind: fish|food|gift, name, about, rarity, count, sell, feed: 喂它基础涨多少亲密度（0 不能喂）}
  final List<Map<String, dynamic>> bag = [];

  /// 小动物册（GET /pets/gifts 的结果）：上次取到的，没网时先看这份。没取过是 null
  Map<String, dynamic>? petBookCache;

  /// 钓鱼图鉴（GET /fishing 的结果）：上次取到的
  Map<String, dynamic>? fishBookCache;

  /// 好友和收到的好友申请：{id, name, sign, avatar, title} / {id, user, ts}
  final List<Map<String, dynamic>> friends = [];
  final List<Map<String, dynamic>> requests = [];

  /// 今天各项奖励已经发了几次
  final Map<String, int> daily = {};

  /// 输入框的草稿：哪个输入框 → 写到一半的字（只存本机）
  final Map<String, String> drafts = {};

  /// 没网时记下来、等连上再补发的改动：{m, p, b}
  final List<Map<String, dynamic>> _outbox = [];

  /// 接后端之前存在本机的旧数据，第一次登录时搬上去
  Map<String, dynamic>? _legacy;
  Timer? _saver;
  final _destinyTimers = <String, Timer>{};

  Skin get skin => skins.firstWhere((s) => s.id == skinId, orElse: () => skins.first);
  int count(String key) => daily[key] ?? 0;

  static String day([DateTime? t]) {
    final d = t ?? DateTime.now();
    return '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
  }

  // ───────── 启动 ─────────

  Future<void> load() async {
    dir = await YuanjingFiles.docsDir();
    try {
      final file = File('$dir/yuanjing.json');
      if (dir != null && file.existsSync()) _readCache(jsonDecode(file.readAsStringSync()) as Map<String, dynamic>);
    } catch (e) {
      debugPrint('缓存读不出来，从头开始：$e');
    }
    deviceId ??= _newId();
    ready = true;
    notifyListeners();
    unawaited(connect());
  }

  static String _newId() {
    final r = Random.secure();
    return List.generate(32, (_) => r.nextInt(16).toRadixString(16)).join();
  }

  /// 登录、补发没网时的改动、拉全部数据。启动时和从后台回来时调。
  Future<bool> connect() async {
    try {
      final r = await api.post('/auth/device', {'device_id': deviceId});
      api.token = r['token'] as String;
      if (r['new'] == true && _legacy != null) await _importLegacy();
      _legacy = null;
      await _flush();
      _apply(await api.get('/me/state') as Map<String, dynamic>);
      online = true;
    } on ApiError catch (e) {
      debugPrint('连服务器失败：$e');
      online = false;
    }
    touch();
    return online;
  }

  Future<void> refresh() async {
    try {
      _apply(await api.get('/me/state') as Map<String, dynamic>);
      online = true;
      touch();
    } on ApiError {
      online = false;
      notifyListeners();
    }
  }

  void _apply(Map<String, dynamic> s) {
    _applyUser(s['user'] as Map<String, dynamic>);
    List<Map<String, dynamic>> maps(String k) => [for (final m in (s[k] as List? ?? [])) Map<String, dynamic>.from(m as Map)];
    wishes
      ..clear()
      ..addAll(maps('wishes'));
    vision
      ..clear()
      ..addAll(maps('vision'));
    // 正在输入、还没发出去的终点密码不能被覆盖
    final typing = {for (final k in _destinyTimers.keys) k: destiny[k]};
    destiny
      ..clear()
      ..addAll((s['destiny'] as Map).cast<String, String>());
    for (final e in typing.entries) {
      if (e.value == null) {
        destiny.remove(e.key);
      } else {
        destiny[e.key] = e.value!;
      }
    }
    destinyTs = s['destiny_ts'] as int? ?? 0;
    affirmations
      ..clear()
      ..addAll(maps('affirmations'));
    pets
      ..clear()
      ..addAll(maps('pets'));
    owned
      ..clear()
      ..addAll((s['owned'] as List).cast<String>());
    equipped
      ..clear()
      ..addAll((s['equipped'] as List).cast<String>());
    if (s['bag'] is List) _applyBag(s['bag'] as List);
    if (s['pet_book'] is Map) petBookCache = Map<String, dynamic>.from(s['pet_book'] as Map);
    if (s['fish_book'] is Map) fishBookCache = Map<String, dynamic>.from(s['fish_book'] as Map);
    friends
      ..clear()
      ..addAll(maps('friends'));
    requests
      ..clear()
      ..addAll(maps('requests'));
    daily
      ..clear()
      ..addAll((s['daily'] as Map).cast<String, int>());
    coinLog
      ..clear()
      ..addAll([for (final c in s['coin_log'] as List) CoinEntry(c['amount'] as int, c['what'] as String, c['ts'] as int)]);
  }

  void _applyUser(Map<String, dynamic> u) {
    userId = u['id'] as int;
    name = u['name'] as String;
    sign = u['sign'] as String;
    avatar = u['avatar'] as String?;
    coins = u['coins'] as int;
    member = u['member'] as bool;
    skinId = u['skin'] as String;
    lookMode = u['look_mode'] as String;
    lookDynamic = u['look_dynamic'] as bool;
    streak = u['streak'] as int;
    checkedIn = u['checked_in'] as bool;
    title = u['title'] as String;
    titleLine = (u['title_line'] as String?) ?? '';
  }

  // ───────── 本机缓存 ─────────

  void _readCache(Map<String, dynamic> j) {
    List<Map<String, dynamic>> maps(String k) => [for (final m in (j[k] as List? ?? [])) Map<String, dynamic>.from(m as Map)];
    deviceId = j['deviceId'] as String?;
    drafts.addAll((j['drafts'] as Map? ?? {}).cast<String, String>());
    _outbox.addAll(maps('outbox'));
    if (j['v'] != 2) {
      // 接后端之前的存档：留着第一次登录时搬上去
      if (['wishes', 'posts', 'vision', 'affirmations'].any((k) => (j[k] as List?)?.isNotEmpty ?? false) || ((j['destiny'] as Map?)?.isNotEmpty ?? false)) {
        _legacy = j;
      }
      return;
    }
    if (j['state'] is Map) _apply(Map<String, dynamic>.from(j['state'] as Map));
  }

  Map<String, dynamic> _stateJson() => {
        'user': {
          'id': userId,
          'name': name,
          'sign': sign,
          'avatar': avatar,
          'coins': coins,
          'member': member,
          'skin': skinId,
          'look_mode': lookMode,
          'look_dynamic': lookDynamic,
          'streak': streak,
          'checked_in': checkedIn,
          'title': title,
          'title_line': titleLine,
        },
        'wishes': wishes,
        'vision': vision,
        'destiny': destiny,
        'destiny_ts': destinyTs,
        'affirmations': affirmations,
        'pets': pets,
        'owned': owned.toList(),
        'equipped': equipped.toList(),
        'bag': bag,
        'pet_book': ?petBookCache,
        'fish_book': ?fishBookCache,
        'friends': friends,
        'requests': requests,
        'daily': daily,
        'coin_log': [for (final c in coinLog.take(60)) {'amount': c.amount, 'what': c.what, 'ts': c.ts}],
      };

  /// 刷新界面，稍后存缓存
  void touch({bool notify = true}) {
    if (notify) notifyListeners();
    _saver?.cancel();
    _saver = Timer(const Duration(milliseconds: 400), () {
      if (dir == null) return;
      try {
        File('$dir/yuanjing.json').writeAsStringSync(jsonEncode({'v': 2, 'deviceId': deviceId, 'drafts': drafts, 'outbox': _outbox, 'state': _stateJson()}));
      } catch (e) {
        debugPrint('缓存写不进去：$e');
      }
    });
  }

  void saveDraft(String key, String text) {
    if (text.isEmpty) {
      drafts.remove(key);
    } else {
      drafts[key] = text;
    }
    touch(notify: false);
  }

  // ───────── 没网时的待上传 ─────────

  /// 调一个「没网也能先记下」的接口：失败且是没网，就放进待上传，返回 null
  Future<dynamic> _send(String m, String path, Object? body, {String? replaceKey}) async {
    try {
      final r = await switch (m) { 'POST' => api.post(path, body), 'PUT' => api.put(path, body), 'PATCH' => api.patch(path, body), _ => api.delete(path) };
      online = true;
      return r;
    } on ApiError catch (e) {
      if (!e.offline) rethrow;
      online = false;
      if (replaceKey != null) _outbox.removeWhere((o) => o['k'] == replaceKey);
      _outbox.add({'m': m, 'p': path, 'b': body, 'k': replaceKey});
      touch();
      return null;
    }
  }

  Future<void> _flush() async {
    while (_outbox.isNotEmpty) {
      final o = _outbox.first;
      try {
        await switch (o['m']) { 'POST' => api.post(o['p'] as String, o['b']), 'PUT' => api.put(o['p'] as String, o['b']), 'PATCH' => api.patch(o['p'] as String, o['b']), _ => api.delete(o['p'] as String) };
      } on ApiError catch (e) {
        if (e.offline) rethrow;
        debugPrint('待上传的一条被拒绝，丢掉：${o['p']} $e');
      }
      _outbox.removeAt(0);
    }
  }

  Future<void> _importLegacy() async {
    final j = _legacy!;
    final visionItems = <Map<String, dynamic>>[];
    for (final v in (j['vision'] as List? ?? [])) {
      final m = Map<String, dynamic>.from(v as Map);
      final local = photoPath(m['photo'] as String?);
      String? url;
      if (local != null && File(local).existsSync()) {
        try {
          url = await api.upload(local);
        } on ApiError {
          url = null;
        }
      }
      visionItems.add({'text': m['text'] ?? '', 'scene': m['scene'], 'photo': url});
    }
    final affirm = [for (final a in (j['affirmations'] as List? ?? [])) a is String ? a : (a as Map)['text'] as String];
    try {
      await api.post('/me/import', {
        'wishes': j['wishes'] ?? [],
        'vision': visionItems,
        'destiny': j['destiny'] ?? {},
        'affirmations': affirm,
        'pets': [for (final p in (j['pets'] as List? ?? [])) {'name': p['name'], 'kind': p['kind']}],
        'posts': j['posts'] ?? [],
        'profile': {'name': j['name'], 'sign': j['sign'], 'look_mode': j['lookMode'], 'skin': j['skinId']},
      });
    } on ApiError catch (e) {
      debugPrint('旧数据没搬上去：$e');
    }
  }

  // ───────── 图片 ─────────

  /// 本机文件（photos/...）的完整路径；服务器上的图返回 null
  String? photoPath(String? ref) => ref == null || dir == null || ref.startsWith('/') || ref.startsWith('http') ? null : '$dir/$ref';

  /// 能直接给 Image 用的图：服务器上的走网络，本机的走文件
  ImageProvider? photo(String? ref) {
    if (ref == null || ref.isEmpty) return null;
    if (ref.startsWith('/files') || ref.startsWith('http')) return NetworkImage(Api.fileUrl(ref));
    final path = photoPath(ref);
    return path != null && File(path).existsSync() ? FileImage(File(path)) : null;
  }

  /// 从相册选一张并传上服务器，返回服务器地址；取消返回 null
  Future<String?> pickAndUpload() async {
    final local = await YuanjingFiles.pickPhoto();
    if (local == null) return null;
    return api.upload(photoPath(local)!);
  }

  // ───────── 改动：可以先记在本机的 ─────────

  /// 记一条心愿，返回发了多少金币（没网时先记下，金币等连上再发）
  Future<int> addWish(String scene, String text) async {
    final item = {'id': null, 'scene': scene, 'text': text, 'ts': DateTime.now().millisecondsSinceEpoch};
    wishes.insert(0, item);
    touch();
    final r = await _send('POST', '/wishes', {'scene': scene, 'text': text});
    if (r == null) return 0;
    item['id'] = r['wish']['id'];
    coins = r['coins'] as int;
    if ((r['got'] as int) > 0) daily['wish'] = count('wish') + 1;
    touch();
    return r['got'] as int;
  }

  Future<void> updateProfile({String? name, String? sign, String? avatar, String? lookMode, bool? lookDynamic}) async {
    final body = {'name': ?name, 'sign': ?sign, 'avatar': ?avatar, 'look_mode': ?lookMode, 'look_dynamic': ?lookDynamic};
    if (name != null) this.name = name;
    if (sign != null) this.sign = sign;
    if (avatar != null) this.avatar = avatar;
    if (lookMode != null) this.lookMode = lookMode;
    if (lookDynamic != null) this.lookDynamic = lookDynamic;
    touch();
    final r = await _send('PATCH', '/me', body);
    if (r != null) {
      _applyUser(r as Map<String, dynamic>);
      touch();
    }
  }

  /// 边写边存：停笔一秒后再发
  void setDestiny(String scene, String text) {
    if ((destiny[scene] ?? '') == text) return;
    if (text.trim().isEmpty) {
      destiny.remove(scene);
    } else {
      destiny[scene] = text;
    }
    destinyTs = DateTime.now().millisecondsSinceEpoch;
    touch(notify: false);
    _destinyTimers[scene]?.cancel();
    _destinyTimers[scene] = Timer(const Duration(seconds: 1), () {
      _destinyTimers.remove(scene);
      _send('PUT', '/destiny/$scene', {'text': text}, replaceKey: 'destiny_$scene');
    });
  }

  /// 离开终点密码页时把还没发的马上发出去
  void flushDestiny() {
    for (final scene in _destinyTimers.keys.toList()) {
      _destinyTimers.remove(scene)!.cancel();
      _send('PUT', '/destiny/$scene', {'text': destiny[scene] ?? ''}, replaceKey: 'destiny_$scene');
    }
  }

  Future<void> addAffirmation(String text) async {
    final item = <String, dynamic>{'id': null, 'text': text};
    affirmations.insert(0, item);
    touch();
    final r = await _send('POST', '/affirmations', {'text': text});
    if (r != null) {
      item['id'] = r['id'];
      touch();
    }
  }

  Future<void> addPet(String name, String kind) async {
    final item = <String, dynamic>{'id': null, 'name': name, 'kind': kind, 'photo': null};
    pets.add(item);
    touch();
    final r = await _send('POST', '/pets', {'name': name, 'kind': kind});
    if (r != null) {
      item['id'] = r['id'];
      touch();
    }
  }

  // ───────── 改动：必须在线的（失败时抛 ApiError，页面拿 message 提示） ─────────

  Future<T> _online<T>(Future<T> Function() run) async {
    try {
      final r = await run();
      online = true;
      return r;
    } on ApiError catch (e) {
      if (e.offline) {
        online = false;
        notifyListeners();
      }
      rethrow;
    }
  }

  Future<void> removeWish(Map<String, dynamic> w) => _removeById(wishes, w, '/wishes');
  Future<void> removeAffirmation(Map<String, dynamic> a) => _removeById(affirmations, a, '/affirmations');
  Future<void> removePet(Map<String, dynamic> p) => _removeById(pets, p, '/pets');
  Future<void> removeVision(Map<String, dynamic> v) => _removeById(vision, v, '/vision');

  Future<void> _removeById(List<Map<String, dynamic>> list, Map<String, dynamic> item, String path) async {
    if (item['id'] != null) await _online(() => api.delete('$path/${item['id']}'));
    list.remove(item);
    touch();
  }

  Future<void> addVision(String text, String scene, String? photo) async {
    final r = await _online(() => api.post('/vision', {'text': text, 'scene': scene, 'photo': photo}));
    vision.insert(0, Map<String, dynamic>.from(r as Map));
    touch();
  }

  Future<void> setPetPhoto(Map<String, dynamic> pet, String url) async {
    final r = await _online(() => api.patch('/pets/${pet['id']}', {'photo': url}));
    pet['photo'] = r['photo'];
    touch();
  }

  Future<int> checkin() async {
    final r = await _online(() => api.post('/checkin'));
    coins = r['coins'] as int;
    streak = r['streak'] as int;
    checkedIn = true;
    if ((r['got'] as int) > 0) {
      daily['checkin'] = 1;
      coinLog.insert(0, CoinEntry(r['got'] as int, '每日签到', DateTime.now().millisecondsSinceEpoch));
    }
    touch();
    return r['got'] as int;
  }

  Future<void> setSkin(String id) async {
    final r = await _online(() => api.patch('/me', {'skin': id}));
    _applyUser(r as Map<String, dynamic>);
    touch();
  }

  Future<void> setMember(bool on) async {
    final r = await _online(() => api.post('/membership/demo', {'on': on}));
    _applyUser(r as Map<String, dynamic>);
    touch();
  }

  /// 买东西或解锁冥想。会员限定的会员直接领。
  Future<void> buy(String itemId) async {
    final r = await _online(() => api.post('/shop/buy', {'item_id': itemId}));
    _applyShop(r as Map<String, dynamic>);
    await refresh();
  }

  Future<void> wear(String itemId, bool on) async {
    final r = await _online(() => api.post('/shop/equip', {'item_id': itemId, 'on': on}));
    _applyShop(r as Map<String, dynamic>);
  }

  void _applyShop(Map<String, dynamic> r) {
    coins = r['coins'] as int;
    owned
      ..clear()
      ..addAll((r['owned'] as List).cast<String>());
    equipped
      ..clear()
      ..addAll((r['equipped'] as List).cast<String>());
    touch();
  }

  // ───────── 湖心小寺：背包、钓鱼、喂食、礼物（都必须在线；没网时抛 ApiError，背包和图鉴先显示上次的） ─────────

  /// 背包里这样东西有几个
  int bagCount(String id) {
    for (final i in bag) {
      if (i['id'] == id) return (i['count'] as num).toInt();
    }
    return 0;
  }

  void _applyBag(List items) {
    bag
      ..clear()
      ..addAll([for (final m in items) Map<String, dynamic>.from(m as Map)]);
  }

  /// 小寺的接口返回里常带着 coins（余额）和 items（背包现在的样子），调完用它一起同步
  void _applyIslet(Map<String, dynamic> r) {
    if (r['coins'] is int) coins = r['coins'] as int;
    if (r['items'] is List) _applyBag(r['items'] as List);
    touch();
  }

  /// 重新取一遍背包
  Future<void> loadBag() async {
    final r = await _online(() => api.get('/bag'));
    _applyIslet(r as Map<String, dynamic>);
  }

  /// 提竿成功后调：服务器摇一条鱼放进背包。[spot] sea / pond，[time] dawn / day / dusk / night，[weather] clear / rain / storm / snow。
  /// 返回 {fish: {id, name, rarity, about, size_cm, record, first}, count, left, got, coins}；今天钓满了抛 ApiError(409)。
  Future<Map<String, dynamic>> catchFish(String spot, {String time = 'day', String weather = 'clear'}) async {
    final r = (await _online(() => api.post('/fishing/catch', {'spot': spot, 'time': time, 'weather': weather}))) as Map<String, dynamic>;
    final got = (r['got'] as num?)?.toInt() ?? 0;
    if (got > 0) coinLog.insert(0, CoinEntry(got, '第一次钓到${r['fish']['name']}', DateTime.now().millisecondsSinceEpoch));
    if (fishBookCache != null) {
      fishBookCache!['left'] = r['left'];
      final f = r['fish'] as Map;
      for (final e in (fishBookCache!['fish'] as List).cast<Map>()) {
        if (e['id'] != f['id']) continue;
        if (e['caught'] != true) fishBookCache!['kinds'] = ((fishBookCache!['kinds'] as num?)?.toInt() ?? 0) + 1;
        e['caught'] = true;
        e['count'] = ((e['count'] as num?)?.toInt() ?? 0) + 1;
        final size = (f['size_cm'] as num).toDouble();
        if (e['best_cm'] == null || size > (e['best_cm'] as num)) e['best_cm'] = size;
      }
    }
    _applyIslet(r);
    return r;
  }

  /// 钓鱼图鉴：{fish: [{id, name, rarity, about, sell, min_cm, max_cm, spots, caught, count, best_cm}], left, daily, kinds, total}
  Future<Map<String, dynamic>> loadFishBook() async {
    final r = (await _online(() => api.get('/fishing'))) as Map<String, dynamic>;
    fishBookCache = r;
    touch();
    return r;
  }

  /// 卖掉背包里的东西，返回换了多少金币
  Future<int> sellItem(String itemId, [int count = 1]) async {
    final r = (await _online(() => api.post('/bag/sell', {'item_id': itemId, 'count': count}))) as Map<String, dynamic>;
    _applyIslet(r);
    return (r['got'] as num).toInt();
  }

  /// 摸一下小动物。返回这只动物现在的样子，另有 counted、gain、level_up、milestone、milestones_new。
  Future<Map<String, dynamic>> strokePet(String pet) async {
    final r = (await _online(() => api.post('/pets/$pet/pet', {}))) as Map<String, dynamic>;
    _afterPet(pet, r);
    return r;
  }

  /// 喂小动物。[item] 是背包里的鱼或口粮的编号；不给就是花金币喂一把普通口粮。
  /// 返回这只动物现在的样子，另有 counted、gain、level_up、favorite、reaction、milestone、milestones_new、coins。
  Future<Map<String, dynamic>> feedPet(String pet, {String? item}) async {
    final r = (await _online(() => api.post('/pets/$pet/feed', {'item': ?item}))) as Map<String, dynamic>;
    _afterPet(pet, r);
    return r;
  }

  /// 收下小动物叼来的每日礼物（一件收藏品，进背包）。今天没有礼物时返回里的 item 是 null。
  /// 返回 {got: 0, coins, name, what, count, item: {id, name, about, rarity}}
  Future<Map<String, dynamic>> takePetGift(String pet) async {
    final r = (await _online(() => api.post('/pets/$pet/gift', {}))) as Map<String, dynamic>;
    final item = r['item'];
    if (item is Map) {
      for (final p in _bookPets) {
        if (p['id'] != pet) continue;
        for (final d in (p['daily'] as List).cast<Map>()) {
          if (d['id'] == item['id']) d['seen'] = true;
        }
      }
    }
    _applyIslet(r);
    return r;
  }

  /// 小动物册：{pets: [{id, name, kind, affinity, level, level_name, next, favorites, favorites_known, frame,
  /// milestones: [{at, kind, what, coins, items, item_id, done}], next_milestone, daily: [{id, name, rarity, seen}]}], names: {编号: 名字}}
  Future<Map<String, dynamic>> loadPetBook() async {
    final r = (await _online(() => api.get('/pets/gifts'))) as Map<String, dynamic>;
    petBookCache = r;
    touch();
    return r;
  }

  List<Map> get _bookPets => ((petBookCache?['pets'] as List?) ?? const []).cast<Map>();

  /// 这只小动物已经喂出来的最爱（没取过小动物册时是空的）
  List<String> knownFavorites(String pet) {
    for (final p in _bookPets) {
      if (p['id'] == pet) return (p['favorites_known'] as List).cast<String>();
    }
    return const [];
  }

  /// 摸完、喂完：同步余额和背包；里程碑送的专属头像框记进「已拥有」；把小动物册里这一只更新一下
  void _afterPet(String pet, Map<String, dynamic> r) {
    final news = ((r['milestones_new'] as List?) ?? const []).cast<Map>();
    for (final m in news) {
      if (m['item_id'] is String) owned.add(m['item_id'] as String);
      final c = (m['coins'] as num?)?.toInt() ?? 0;
      if (c > 0) coinLog.insert(0, CoinEntry(c, '${r['name']}送的一包金币', DateTime.now().millisecondsSinceEpoch));
    }
    for (final p in _bookPets) {
      if (p['id'] != pet) continue;
      for (final k in const ['affinity', 'level', 'level_name', 'next', 'favorites_known']) {
        p[k] = r[k];
      }
      final got = ((r['milestones'] as Map?)?['got'] as num?)?.toInt() ?? 0;
      final list = (p['milestones'] as List).cast<Map>();
      for (var i = 0; i < list.length; i++) {
        list[i]['done'] = i < got;
      }
      p['next_milestone'] = (r['milestones'] as Map?)?['next'];
    }
    _applyIslet(r);
  }

  /// 买可以叠加的东西（小寺的口粮），放进背包
  Future<void> buyStack(String itemId, int count) async {
    final r = (await _online(() => api.post('/shop/buy_stack', {'item_id': itemId, 'count': count}))) as Map<String, dynamic>;
    _applyIslet(r);
  }

  /// 用收藏品兑换一件「小动物的礼物」：扣收藏品，变成已拥有并戴上
  Future<void> redeem(String itemId) async {
    final r = (await _online(() => api.post('/shop/redeem', {'item_id': itemId}))) as Map<String, dynamic>;
    if (r['items'] is List) _applyBag(r['items'] as List);
    _applyShop(r);
  }

  /// 任何返回里带着 coins 的接口，调完用它同步余额
  void setCoins(dynamic r) {
    if (r is Map && r['coins'] is int) {
      coins = r['coins'] as int;
      touch();
    }
  }

  /// 加好友：返回 friends（已是好友）或 requested（等对方同意）
  Future<(String, int)> addFriend(int id) async {
    final r = await _online(() => api.post('/friends/$id'));
    setCoins(r);
    if (r['status'] == 'friends') await refresh();
    return (r['status'] as String, r['got'] as int);
  }

  Future<int> answerRequest(int requestId, bool accept) async {
    final r = await _online(() => api.post('/friends/requests/$requestId/${accept ? 'accept' : 'decline'}'));
    setCoins(r);
    await refresh();
    return r['got'] as int;
  }

  Future<void> removeFriend(int id) async {
    await _online(() => api.delete('/friends/$id'));
    friends.removeWhere((f) => f['id'] == id);
    touch();
  }

  Future<void> block(int id) async {
    await _online(() => api.post('/blocks/$id'));
    friends.removeWhere((f) => f['id'] == id);
    touch();
  }
}

final store = AppStore();
