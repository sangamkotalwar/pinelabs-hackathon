import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/app_state.dart';
import '../models/models.dart';
import 'package:intl/intl.dart';

final _rupee = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AppState>().refreshAll();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final dashboard = state.dashboard;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: const Text('PayChat'),
        backgroundColor: const Color(0xFF1A73E8),
        foregroundColor: Colors.white,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => state.refreshAll(),
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => state.logout(),
          ),
        ],
      ),
      body: state.isLoading && dashboard == null
          ? const Center(child: CircularProgressIndicator())
          : dashboard == null
              ? const Center(child: Text('Loading dashboard...'))
              : RefreshIndicator(
                  onRefresh: state.refreshAll,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _WelcomeCard(merchant: dashboard.merchant),
                        const SizedBox(height: 16),
                        _BalanceCards(balance: dashboard.balance),
                        const SizedBox(height: 16),
                        _SectionTitle(title: 'Recent Pending', count: dashboard.recentPending.length),
                        ...dashboard.recentPending.map((inv) => _InvoiceCard(invoice: inv, isPending: true)),
                        if (dashboard.recentPending.isEmpty)
                          const _EmptyState(message: 'No pending payments ✅'),
                        const SizedBox(height: 16),
                        _SectionTitle(title: 'Recent Sent', count: dashboard.recentSent.length),
                        ...dashboard.recentSent.map((inv) => _InvoiceCard(invoice: inv, isPending: false)),
                        if (dashboard.recentSent.isEmpty)
                          const _EmptyState(message: 'No sent invoices yet'),
                        const SizedBox(height: 80),
                      ],
                    ),
                  ),
                ),
    );
  }
}

class _WelcomeCard extends StatelessWidget {
  final MerchantModel merchant;
  const _WelcomeCard({required this.merchant});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1A73E8), Color(0xFF0D47A1)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.blue.withOpacity(0.3), blurRadius: 12, offset: const Offset(0, 4)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const CircleAvatar(
                radius: 24,
                backgroundColor: Colors.white24,
                child: Icon(Icons.business, color: Colors.white, size: 28),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      merchant.businessName,
                      style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    if (merchant.email != null)
                      Text(merchant.email!, style: const TextStyle(color: Colors.white70, fontSize: 12)),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _BalanceCards extends StatelessWidget {
  final BalanceSummary balance;
  const _BalanceCards({required this.balance});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _MetricCard(
            title: 'Receivable',
            amount: balance.totalReceivable,
            count: balance.receivableCount,
            color: const Color(0xFF34A853),
            icon: Icons.arrow_downward,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _MetricCard(
            title: 'Payable',
            amount: balance.totalPayable,
            count: balance.payableCount,
            color: const Color(0xFFEA4335),
            icon: Icons.arrow_upward,
          ),
        ),
      ],
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String title;
  final double amount;
  final int count;
  final Color color;
  final IconData icon;

  const _MetricCard({
    required this.title,
    required this.amount,
    required this.count,
    required this.color,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.06), blurRadius: 8)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 6),
              Text(title, style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13)),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _rupee.format(amount),
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF202124)),
          ),
          Text('$count invoice${count == 1 ? '' : 's'}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final int count;
  const _SectionTitle({required this.title, required this.count});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF202124))),
          if (count > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: const Color(0xFF1A73E8).withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text('$count', style: const TextStyle(color: Color(0xFF1A73E8), fontWeight: FontWeight.bold)),
            ),
        ],
      ),
    );
  }
}

class _InvoiceCard extends StatelessWidget {
  final InvoiceModel invoice;
  final bool isPending;
  const _InvoiceCard({required this.invoice, required this.isPending});

  Color get _statusColor {
    switch (invoice.status) {
      case 'paid':
        return const Color(0xFF34A853);
      case 'refunded':
        return const Color(0xFF9E9E9E);
      case 'payment_link_sent':
        return const Color(0xFFFBBC04);
      default:
        return const Color(0xFFEA4335);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 1,
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: CircleAvatar(
          backgroundColor: _statusColor.withOpacity(0.15),
          child: Icon(
            isPending ? Icons.inbox : Icons.send,
            color: _statusColor,
            size: 20,
          ),
        ),
        title: Text(invoice.invoiceNumber, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        subtitle: Text(
          isPending
              ? 'From: ${invoice.fromBusiness ?? 'Unknown'}'
              : 'To: ${invoice.toBusiness ?? 'Unknown'}',
          style: const TextStyle(fontSize: 12),
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              _rupee.format(invoice.amount),
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: _statusColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                invoice.status.toUpperCase().replaceAll('_', ' '),
                style: TextStyle(color: _statusColor, fontSize: 9, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final String message;
  const _EmptyState({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Text(message, textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey)),
    );
  }
}
