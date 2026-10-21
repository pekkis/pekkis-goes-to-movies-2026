import 'package:flutter/material.dart';
// Plugin imports
import 'package:flutter_riverpod/flutter_riverpod.dart';
// Page imports
import 'app/landing.dart';

void main() {
  runApp(
    const ProviderScope(
      child: MovieMapApp(),
    ),
  );
}


class MovieMapApp extends StatelessWidget {
  const MovieMapApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: LandingPage(),
    );
  }
}
