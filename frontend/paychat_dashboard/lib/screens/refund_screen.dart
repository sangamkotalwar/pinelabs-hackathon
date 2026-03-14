import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../services/app_state.dart';
import '../services/api_service.dart';
import '../models/models.dart';

final _rupee = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

class RefundScreen extends StatefulWidget {
  const RefundScreen({super.key});

  @override
  State<RefundScreen> createState() => _RefundScreenState();
}

class _RefundScreenState extends State<RefundScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AppState>().refreshSentInvoices();
    });
  }

  List<InvoiceModel> _paidInvoices(List<InvoiceModel> sent) =>
      sent.where((i) => i.status == 'paid').toList();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final paidInvoices = _paidInvoices(state.sentInvoices);

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        title: const Text('Refunds'),
        backgroundColor: const Color(0xFF1A73E8),
        foregroundColor: Colors.white,
      ),
      body: paidInvoices.isEmpty
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.receipt_long_outlined, size: 64, color: Colors.grey),
                  SizedBox(height: 16),
                  Text('No paid invoices', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  SizedBox(height: 8),
                  Text('Only paid invoices can be refunded.', style: TextStyle(color: Colors.grey)),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: paidInvoices.length,
              itemBuilder: (ctx, i) => _RefundTile(invoice: paidInvoices[i]),
            ),
    );
  }
}

class _RefundTile extends StatefulWidget {
  final InvoiceModel invoice;
  const _RefundTile({required this.invoice});

  @override
  State<_RefundTile> createState() => _RefundTileState();
}

class _RefundTileState extends State<_RefundTile> {
  bool _loading = false;

  Future<void> _initiateRefund() async {
    final reasonCtrl = TextEditingController(text: 'Refund requested');

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Initiate Refund'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Invoice: ${widget.invoice.invoiceNumber}'),
            Text('Amount: ${_rupee.format(widget.invoice.amount)}'),
            Text('To: ${widget.invoice.toBusiness ?? 'Unknown'}'),
            const SizedBox(height: 16),
            const Text('Reason:', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            TextField(
              controller: reasonCtrl,
              decoration: InputDecoration(
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFEA4335), foregroundColor: Colors.white),
            child: const Text('Refund'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _loading = true);
    try {
      final api = ApiService();
      final result = await api.refundInvoice(
        invoiceId: widget.invoice.id,
        reason: reasonCtrl.text,
      );

      if (mounted) {
        context.read<AppState>().refreshAll();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result['success'] == true
                ? '✅ Refund initiated for ${_rupee.format(result['amount'] ?? 0)}'
                : '❌ ${result['error'] ?? 'Refund failed'}'),
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
      if (mounted) setState(() => _loading = false);
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
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(inv.invoiceNumber,
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                  const SizedBox(height: 4),
                  Text('To: ${inv.toBusiness ?? 'Unknown'}',
                      style: const TextStyle(color: Colors.grey, fontSize: 12)),
                  const SizedBox(height: 4),
                  Text(
                    _rupee.format(inv.amount),
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  if (inv.paidAt != null)
                    Text(
                      'Paid: ${DateFormat('dd MMM yyyy').format(inv.paidAt!)}',
                      style: const TextStyle(color: Color(0xFF34A853), fontSize: 12),
                    ),
                ],
              ),
            ),
            ElevatedButton(
              onPressed: _loading ? null : _initiateRefund,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFEA4335),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: _loading
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : const Text('Refund'),
            ),
          ],
        ),
      ),
    );
  }
}
