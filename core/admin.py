from django.contrib import admin

from .models import (
    CommissionLog,
    CommissionRate,
    EmailOTP,
    Investment,
    InvestmentPackage,
    InvestmentWallet,
    ManualPaymentRequest,
    ManualWithdrawalRequest,
    PaymentMethod,
    SystemConfiguration,
    User,
    Wallet,
    WalletTransaction,
    WithdrawalMethod,
)

admin.site.register(User)
admin.site.register(Wallet)
admin.site.register(InvestmentWallet)
admin.site.register(WalletTransaction)
admin.site.register(Investment)
admin.site.register(InvestmentPackage)
admin.site.register(CommissionRate)
admin.site.register(CommissionLog)
admin.site.register(EmailOTP)


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ("email_host", "email_port", "email_host_user", "email_use_tls", "email_use_ssl", "updated_at")

    def has_add_permission(self, request):
        return not SystemConfiguration.objects.exists()


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


@admin.register(WithdrawalMethod)
class WithdrawalMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "withdrawal_fee_percent", "withdrawal_fee_fixed", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "account_details", "instruction")


@admin.register(ManualWithdrawalRequest)
class ManualWithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "amount",
        "payment_method",
        "status",
        "wallet_debited",
        "created_at",
    )
    list_filter = ("status", "wallet_debited", "payment_method")
    search_fields = ("user__username", "request_code", "payment_method")
