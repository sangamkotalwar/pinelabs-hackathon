class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const String appName = 'PayChat';
  static const String appTagline = 'B2B Payments via Telegram';
}
