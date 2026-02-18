from decimal import Decimal, ROUND_DOWN
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    CommissionLog,
    CommissionRate,
    Investment,
    InvestmentWallet,
    InvestmentPackage,
    User,
    WalletTransaction,
)

MAX_LEVEL = 5
TWOPLACES = Decimal("0.01")


def to_2dp(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_DOWN)


def get_rate_map() -> dict[int, Decimal]:
    rates = {
        item.level: item.rate_percent
        for item in CommissionRate.objects.filter(level__lte=MAX_LEVEL)
    }
    defaults = {
        1: Decimal("10.00"),
        2: Decimal("5.00"),
        3: Decimal("3.00"),
        4: Decimal("2.00"),
        5: Decimal("1.00"),
    }
    for level, default_rate in defaults.items():
        rates.setdefault(level, default_rate)
    return rates


@transaction.atomic
def credit_wallet(user: User, amount: Decimal, description: str) -> None:
    wallet = user.wallet
    wallet.balance = to_2dp(wallet.balance + amount)
    wallet.save(update_fields=["balance", "updated_at"])
    WalletTransaction.objects.create(
        user=user,
        tx_type=WalletTransaction.TxType.CREDIT,
        amount=to_2dp(amount),
        description=description,
    )


@transaction.atomic
def debit_wallet(user: User, amount: Decimal, description: str) -> None:
    wallet = user.wallet
    if wallet.balance < amount:
        raise ValueError("Insufficient wallet balance")
    wallet.balance = to_2dp(wallet.balance - amount)
    wallet.save(update_fields=["balance", "updated_at"])
    WalletTransaction.objects.create(
        user=user,
        tx_type=WalletTransaction.TxType.DEBIT,
        amount=to_2dp(amount),
        description=description,
    )


@transaction.atomic
def transfer_wallet_to_investment_wallet(user: User, amount: Decimal, description: str) -> None:
    amount = to_2dp(amount)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    debit_wallet(user, amount, description)
    investment_wallet, _ = InvestmentWallet.objects.get_or_create(user=user)
    investment_wallet.balance = to_2dp(investment_wallet.balance + amount)
    investment_wallet.save(update_fields=["balance", "updated_at"])


@transaction.atomic
def transfer_investment_wallet_to_wallet(user: User, amount: Decimal, description: str) -> None:
    amount = to_2dp(amount)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    investment_wallet, _ = InvestmentWallet.objects.get_or_create(user=user)
    if investment_wallet.balance < amount:
        raise ValueError("Insufficient investment wallet balance")

    investment_wallet.balance = to_2dp(investment_wallet.balance - amount)
    investment_wallet.save(update_fields=["balance", "updated_at"])
    credit_wallet(user, amount, description)


@transaction.atomic
def create_investment(user: User, principal_amount: Decimal, from_wallet: bool = False) -> Investment:
    principal_amount = to_2dp(principal_amount)
    if principal_amount <= 0:
        raise ValueError("Investment amount must be greater than zero")

    if from_wallet:
        debit_wallet(user, principal_amount, "Investment principal deduction")

    return Investment.objects.create(user=user, principal_amount=principal_amount)


@transaction.atomic
def create_package_investment(user: User, package: InvestmentPackage) -> Investment:
    amount = to_2dp(package.amount)
    if amount <= 0:
        raise ValueError("Package amount must be greater than zero")
    if package.duration_days <= 0:
        raise ValueError("Package duration must be greater than zero")

    transfer_wallet_to_investment_wallet(
        user,
        amount,
        f"Transfer to investment wallet for package {package.name}",
    )

    now = timezone.now()
    return Investment.objects.create(
        user=user,
        package=package,
        principal_amount=amount,
        duration_days=package.duration_days,
        starts_at=now,
        ends_at=now + timedelta(days=package.duration_days),
        status=Investment.Status.ACTIVE,
    )


@transaction.atomic
def settle_matured_investments(user: User | None = None) -> int:
    qs = Investment.objects.select_for_update().filter(
        status=Investment.Status.ACTIVE,
        principal_returned=False,
        ends_at__isnull=False,
        ends_at__lte=timezone.now(),
    )
    if user is not None:
        qs = qs.filter(user=user)

    processed = 0
    for inv in qs.select_related("user"):
        transfer_investment_wallet_to_wallet(
            inv.user,
            inv.principal_amount,
            f"Principal returned after package period (Investment #{inv.pk})",
        )
        inv.principal_returned = True
        inv.status = Investment.Status.COMPLETED
        inv.save(update_fields=["principal_returned", "status"])
        processed += 1
    return processed


@transaction.atomic
def realize_profit(investment: Investment, new_profit_amount: Decimal) -> None:
    new_profit_amount = to_2dp(new_profit_amount)
    if new_profit_amount <= 0:
        raise ValueError("Profit amount must be greater than zero")

    # Profit can be added in chunks; commissions are generated only on the new profit chunk.
    investment.profit_realized = to_2dp(investment.profit_realized + new_profit_amount)
    investment.save(update_fields=["profit_realized"])

    # Profit itself lands in investor wallet.
    credit_wallet(
        investment.user,
        new_profit_amount,
        f"Profit realized for investment #{investment.pk}",
    )

    distribute_commission_upward(investment, new_profit_amount)


@transaction.atomic
def distribute_commission_upward(investment: Investment, profit_chunk: Decimal) -> None:
    source_user = investment.user
    current = source_user.referred_by
    level = 1
    rates = get_rate_map()

    while current and level <= MAX_LEVEL:
        rate_percent = rates[level]
        commission_amount = to_2dp((profit_chunk * rate_percent) / Decimal("100"))

        if commission_amount > 0:
            credit_wallet(
                current,
                commission_amount,
                f"Level {level} commission from {source_user.username}",
            )
            CommissionLog.objects.create(
                beneficiary=current,
                source_user=source_user,
                investment=investment,
                level=level,
                rate_percent=rate_percent,
                profit_base=profit_chunk,
                commission_amount=commission_amount,
            )

        current = current.referred_by
        level += 1
