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
    ProfitDistribution,
    ProfitDistributionEntry,
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

    # Referral commission is distributed first from this profit chunk.
    referral_commission = distribute_commission_upward(investment, new_profit_amount)
    net_profit = to_2dp(new_profit_amount - referral_commission)
    if net_profit < 0:
        net_profit = Decimal("0.00")

    # Investor gets only the net won profit after referral commission.
    investment.profit_realized = to_2dp(investment.profit_realized + net_profit)
    investment.save(update_fields=["profit_realized"])
    if net_profit > 0:
        credit_wallet(
            investment.user,
            net_profit,
            f"Profit realized for investment #{investment.pk} (net won profit)",
        )


@transaction.atomic
def distribute_commission_upward(investment: Investment, profit_chunk: Decimal) -> Decimal:
    source_user = investment.user
    uplines: list[User] = []
    current = source_user.referred_by
    while current and len(uplines) < MAX_LEVEL:
        uplines.append(current)
        current = current.referred_by

    if not uplines:
        return Decimal("0.00")

    rates = get_rate_map()
    computed: dict[int, dict[str, Decimal]] = {}
    total_commission = Decimal("0.00")

    for level in range(1, len(uplines) + 1):
        rate_percent = rates[level]
        if level == 1:
            profit_base = profit_chunk
        else:
            profit_base = computed[level - 1]["commission_amount"]
        commission_amount = to_2dp((profit_base * rate_percent) / Decimal("100"))

        computed[level] = {
            "rate_percent": rate_percent,
            "profit_base": profit_base,
            "commission_amount": commission_amount,
        }

    for level, beneficiary in enumerate(uplines, start=1):
        row = computed[level]
        commission_amount = row["commission_amount"]
        if commission_amount <= 0:
            continue

        credit_wallet(
            beneficiary,
            commission_amount,
            f"Level {level} commission from {source_user.username}",
        )
        CommissionLog.objects.create(
            beneficiary=beneficiary,
            source_user=source_user,
            investment=investment,
            level=level,
            rate_percent=row["rate_percent"],
            profit_base=row["profit_base"],
            commission_amount=commission_amount,
        )
        total_commission = to_2dp(total_commission + commission_amount)

    return total_commission


@transaction.atomic
def distribute_profit_to_active_investors(
    total_amount: Decimal,
    created_by: User | None = None,
    note: str = "",
) -> ProfitDistribution:
    total_amount = to_2dp(total_amount)
    if total_amount <= 0:
        raise ValueError("Distribution amount must be greater than zero")

    settle_matured_investments()
    now = timezone.now()
    active_investments = list(
        Investment.objects.select_for_update()
        .select_related("user")
        .filter(
            status=Investment.Status.ACTIVE,
            package__isnull=False,
            principal_returned=False,
            starts_at__isnull=False,
            ends_at__isnull=False,
            starts_at__lte=now,
            ends_at__gt=now,
        )
        .order_by("-principal_amount", "id")
    )
    if not active_investments:
        return ProfitDistribution.objects.create(
            total_amount=total_amount,
            total_active_principal=Decimal("0.00"),
            distributed_amount=Decimal("0.00"),
            remainder_amount=total_amount,
            total_referral_commission=Decimal("0.00"),
            total_won_profit=Decimal("0.00"),
            note=(note or "").strip(),
            created_by=created_by,
        )

    total_active_principal = to_2dp(
        sum((item.principal_amount for item in active_investments), Decimal("0.00"))
    )
    if total_active_principal <= 0:
        return ProfitDistribution.objects.create(
            total_amount=total_amount,
            total_active_principal=Decimal("0.00"),
            distributed_amount=Decimal("0.00"),
            remainder_amount=total_amount,
            total_referral_commission=Decimal("0.00"),
            total_won_profit=Decimal("0.00"),
            note=(note or "").strip(),
            created_by=created_by,
        )

    distribution = ProfitDistribution.objects.create(
        total_amount=total_amount,
        total_active_principal=total_active_principal,
        total_referral_commission=Decimal("0.00"),
        total_won_profit=Decimal("0.00"),
        note=(note or "").strip(),
        created_by=created_by,
    )

    rows: list[dict] = []
    for item in active_investments:
        active_principal = to_2dp(item.principal_amount)
        payout_amount = to_2dp((total_amount * active_principal) / total_active_principal)
        rows.append(
            {
                "investment": item,
                "user": item.user,
                "active_principal": active_principal,
                "gross_profit": payout_amount,
            }
        )

    distributed_amount = to_2dp(sum((row["gross_profit"] for row in rows), Decimal("0.00")))
    remainder_amount = to_2dp(total_amount - distributed_amount)
    if remainder_amount > 0 and rows:
        rows[0]["gross_profit"] = to_2dp(rows[0]["gross_profit"] + remainder_amount)
        distributed_amount = to_2dp(sum((row["gross_profit"] for row in rows), Decimal("0.00")))
        remainder_amount = to_2dp(total_amount - distributed_amount)

    total_referral_commission = Decimal("0.00")
    total_won_profit = Decimal("0.00")
    for row in rows:
        gross_profit = row["gross_profit"]
        if gross_profit <= 0:
            continue

        investment = row["investment"]
        referral_commission = distribute_commission_upward(investment, gross_profit)
        won_profit = to_2dp(gross_profit - referral_commission)
        if won_profit < 0:
            won_profit = Decimal("0.00")

        if won_profit > 0:
            investment.profit_realized = to_2dp(investment.profit_realized + won_profit)
            investment.save(update_fields=["profit_realized"])
            credit_wallet(
                row["user"],
                won_profit,
                f"Admin profit distribution #{distribution.pk} (net won profit)",
            )

        total_referral_commission = to_2dp(total_referral_commission + referral_commission)
        total_won_profit = to_2dp(total_won_profit + won_profit)
        ProfitDistributionEntry.objects.create(
            distribution=distribution,
            user=row["user"],
            investment=investment,
            active_principal=row["active_principal"],
            gross_profit=gross_profit,
            referral_commission=referral_commission,
            won_profit=won_profit,
            payout_amount=won_profit,
        )

    distribution.distributed_amount = distributed_amount
    distribution.remainder_amount = remainder_amount
    distribution.total_referral_commission = total_referral_commission
    distribution.total_won_profit = total_won_profit
    distribution.save(
        update_fields=[
            "distributed_amount",
            "remainder_amount",
            "total_referral_commission",
            "total_won_profit",
        ]
    )
    return distribution
