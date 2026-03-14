import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../services/app_state.dart';
import '../services/api_service.dart';
import '../models/models.dart';

class CreateInvoiceScreen extends StatefulWidget {
  const CreateInvoiceScreen({super.key});

  @override
  State<CreateInvoiceScreen> createState() => _CreateInvoiceScreenState();
}

class _CreateInvoiceScreenState extends State<CreateInvoiceScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
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
        title: const Text('Create Invoice'),
        backgroundColor: const Color(0xFF1A73E8),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          tabs: const [
            Tab(icon: Icon(Icons.edit_note), text: 'Manual'),
            Tab(icon: Icon(Icons.document_scanner), text: 'Upload Image'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _ManualInvoiceForm(),
          _UploadInvoiceForm(),
        ],
      ),
    );
  }
}

class _ManualInvoiceForm extends StatefulWidget {
  const _ManualInvoiceForm();

  @override
  State<_ManualInvoiceForm> createState() => _ManualInvoiceFormState();
}

class _ManualInvoiceFormState extends State<_ManualInvoiceForm> {
  final _formKey = GlobalKey<FormState>();
  MerchantModel? _selectedReceiver;
  final _amountCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _amountCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_selectedReceiver == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a vendor'), backgroundColor: Colors.red),
      );
      return;
    }

    setState(() => _loading = true);
    final state = context.read<AppState>();

    try {
      final api = ApiService();
      final result = await api.createInvoice(
        senderChatId: state.chatId!,
        receiverChatId: _selectedReceiver!.telegramChatId,
        amount: double.parse(_amountCtrl.text),
        description: _descCtrl.text,
      );

      if (mounted) {
        await state.refreshAll();
        _showSuccessDialog(result);
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

  void _showSuccessDialog(Map<String, dynamic> result) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.check_circle, color: Color(0xFF34A853)),
            SizedBox(width: 8),
            Text('Invoice Created!'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Invoice #: ${result['invoice_number']}'),
            Text('Amount: ₹${result['amount']}'),
            const SizedBox(height: 8),
            const Text('Payment link sent via Telegram ✅', style: TextStyle(color: Colors.grey, fontSize: 13)),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final merchants = state.allMerchants.where((m) => m.telegramChatId != state.chatId).toList();

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Send Invoice To', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 8),
            DropdownButtonFormField<MerchantModel>(
              value: _selectedReceiver,
              decoration: _inputDec('Select Vendor'),
              items: merchants
                  .map((m) => DropdownMenuItem(value: m, child: Text(m.businessName)))
                  .toList(),
              onChanged: (val) => setState(() => _selectedReceiver = val),
              validator: (v) => v == null ? 'Select a vendor' : null,
            ),
            const SizedBox(height: 16),
            const Text('Amount (₹)', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 8),
            TextFormField(
              controller: _amountCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: _inputDec('e.g. 1500.00'),
              validator: (v) {
                if (v == null || v.isEmpty) return 'Enter amount';
                if (double.tryParse(v) == null) return 'Invalid amount';
                if (double.parse(v) <= 0) return 'Amount must be positive';
                return null;
              },
            ),
            const SizedBox(height: 16),
            const Text('Description', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 8),
            TextFormField(
              controller: _descCtrl,
              decoration: _inputDec('e.g. Office supplies, Q1 services...'),
              maxLines: 3,
            ),
            const SizedBox(height: 28),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _loading ? null : _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1A73E8),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: _loading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Create Invoice & Send Link', style: TextStyle(fontSize: 16)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  InputDecoration _inputDec(String hint) => InputDecoration(
        hintText: hint,
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      );
}

class _UploadInvoiceForm extends StatefulWidget {
  const _UploadInvoiceForm();

  @override
  State<_UploadInvoiceForm> createState() => _UploadInvoiceFormState();
}

