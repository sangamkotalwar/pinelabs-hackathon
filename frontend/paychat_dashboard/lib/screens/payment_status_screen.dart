import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../services/app_state.dart';
import '../services/api_service.dart';
import '../models/models.dart';

final _rupee = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

class PaymentStatusScreen extends StatefulWidget {
  const PaymentStatusScreen({super.key});

  @override
  State<PaymentStatusScreen> createState() => _PaymentStatusScreenState();
}

class _PaymentStatusScreenState extends State<PaymentStatusScreen> {
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
    final all = [...state.pendingInvoices, ...state.sentInvoices];
    all.sort((a, b) => b.createdAt.compareTo(a.createdAt));

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: const Text('Payment Status'),
        backgroundColor: const Color(0xFF1A73E8),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: state.refreshAll,
          ),
        ],
      ),
      body: all.isEmpty
          ? const Center(child: Text('No transactions yet'))
          : RefreshIndicator(
              onRefresh: state.refreshAll,
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: all.length,
                itemBuilder: (ctx, i) => _StatusTile(
                  invoice: all[i],
                  currentChatId: state.chatId!,
                ),
              ),
            ),
    );
  }
}

class _StatusTile extends StatelessWidget {
  final InvoiceModel invoice;
  final String currentChatId;
  const _StatusTile({required this.invoice, required this.currentChatId});

  @override
  Widget build(BuildContext context) {
    final isReceivable = invoice.fromBusiness == null;
    final statusConfig = _statusConfig(invoice.status);

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 1.5,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _showDetail(context),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: statusConfig['color'].withOpacity(0.12),
                  shape: BoxShape.circle,
                ),
                child: Icon(statusConfig['icon'], color: statusConfig['color'], size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(invoice.invoiceNumber,
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                    const SizedBox(height: 3),
                    Text(
                      isReceivable
                          ? 'To: ${invoice.toBusiness ?? 'Unknown'}'
                          : 'From: ${invoice.fromBusiness ?? 'Unknown'}',
                      style: const TextStyle(color: Colors.grey, fontSize: 12),
                    ),
                    Text(
                      DateFormat('dd MMM yyyy, hh:mm a').format(invoice.createdAt),
                      style: const TextStyle(color: Colors.grey, fontSize: 11),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _rupee.format(invoice.amount),
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(
                      color: statusConfig['color'].withOpacity(0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      invoice.status.toUpperCase().replaceAll('_', ' '),
                      style: TextStyle(
                          color: statusConfig['color'], fontSize: 9, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Map<String, dynamic> _statusConfig(String status) {
    switch (status) {
      case 'paid':
        return {'color': const Color(0xFF34A853), 'icon': Icons.check_circle};
      case 'refunded':
        return {'color': const Color(0xFF9E9E9E), 'icon': Icons.replay};
      case 'payment_link_sent':
        return {'color': const Color(0xFFFBBC04), 'icon': Icons.link};
      case 'cancelled':
        return {'color': const Color(0xFF9E9E9E), 'icon': Icons.cancel};
      default:
        return {'color': const Color(0xFFEA4335), 'icon': Icons.pending};
    }
  }

  void _showDetail(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 20),
            Text(invoice.invoiceNumber,
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            _DetailRow('Amount', _rupee.format(invoice.amount)),
            _DetailRow('Status', invoice.status.toUpperCase().replaceAll('_', ' ')),
            if (invoice.fromBusiness != null) _DetailRow('From', invoice.fromBusiness!),
            if (invoice.toBusiness != null) _DetailRow('To', invoice.toBusiness!),
            if (invoice.description != null && invoice.description!.isNotEmpty)
              _DetailRow('Description', invoice.description!),
            _DetailRow('Created', DateFormat('dd MMM yyyy').format(invoice.createdAt)),
            if (invoice.paidAt != null)
              _DetailRow('Paid', DateFormat('dd MMM yyyy').format(invoice.paidAt!)),
            if (invoice.paymentLink != null && invoice.isPending) ...[
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () async {
                    Navigator.pop(ctx);
                    final api = ApiService();
                    try {
                      await api.resendPaymentLink(invoice.id);
                      if (ctx.mounted) {
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          const SnackBar(content: Text('Payment link resent!')),
                        );
                      }
                    } catch (_) {}
                  },
                  icon: const Icon(Icons.send),
                  label: const Text('Resend Payment Link'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1A73E8),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ),
            ],
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;
  const _DetailRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(label, style: const TextStyle(color: Colors.grey, fontSize: 13)),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
          ),
        ],
      ),
    );
  }
}
