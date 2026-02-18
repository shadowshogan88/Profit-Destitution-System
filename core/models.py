from decimal import Decimal
import secrets

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class User(AbstractUser):
    class UserType(models.TextChoices):
        ADMIN = "admin", "Admin"
        USER = "user", "User"

    user_type = models.CharField(
        max_length=10,
        choices=UserType.choices,
        default=UserType.USER,
    )
    referral_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    referred_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="downlines",
    )

    @classmethod
    def generate_referral_code(cls) -> str:
        while True:
            code = f"REF{secrets.token_hex(4).upper()}"
            if not cls.objects.filter(referral_code=code).exists():
                return code

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        if self.is_superuser:
            self.user_type = self.UserType.ADMIN
        if self.user_type == self.UserType.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.username


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} wallet"


class InvestmentWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="investment_wallet")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} investment wallet"


class WalletTransaction(models.Model):
    class TxType(models.TextChoices):
        CREDIT = "CREDIT", "Credit"
        DEBIT = "DEBIT", "Debit"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallet_transactions")
    tx_type = models.CharField(max_length=10, choices=TxType.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} {self.tx_type} {self.amount}"


class Investment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    package = models.ForeignKey(
        "InvestmentPackage",
        on_delete=models.SET_NULL,
        related_name="investments",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="investments")
    principal_amount = models.DecimalField(max_digits=14, decimal_places=2)
    profit_realized = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    duration_days = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    principal_returned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Investment#{self.pk} by {self.user.username}"


class CommissionRate(models.Model):
    level = models.PositiveSmallIntegerField(unique=True)
    rate_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )

    class Meta:
        ordering = ["level"]

    def __str__(self) -> str:
        return f"Level {self.level}: {self.rate_percent}%"


class CommissionLog(models.Model):
    beneficiary = models.ForeignKey(User, on_delete=models.CASCADE, related_name="commission_earnings")
    source_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="commission_sources")
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name="commission_logs")
    level = models.PositiveSmallIntegerField()
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    profit_base = models.DecimalField(max_digits=14, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return (
            f"{self.beneficiary.username} earned {self.commission_amount} "
            f"from {self.source_user.username} L{self.level}"
        )


class PaymentMethod(models.Model):
    name = models.CharField(max_length=100, unique=True)
    account_details = models.TextField(blank=True)
    instruction = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class InvestmentPackage(models.Model):
    name = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    duration_days = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.duration_days}d)"


class ManualPaymentRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="manual_payment_requests")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=100)
    transaction_reference = models.CharField(max_length=120, blank=True)
    details = models.TextField()
    proof_image = models.FileField(upload_to="manual_payments/", null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    wallet_credited = models.BooleanField(default=False)
    credited_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PaymentRequest#{self.pk} {self.user.username} {self.amount} {self.status}"


@receiver(post_save, sender=User)
def create_wallet_for_user(sender, instance: User, created: bool, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)
        InvestmentWallet.objects.get_or_create(user=instance)


@receiver(post_save, sender=ManualPaymentRequest)
def credit_wallet_when_manual_payment_approved(sender, instance: ManualPaymentRequest, **kwargs):
    if instance.status != ManualPaymentRequest.Status.APPROVED or instance.wallet_credited:
        return

    with transaction.atomic():
        locked = (
            ManualPaymentRequest.objects.select_for_update()
            .select_related("user")
            .get(pk=instance.pk)
        )
        if locked.status != ManualPaymentRequest.Status.APPROVED or locked.wallet_credited:
            return

        wallet, _ = Wallet.objects.get_or_create(user=locked.user)
        wallet.balance = wallet.balance + locked.amount
        wallet.save(update_fields=["balance", "updated_at"])

        WalletTransaction.objects.create(
            user=locked.user,
            tx_type=WalletTransaction.TxType.CREDIT,
            amount=locked.amount,
            description=f"Manual payment approved (Request #{locked.pk})",
        )

        locked.wallet_credited = True
        locked.credited_at = timezone.now()
        locked.save(update_fields=["wallet_credited", "credited_at", "updated_at"])