class _UploadInvoiceFormState extends State<_UploadInvoiceForm> {
  MerchantModel? _selectedReceiver;
  Uint8List? _fileBytes;
  String? _fileName;
  String? _mimeType;
  final _amountCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _amountCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['jpg', 'jpeg', 'png', 'pdf'],
      withData: true,
    );
    if (result != null && result.files.single.bytes != null) {
      setState(() {
        _fileBytes = result.files.single.bytes;
        _fileName = result.files.single.name;
        _mimeType = result.files.single.extension == 'pdf' ? 'application/pdf' : 'image/jpeg';
      });
    }
  }

  Future<void> _submit() async {
    if (_selectedReceiver == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a vendor'), backgroundColor: Colors.red),
      );
      return;
    }
    if (_fileBytes == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select an invoice file'), backgroundColor: Colors.red),
      );
      return;
    }

    setState(() => _loading = true);
    final state = context.read<AppState>();

    try {
      final api = ApiService();
      final result = await api.uploadInvoice(
        senderChatId: state.chatId!,
        receiverChatId: _selectedReceiver!.telegramChatId,
        fileBytes: _fileBytes!,
        fileName: _fileName!,
        mimeType: _mimeType!,
        amountOverride: _amountCtrl.text.isNotEmpty ? double.tryParse(_amountCtrl.text) : null,
        notes: _notesCtrl.text.isNotEmpty ? _notesCtrl.text : null,
      );

      if (mounted) {
        await state.refreshAll();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✅ Invoice ${result['invoice_number']} created! Amount: ₹${result['amount']}'),
            backgroundColor: Colors.green,
          ),
        );
        setState(() {
          _fileBytes = null;
          _fileName = null;
          _selectedReceiver = null;
          _amountCtrl.clear();
          _notesCtrl.clear();
        });
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
    final state = context.watch<AppState>();
    final merchants = state.allMerchants.where((m) => m.telegramChatId != state.chatId).toList();

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFF1A73E8).withOpacity(0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF1A73E8).withOpacity(0.2)),
            ),
            child: const Row(
              children: [
                Icon(Icons.auto_awesome, color: Color(0xFF1A73E8), size: 20),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'AI-powered OCR reads handwritten or printed invoices automatically!',
                    style: TextStyle(color: Color(0xFF1A73E8), fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          const Text('Send To Vendor', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 8),
          DropdownButtonFormField<MerchantModel>(
            value: _selectedReceiver,
            decoration: _inputDec('Select Vendor'),
            items: merchants.map((m) => DropdownMenuItem(value: m, child: Text(m.businessName))).toList(),
            onChanged: (val) => setState(() => _selectedReceiver = val),
          ),
          const SizedBox(height: 16),
          const Text('Upload Invoice', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 8),
          InkWell(
            onTap: _pickFile,
            child: Container(
              width: double.infinity,
              height: 120,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: _fileBytes != null ? const Color(0xFF34A853) : Colors.grey.shade300,
                  width: 2,
                  style: BorderStyle.solid,
                ),
              ),
              child: _fileBytes != null
                  ? Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.check_circle, color: Color(0xFF34A853), size: 36),
                        const SizedBox(height: 8),
                        Text(_fileName ?? 'File selected',
                            style: const TextStyle(fontWeight: FontWeight.w600)),
                        const Text('Tap to change', style: TextStyle(color: Colors.grey, fontSize: 12)),
                      ],
                    )
                  : const Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.upload_file, size: 36, color: Colors.grey),
                        SizedBox(height: 8),
                        Text('Tap to upload invoice', style: TextStyle(color: Colors.grey)),
                        Text('JPG, PNG, or PDF', style: TextStyle(color: Colors.grey, fontSize: 12)),
                      ],
                    ),
            ),
          ),
          const SizedBox(height: 16),
          const Text('Amount Override (optional)', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 4),
          const Text('Leave blank to auto-detect from invoice', style: TextStyle(color: Colors.grey, fontSize: 12)),
          const SizedBox(height: 8),
          TextField(
            controller: _amountCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: _inputDec('e.g. 1500.00'),
          ),
          const SizedBox(height: 16),
          const Text('Notes', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 8),
          TextField(
            controller: _notesCtrl,
            decoration: _inputDec('Additional notes...'),
            maxLines: 2,
          ),
          const SizedBox(height: 28),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _loading ? null : _submit,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1A73E8),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: _loading
                  ? const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)),
                        SizedBox(width: 12),
                        Text('Processing with AI...', style: TextStyle(fontSize: 15)),
                      ],
                    )
                  : const Text('Upload & Create Invoice', style: TextStyle(fontSize: 16)),
            ),
          ),
        ],
      ),
    );
  }

  InputDecoration _inputDec(String hint) => InputDecoration(
        hintText: hint,
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      );
}
