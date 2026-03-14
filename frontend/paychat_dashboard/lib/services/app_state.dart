import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class AppState extends ChangeNotifier {
  final ApiService _api = ApiService();

  String? _chatId;
  MerchantModel? _merchant;
  DashboardData? _dashboard;
  List<InvoiceModel> _pendingInvoices = [];
  List<InvoiceModel> _sentInvoices = [];
  List<MerchantModel> _allMerchants = [];
  bool _isLoading = false;
  String? _error;

  String? get chatId => _chatId;
  MerchantModel? get merchant => _merchant;
  DashboardData? get dashboard => _dashboard;
  List<InvoiceModel> get pendingInvoices => _pendingInvoices;
  List<InvoiceModel> get sentInvoices => _sentInvoices;
  List<MerchantModel> get allMerchants => _allMerchants;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isLoggedIn => _chatId != null && _merchant != null;

  Future<void> loadSavedSession() async {
    final prefs = await SharedPreferences.getInstance();
    final savedChatId = prefs.getString('chat_id');
    if (savedChatId != null) {
      await loginWithChatId(savedChatId);
    }
  }

  Future<bool> loginWithChatId(String chatId) async {
    _setLoading(true);
    _error = null;
    try {
      final merchant = await _api.getMerchant(chatId);
      _chatId = chatId;
      _merchant = merchant;
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('chat_id', chatId);
      await refreshAll();
      return true;
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        _error = 'Business not found. Register on Telegram first.';
      } else {
        _error = e.message;
      }
      return false;
    } finally {
      _setLoading(false);
    }
  }

  Future<void> logout() async {
    _chatId = null;
    _merchant = null;
    _dashboard = null;
    _pendingInvoices = [];
    _sentInvoices = [];
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('chat_id');
    notifyListeners();
  }

  Future<void> refreshAll() async {
    if (_chatId == null) return;
    await Future.wait([
      refreshDashboard(),
      refreshPendingInvoices(),
      refreshSentInvoices(),
      refreshMerchants(),
    ]);
  }

  Future<void> refreshDashboard() async {
    if (_chatId == null) return;
    try {
      _dashboard = await _api.getDashboard(_chatId!);
      notifyListeners();
    } catch (e) {
      debugPrint('Dashboard refresh error: $e');
    }
  }

  Future<void> refreshPendingInvoices() async {
    if (_chatId == null) return;
    try {
      _pendingInvoices = await _api.getPendingInvoices(_chatId!);
      notifyListeners();
    } catch (e) {
      debugPrint('Pending invoices refresh error: $e');
    }
  }

  Future<void> refreshSentInvoices() async {
    if (_chatId == null) return;
    try {
      _sentInvoices = await _api.getSentInvoices(_chatId!);
      notifyListeners();
    } catch (e) {
      debugPrint('Sent invoices refresh error: $e');
    }
  }

  Future<void> refreshMerchants() async {
    try {
      _allMerchants = await _api.listMerchants();
      notifyListeners();
    } catch (e) {
      debugPrint('Merchants refresh error: $e');
    }
  }

  void _setLoading(bool val) {
    _isLoading = val;
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
