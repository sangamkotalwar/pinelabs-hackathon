class MerchantModel {
  final int id;
  final String telegramChatId;
  final String businessName;
  final String? email;
  final String? phone;
  final DateTime? createdAt;

  MerchantModel({
    required this.id,
    required this.telegramChatId,
    required this.businessName,
    this.email,
    this.phone,
    this.createdAt,
  });

  factory MerchantModel.fromJson(Map<String, dynamic> json) {
    return MerchantModel(
      id: json['id'] as int,
      telegramChatId: json['telegram_chat_id'] as String,
      businessName: json['business_name'] as String,
      email: json['email'] as String?,
      phone: json['phone'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : null,
    );
  }
}

class InvoiceModel {
  final int id;
  final String invoiceNumber;
  final String? fromBusiness;
  final String? toBusiness;
  final double amount;
  final String status;
  final String? paymentLink;
  final DateTime createdAt;
  final DateTime? paidAt;
  final String? description;

  InvoiceModel({
    required this.id,
    required this.invoiceNumber,
    this.fromBusiness,
    this.toBusiness,
    required this.amount,
    required this.status,
    this.paymentLink,
    required this.createdAt,
    this.paidAt,
    this.description,
  });

  factory InvoiceModel.fromJson(Map<String, dynamic> json) {
    return InvoiceModel(
      id: json['id'] as int,
      invoiceNumber: json['invoice_number'] as String,
      fromBusiness: (json['from_business'] ?? json['from']) as String?,
      toBusiness: (json['to_business'] ?? json['to']) as String?,
      amount: (json['amount'] as num).toDouble(),
      status: json['status'] as String,
      paymentLink: json['payment_link'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      paidAt: json['paid_at'] != null
          ? DateTime.parse(json['paid_at'] as String)
          : null,
      description: json['description'] as String?,
    );
  }

  bool get isPaid => status == 'paid';
  bool get isPending => status == 'pending' || status == 'payment_link_sent';
  bool get isRefunded => status == 'refunded';
}

class BalanceSummary {
  final double totalPayable;
  final double totalReceivable;
  final double net;
  final int payableCount;
  final int receivableCount;

  BalanceSummary({
    required this.totalPayable,
    required this.totalReceivable,
    required this.net,
    required this.payableCount,
    required this.receivableCount,
  });

  factory BalanceSummary.fromJson(Map<String, dynamic> json) {
    return BalanceSummary(
      totalPayable: (json['total_payable'] as num).toDouble(),
      totalReceivable: (json['total_receivable'] as num).toDouble(),
      net: (json['net'] as num).toDouble(),
      payableCount: json['payable_count'] as int,
      receivableCount: json['receivable_count'] as int,
    );
  }
}

class DashboardData {
  final MerchantModel merchant;
  final BalanceSummary balance;
  final List<InvoiceModel> recentSent;
  final List<InvoiceModel> recentPending;

  DashboardData({
    required this.merchant,
    required this.balance,
    required this.recentSent,
    required this.recentPending,
  });

  factory DashboardData.fromJson(Map<String, dynamic> json) {
    return DashboardData(
      merchant: MerchantModel.fromJson(json['merchant'] as Map<String, dynamic>),
      balance: BalanceSummary.fromJson(json['balance'] as Map<String, dynamic>),
      recentSent: (json['recent_sent'] as List)
          .map((e) => InvoiceModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      recentPending: (json['recent_pending'] as List)
          .map((e) => InvoiceModel.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
