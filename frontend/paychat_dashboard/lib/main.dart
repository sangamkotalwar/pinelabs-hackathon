import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/app_state.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/invoice_list_screen.dart';
import 'screens/create_invoice_screen.dart';
import 'screens/payment_status_screen.dart';
import 'screens/refund_screen.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => AppState()..loadSavedSession(),
      child: const PayChatApp(),
    ),
  );
}

class PayChatApp extends StatelessWidget {
  const PayChatApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PayChat',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A73E8),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        fontFamily: 'Roboto',
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF1A73E8),
          foregroundColor: Colors.white,
          elevation: 0,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF1A73E8),
            foregroundColor: Colors.white,
            elevation: 2,
          ),
        ),
      ),
      home: const _AppShell(),
    );
  }
}

class _AppShell extends StatelessWidget {
  const _AppShell();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    if (!state.isLoggedIn) {
      return const LoginScreen();
    }

    return const _MainNav();
  }
}

class _MainNav extends StatefulWidget {
  const _MainNav();

  @override
  State<_MainNav> createState() => _MainNavState();
}

class _MainNavState extends State<_MainNav> {
  int _currentIndex = 0;

  static const _screens = [
    DashboardScreen(),
    InvoiceListScreen(),
    CreateInvoiceScreen(),
    PaymentStatusScreen(),
    RefundScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (i) => setState(() => _currentIndex = i),
        indicatorColor: const Color(0xFF1A73E8).withOpacity(0.12),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard, color: Color(0xFF1A73E8)),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.receipt_long_outlined),
            selectedIcon: Icon(Icons.receipt_long, color: Color(0xFF1A73E8)),
            label: 'Invoices',
          ),
          NavigationDestination(
            icon: Icon(Icons.add_circle_outline),
            selectedIcon: Icon(Icons.add_circle, color: Color(0xFF1A73E8)),
            label: 'Create',
          ),
          NavigationDestination(
            icon: Icon(Icons.payment_outlined),
            selectedIcon: Icon(Icons.payment, color: Color(0xFF1A73E8)),
            label: 'Payments',
          ),
          NavigationDestination(
            icon: Icon(Icons.replay_outlined),
            selectedIcon: Icon(Icons.replay, color: Color(0xFF1A73E8)),
            label: 'Refunds',
          ),
        ],
      ),
    );
  }
}
