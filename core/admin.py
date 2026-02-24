from django.contrib import admin
from django.contrib import messages
from django import forms
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from .models import (
    CommissionLog,
    CommissionRate,
    Investment,
    InvestmentPackage,
    InvestmentWallet,
    ManualPaymentRequest,
    PaymentMethod,
    ProfitDistribution,
    ProfitDistributionEntry,
    User,
    Wallet,
    WalletTransaction,
)
from .services import distribute_profit_to_active_investors


class ProfitDistributionAdminForm(forms.ModelForm):
    class Meta:
        model = ProfitDistribution
        fields = "__all__"

    def clean_total_amount(self):
        value = self.cleaned_data["total_amount"]
        if value <= 0:
            raise forms.ValidationError("Total amount must be greater than zero.")
        return value


admin.site.register(Wallet)
admin.site.register(InvestmentWallet)
admin.site.register(Investment)
admin.site.register(InvestmentPackage)
admin.site.register(CommissionRate)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "referrer_username",
        "wallet_balance",
        "invested_amount",
    )
    search_fields = ("username", "referral_code", "referred_by__username")
    list_select_related = ("referred_by",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("referred_by")
        return qs.annotate(
            total_invested=Coalesce(
                Sum("investments__principal_amount"),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2)),
            )
        )

    @admin.display(description="Referrer")
    def referrer_username(self, obj):
        return obj.referred_by.username if obj.referred_by else "-"

    @admin.display(description="Wallet")
    def wallet_balance(self, obj):
        return getattr(getattr(obj, "wallet", None), "balance", 0)

    @admin.display(description="Invested")
    def invested_amount(self, obj):
        return obj.total_invested


@admin.register(CommissionLog)
class CommissionLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "beneficiary",
        "source_user",
        "investment",
        "level",
        "rate_percent",
        "profit_base",
        "commission_amount",
        "created_at",
    )
    list_filter = ("level", "created_at")
    search_fields = (
        "beneficiary__username",
        "source_user__username",
        "investment__id",
    )
    list_select_related = ("beneficiary", "source_user", "investment")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "tx_type",
        "amount",
        "description",
        "created_at",
    )
    list_filter = ("tx_type", "created_at")
    search_fields = ("user__username", "description")
    list_select_related = ("user",)
    ordering = ("-created_at",)


class ProfitDistributionEntryInline(admin.TabularInline):
    model = ProfitDistributionEntry
    extra = 0
    can_delete = False
    fields = (
        "user",
        "investment",
        "active_principal",
        "gross_profit",
        "referral_commission",
        "won_profit",
        "payout_amount",
        "created_at",
    )
    readonly_fields = fields


@admin.register(ProfitDistribution)
class ProfitDistributionAdmin(admin.ModelAdmin):
    form = ProfitDistributionAdminForm
    list_display = (
        "id",
        "total_amount",
        "total_active_principal",
        "distributed_amount",
        "remainder_amount",
        "total_referral_commission",
        "total_won_profit",
        "created_by",
        "created_at",
    )
    readonly_fields = (
        "current_total_invested",
        "total_active_principal",
        "distributed_amount",
        "remainder_amount",
        "total_referral_commission",
        "total_won_profit",
        "created_by",
        "created_at",
    )
    fields = (
        "total_amount",
        "note",
        "current_total_invested",
        "total_active_principal",
        "distributed_amount",
        "remainder_amount",
        "total_referral_commission",
        "total_won_profit",
        "created_by",
        "created_at",
    )
    inlines = [ProfitDistributionEntryInline]

    @admin.display(description="Current Total Invested (All Users)")
    def current_total_invested(self, obj=None):
        total = Investment.objects.aggregate(total=Sum("principal_amount"))["total"]
        return total or 0

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        return request.user.is_staff

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return

        created = distribute_profit_to_active_investors(
            total_amount=obj.total_amount,
            created_by=request.user,
            note=obj.note,
        )

        obj.pk = created.pk
        obj.total_active_principal = created.total_active_principal
        obj.distributed_amount = created.distributed_amount
        obj.remainder_amount = created.remainder_amount
        obj.total_referral_commission = created.total_referral_commission
        obj.total_won_profit = created.total_won_profit
        obj.created_by = created.created_by
        obj.created_at = created.created_at

        if created.distributed_amount > 0:
            messages.success(
                request,
                f"Profit distribution #{created.pk} completed. "
                f"Gross {created.distributed_amount}, referral {created.total_referral_commission}, "
                f"won profit {created.total_won_profit}.",
            )
        else:
            messages.warning(
                request,
                f"Distribution #{created.pk} saved, but no active running package found.",
            )


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
