from django.contrib import admin

from .models import (
    CommissionLog,
    CommissionRate,
    Investment,
    InvestmentPackage,
    InvestmentWallet,
    ManualPaymentRequest,
    PaymentMethod,
    User,
    Wallet,
    WalletTransaction,
)

admin.site.register(User)
admin.site.register(Wallet)
admin.site.register(InvestmentWallet)
admin.site.register(WalletTransaction)
admin.site.register(Investment)
admin.site.register(InvestmentPackage)
admin.site.register(CommissionRate)
admin.site.register(CommissionLog)
@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "account_details", "instruction")


@admin.register(ManualPaymentRequest)
class ManualPaymentRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "amount",
        "payment_method",
        "status",
        "wallet_credited",
        "created_at",
    )
    list_filter = ("status", "wallet_credited", "payment_method")
    search_fields = ("user__username", "transaction_reference", "payment_method")
