import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app/shell.dart';
import 'app/store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // 先把本机存档读进来，界面一出来就是上次的样子
  await store.load();
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  SystemChrome.setSystemUIOverlayStyle(SystemUiOverlayStyle.light);
  runApp(const YuanjingApp());
}

class YuanjingApp extends StatelessWidget {
  const YuanjingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '愿境',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: Colors.black,
        splashFactory: NoSplash.splashFactory,
        highlightColor: Colors.transparent,
        textSelectionTheme: const TextSelectionThemeData(cursorColor: Colors.white70),
      ),
      home: const Shell(),
    );
  }
}
