import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/app_state.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _chatIdCtrl = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _chatIdCtrl.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final chatId = _chatIdCtrl.text.trim();
    if (chatId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter your Telegram Chat ID')),
      );
      return;
    }

    setState(() => _loading = true);
    final state = context.read<AppState>();
    final success = await state.loginWithChatId(chatId);

    if (!success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(state.error ?? 'Login failed'),
          backgroundColor: Colors.red,
        ),
      );
      state.clearError();
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1A73E8),
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(),
            const _LogoSection(),
            const Spacer(),
            _LoginCard(
              chatIdCtrl: _chatIdCtrl,
              loading: _loading,
              onLogin: _login,
            ),
          ],
        ),
      ),
    );
  }
}

class _LogoSection extends StatelessWidget {
  const _LogoSection();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 90,
          height: 90,
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(color: Colors.black.withOpacity(0.2), blurRadius: 20, offset: const Offset(0, 8)),
            ],
          ),
          child: const Icon(Icons.chat_bubble, color: Color(0xFF1A73E8), size: 48),
        ),
        const SizedBox(height: 24),
        const Text(
          'PayChat',
          style: TextStyle(
            color: Colors.white,
            fontSize: 36,
            fontWeight: FontWeight.bold,
            letterSpacing: -0.5,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'B2B Payments via Telegram',
          style: TextStyle(color: Colors.white70, fontSize: 16),
        ),
      ],
    );
  }
}

class _LoginCard extends StatelessWidget {
  final TextEditingController chatIdCtrl;
  final bool loading;
  final VoidCallback onLogin;

  const _LoginCard({
    required this.chatIdCtrl,
    required this.loading,
    required this.onLogin,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Sign In',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFF202124)),
          ),
          const SizedBox(height: 8),
          const Text(
            'Enter your Telegram Chat ID to continue',
            style: TextStyle(color: Colors.grey, fontSize: 14),
          ),
          const SizedBox(height: 24),
          TextField(
            controller: chatIdCtrl,
            keyboardType: TextInputType.number,
            style: const TextStyle(fontSize: 18, letterSpacing: 1),
            decoration: InputDecoration(
              labelText: 'Telegram Chat ID',
              hintText: 'e.g. 123456789',
              prefixIcon: const Icon(Icons.telegram, color: Color(0xFF1A73E8)),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: Colors.grey.shade300),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: Colors.grey.shade300),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Color(0xFF1A73E8), width: 2),
              ),
              filled: true,
              fillColor: const Color(0xFFF8F9FA),
            ),
            onSubmitted: (_) => onLogin(),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Icon(Icons.info_outline, size: 14, color: Colors.grey),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Get your Chat ID by messaging @userinfobot on Telegram or using /myid in PayChat bot',
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: loading ? null : onLogin,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1A73E8),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 2,
              ),
              child: loading
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
                    )
                  : const Text('Sign In', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}
