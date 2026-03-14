import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../config.dart';
import '../models/models.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  final String _base = AppConfig.baseUrl;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  Future<MerchantModel> registerMerchant({
    required String chatId,
    required String businessName,
    String? email,
    String? phone,
  }) async {
    final res = await http.post(
      Uri.parse('$_base/merchant/register'),
      headers: _headers,
      body: jsonEncode({
        'telegram_chat_id': chatId,
        'business_name': businessName,
        'email': email,
        'phone': phone,
      }),
    );
    _checkStatus(res);
    return MerchantModel.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<MerchantModel> getMerchant(String chatId) async {
    final res = await http.get(Uri.parse('$_base/merchant/$chatId'), headers: _headers);
    _checkStatus(res);
    return MerchantModel.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<List<MerchantModel>> listMerchants() async {
    final res = await http.get(Uri.parse('$_base/merchants'), headers: _headers);
    _checkStatus(res);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => MerchantModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> createInvoice({
    required String senderChatId,
    required String receiverChatId,
    required double amount,
    String description = '',
    List<Map<String, dynamic>> lineItems = const [],
    String? notes,
  }) async {
    final res = await http.post(
      Uri.parse('$_base/invoice/create'),
      headers: _headers,
      body: jsonEncode({
        'sender_chat_id': senderChatId,
        'receiver_chat_id': receiverChatId,
        'amount': amount,
        'description': description,
        'line_items': lineItems,
        'notes': notes,
      }),
    );
    _checkStatus(res);
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> uploadInvoice({
    required String senderChatId,
    required String receiverChatId,
    required Uint8List fileBytes,
    required String fileName,
    required String mimeType,
    double? amountOverride,
    String? notes,
  }) async {
    final uri = Uri.parse('$_base/invoice/upload');
    final request = http.MultipartRequest('POST', uri)
      ..fields['sender_chat_id'] = senderChatId
      ..fields['receiver_chat_id'] = receiverChatId;

    if (amountOverride != null) {
      request.fields['amount_override'] = amountOverride.toString();
    }
    if (notes != null) {
      request.fields['notes'] = notes;
    }
    request.files.add(http.MultipartFile.fromBytes('file', fileBytes, filename: fileName));

    final streamed = await request.send();
    final res = await http.Response.fromStream(streamed);
    _checkStatus(res);
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<List<InvoiceModel>> getPendingInvoices(String chatId) async {
    final res = await http.get(
      Uri.parse('$_base/invoice/pending?chat_id=$chatId'),
      headers: _headers,
    );
    _checkStatus(res);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => InvoiceModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<InvoiceModel>> getSentInvoices(String chatId) async {
    final res = await http.get(
      Uri.parse('$_base/invoice/sent?chat_id=$chatId'),
      headers: _headers,
    );
    _checkStatus(res);
    final list = jsonDecode(res.body) as List;
    return list.map((e) => InvoiceModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<DashboardData> getDashboard(String chatId) async {
    final res = await http.get(
      Uri.parse('$_base/dashboard/$chatId'),
      headers: _headers,
    );
    _checkStatus(res);
    return DashboardData.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<BalanceSummary> getBalance(String chatId) async {
    final res = await http.get(
      Uri.parse('$_base/invoice/balance/$chatId'),
      headers: _headers,
    );
    _checkStatus(res);
    return BalanceSummary.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> refundInvoice({
    required int invoiceId,
    double? amount,
    String? reason,
  }) async {
    final res = await http.post(
      Uri.parse('$_base/invoice/refund'),
      headers: _headers,
      body: jsonEncode({
        'invoice_id': invoiceId,
        'amount': amount,
        'reason': reason ?? 'Refund requested',
      }),
    );
    _checkStatus(res);
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> resendPaymentLink(int invoiceId) async {
    final res = await http.post(
      Uri.parse('$_base/payment/resend'),
      headers: _headers,
      body: jsonEncode({'invoice_id': invoiceId}),
    );
    _checkStatus(res);
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> demoPay(String invoiceReference) async {
    final res = await http.post(
      Uri.parse('$_base/demo/pay/$invoiceReference'),
      headers: _headers,
    );
    _checkStatus(res);
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  void _checkStatus(http.Response res) {
    if (res.statusCode >= 400) {
      final body = res.body;
      String message = 'Request failed (${res.statusCode})';
      try {
        final json = jsonDecode(body) as Map<String, dynamic>;
        message = json['detail']?.toString() ?? message;
      } catch (_) {}
      throw ApiException(message, res.statusCode);
    }
  }
}

class ApiException implements Exception {
  final String message;
  final int statusCode;
  ApiException(this.message, this.statusCode);

  @override
  String toString() => 'ApiException($statusCode): $message';
}
