import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:intl/intl.dart';
import '../services/app_state.dart';
import '../services/api_service.dart';
import '../models/models.dart';

final _rupee = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

class InvoiceListScreen extends StatefulWidget {
  const InvoiceListScreen({super.key});

  @override
  State<InvoiceListScreen> createState() => _InvoiceListScreenState();
}

class _InvoiceListScreenState extends State<InvoiceListScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final state = context.read<AppState>();
      state.refreshPendingInvoices();
      state.refreshSentInvoices();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: const Text('Invoices'),
        backgroundColor: const Color(0xFF1A73E8),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          tabs: const [
            Tab(text: 'Pending (To Pay)'),
            Tab(text: 'Sent (To Receive)'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _PendingInvoicesTab(),
          _SentInvoicesTab(),
        ],
      ),
    );
  }
}

class _PendingInvoicesTab extends StatelessWidget {
  const _PendingInvoicesTab();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final invoices = state.pendingInvoices;

    if (invoices.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.check_circle_outline, size: 64, color: Color(0xFF34A853)),
            SizedBox(height: 16),
            Text('No pending payments!', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            SizedBox(height: 8),
            Text('You have no outstanding invoices.', style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: state.refreshPendingInvoices,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: invoices.length,
        itemBuilder: (ctx, i) => _PendingInvoiceTile(invoice: invoices[i]),
      ),
    );
  }
}

class _PendingInvoiceTile extends StatelessWidget {
  final InvoiceModel invoice;
  const _PendingInvoiceTile({required this.invoice});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(invoice.invoiceNumber,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                _StatusChip(status: invoice.status),
              ],
            ),
            const SizedBox(height: 8),
            Text('From: ${invoice.fromBusiness ?? 'Unknown'}',
                style: const TextStyle(color: Colors.grey, fontSize: 13)),
            const SizedBox(height: 4),
            Text('Date: ${DateFormat('dd MMM yyyy').format(invoice.createdAt)}',
                style: const TextStyle(color: Colors.grey, fontSize: 12)),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  _rupee.format(invoice.amount),
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF202124),
                  ),
                ),
                if (invoice.paymentLink != null)
                  ElevatedButton.icon(
                    onPressed: () async {
                      final url = Uri.parse(invoice.paymentLink!);
                      if (await canLaunchUrl(url)) {
                        await launchUrl(url, mode: LaunchMode.externalApplication);
                      }
                    },
                    icon: const Icon(Icons.payment, size: 16),
                    label: const Text('Pay Now'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF1A73E8),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SentInvoicesTab extends StatelessWidget {
  const _SentInvoicesTab();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final invoices = state.sentInvoices;

    if (invoices.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.send_outlined, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('No sent invoices yet', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            SizedBox(height: 8),
            Text('Create an invoice to get started.', style: TextStyle(color: Colors.grey)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: state.refreshSentInvoices,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: invoices.length,
        itemBuilder: (ctx, i) => _SentInvoiceTile(invoice: invoices[i]),
      ),
    );
  }
}

class _SentInvoiceTile extends StatefulWidget {
  final InvoiceModel invoice;
  const _SentInvoiceTile({required this.invoice});

  @override
  State<_SentInvoiceTile> createState() => _SentInvoiceTileState();
}

class _SentInvoiceTileState extends State<_SentInvoiceTile> {
  bool _resending = false;
  bool _demoLoading = false;

  Future<void> _resendLink() async {
    setState(() => _resending = true);
    try {
      final api = ApiService();
      final result = await api.resendPaymentLink(widget.invoice.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result['success'] == true ? '✅ Payment link resent!' : '❌ Failed to resend'),
            backgroundColor: result['success'] == true ? Colors.green : Colors.red,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _resending = false);
    }
  }

  Future<void> _simulatePay() async {
    setState(() => _demoLoading = true);
    try {
      final api = ApiService();
      await api.demoPay(widget.invoice.invoiceNumber);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('✅ Demo payment successful!'), backgroundColor: Colors.green),
        );
        context.read<AppState>().refreshAll();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Demo pay error: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _demoLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final inv = widget.invoice;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(inv.invoiceNumber,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                _StatusChip(status: inv.status),
              ],
            ),
            const SizedBox(height: 8),
            Text('To: ${inv.toBusiness ?? 'Unknown'}',
                style: const TextStyle(color: Colors.grey, fontSize: 13)),
            const SizedBox(height: 4),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  _rupee.format(inv.amount),
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                Text(
                  DateFormat('dd MMM yyyy').format(inv.createdAt),
                  style: const TextStyle(color: Colors.grey, fontSize: 12),
                ),
              ],
            ),
            if (inv.isPending) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _resending ? null : _resendLink,
                      icon: _resending
                          ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.send, size: 14),
                      label: const Text('Resend Link', style: TextStyle(fontSize: 12)),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFF1A73E8),
                        side: const BorderSide(color: Color(0xFF1A73E8)),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _demoLoading ? null : _simulatePay,
                      icon: _demoLoading
                          ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.play_circle_outline, size: 14),
                      label: const Text('Demo Pay', style: TextStyle(fontSize: 12)),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.orange,
                        side: const BorderSide(color: Colors.orange),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  final String status;
  const _StatusChip({required this.status});

  Color get _color {
    switch (status) {
      case 'paid':
        return const Color(0xFF34A853);
      case 'refunded':
        return const Color(0xFF9E9E9E);
      case 'payment_link_sent':
        return const Color(0xFFFBBC04);
      case 'cancelled':
        return const Color(0xFF9E9E9E);
      default:
        return const Color(0xFFEA4335);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _color.withOpacity(0.3)),
      ),
      child: Text(
        status.toUpperCase().replaceAll('_', ' '),
        style: TextStyle(color: _color, fontWeight: FontWeight.bold, fontSize: 10),
      ),
    );
  }
}
