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
    UnsettledBalanceAccount,
    UnsettledBalanceEntry,
    User,
    WalletTransaction,
)

REFERRAL_MAX_LEVEL = 5
OWN_PROFIT_LEVEL = 6
TOTAL_LEVELS = 6
TWOPLACES = Decimal("0.01")


def to_2dp(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_DOWN)


def get_rate_map() -> dict[int, Decimal]:
    configured = list(
        CommissionRate.objects.filter(level__lte=TOTAL_LEVELS).order_by("level")
    )
    if not configured:
        return {}

    rates = {item.level: item.rate_percent for item in configured}
    for level in range(1, TOTAL_LEVELS + 1):
        rates.setdefault(level, Decimal("0.00"))
    return rates


def validate_distribution_rates(rates: dict[int, Decimal]) -> None:
    if not rates:
        raise ValueError("Configure CommissionRate levels 1 to 6 before distributing profit.")

    missing_levels = [level for level in range(1, TOTAL_LEVELS + 1) if level not in rates]
    if missing_levels:
        raise ValueError("Configure CommissionRate levels 1 to 6 before distributing profit.")

    total_percent = to_2dp(sum((rates[level] for level in range(1, TOTAL_LEVELS + 1)), Decimal("0.00")))
    if total_percent != Decimal("100.00"):
        raise ValueError("L1 to L6 percentages must total exactly 100%.")


def get_won_profit_amount(gross_profit: Decimal, rates: dict[int, Decimal]) -> Decimal:
    own_profit_percent = rates[OWN_PROFIT_LEVEL]
    return to_2dp((gross_profit * own_profit_percent) / Decimal("100"))


@transaction.atomic
def credit_unsettled_balance(
    amount: Decimal,
    description: str,
    source_user: User | None = None,
    investment: Investment | None = None,
    distribution: ProfitDistribution | None = None,
    missing_from_level: int | None = None,
    missing_to_level: int | None = None,
) -> None:
    amount = to_2dp(amount)
    if amount <= 0:
        return

    account, _ = UnsettledBalanceAccount.objects.select_for_update().get_or_create(
        name="Unsettled Balance"
    )
    account.balance = to_2dp(account.balance + amount)
    account.save(update_fields=["balance", "updated_at"])

    UnsettledBalanceEntry.objects.create(
        account=account,
        amount=amount,
        description=description,
        source_user=source_user,
        investment=investment,
        distribution=distribution,
        missing_from_level=missing_from_level,
        missing_to_level=missing_to_level,
    )


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
def create_package_investment(
    user: User,
    package: InvestmentPackage,
    amount: Decimal,
) -> Investment:
    amount = to_2dp(amount)
    if amount <= 0:
        raise ValueError("Investment amount must be greater than zero")
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

    rates = get_rate_map()
    validate_distribution_rates(rates)
    referral_commission, _ = distribute_commission_upward(investment, new_profit_amount, rates=rates)
    net_profit = get_won_profit_amount(new_profit_amount, rates)

    # Investor gets the configured L6 own-profit share from gross profit.
    investment.profit_realized = to_2dp(investment.profit_realized + net_profit)
    investment.save(update_fields=["profit_realized"])
    if net_profit > 0:
        credit_wallet(
            investment.user,
            net_profit,
            f"Profit realized for investment #{investment.pk} (net won profit)",
        )
        try:
            from . import notifications

            transaction.on_commit(
                lambda: notifications.send_profit_received(
                    investment.user,
                    amount=net_profit,
                    note=f"Profit realized for Investment {investment.investment_code or investment.pk}.",
                )
            )
        except Exception:
            pass


@transaction.atomic
def distribute_commission_upward(
    investment: Investment,
    profit_chunk: Decimal,
    distribution: ProfitDistribution | None = None,
    rates: dict[int, Decimal] | None = None,
) -> tuple[Decimal, Decimal]:
    source_user = investment.user
    rates = rates or get_rate_map()
    validate_distribution_rates(rates)
    target_max_level = REFERRAL_MAX_LEVEL

    uplines: list[User] = []
    current = source_user.referred_by
    while current and len(uplines) < target_max_level:
        uplines.append(current)
        current = current.referred_by

    computed: dict[int, dict[str, Decimal]] = {}
    total_paid_commission = Decimal("0.00")
    total_theoretical_commission = Decimal("0.00")

    for level in range(1, target_max_level + 1):
        rate_percent = rates[level]
        profit_base = profit_chunk
        commission_amount = to_2dp((profit_base * rate_percent) / Decimal("100"))

        computed[level] = {
            "rate_percent": rate_percent,
            "profit_base": profit_base,
            "commission_amount": commission_amount,
        }
        total_theoretical_commission = to_2dp(total_theoretical_commission + commission_amount)

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
            distribution=distribution,
            level=level,
            rate_percent=row["rate_percent"],
            profit_base=row["profit_base"],
            commission_amount=commission_amount,
        )
        total_paid_commission = to_2dp(total_paid_commission + commission_amount)

    unsettled_commission = to_2dp(total_theoretical_commission - total_paid_commission)
    if unsettled_commission > 0:
        missing_from = len(uplines) + 1 if len(uplines) < target_max_level else None
        missing_to = target_max_level if len(uplines) < target_max_level else None
        credit_unsettled_balance(
            unsettled_commission,
            f"Missing upline levels commission from {source_user.username}",
            source_user=source_user,
            investment=investment,
            distribution=distribution,
            missing_from_level=missing_from,
            missing_to_level=missing_to,
        )

    return total_theoretical_commission, unsettled_commission


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
            total_unsettled_commission=Decimal("0.00"),
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
            total_unsettled_commission=Decimal("0.00"),
            total_won_profit=Decimal("0.00"),
            note=(note or "").strip(),
            created_by=created_by,
        )

    distribution = ProfitDistribution.objects.create(
        total_amount=total_amount,
        total_active_principal=total_active_principal,
        total_referral_commission=Decimal("0.00"),
        total_unsettled_commission=Decimal("0.00"),
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
    total_unsettled_commission = Decimal("0.00")
    total_won_profit = Decimal("0.00")
    rates = get_rate_map()
    validate_distribution_rates(rates)
    for row in rows:
        gross_profit = row["gross_profit"]
        if gross_profit <= 0:
            continue

        investment = row["investment"]
        referral_commission, unsettled_commission = distribute_commission_upward(
            investment,
            gross_profit,
            distribution=distribution,
            rates=rates,
        )
        won_profit = get_won_profit_amount(gross_profit, rates)

        if won_profit > 0:
            investment.profit_realized = to_2dp(investment.profit_realized + won_profit)
            investment.save(update_fields=["profit_realized"])
            credit_wallet(
                row["user"],
                won_profit,
                f"Admin profit distribution #{distribution.pk} (net won profit)",
            )
            try:
                from . import notifications

                transaction.on_commit(
                    lambda user=row["user"], amount=won_profit, dist_id=distribution.pk: notifications.send_profit_received(
                        user,
                        amount=amount,
                        note=f"Profit distribution #{dist_id} credited to your wallet.",
                    )
                )
            except Exception:
                pass

        total_referral_commission = to_2dp(total_referral_commission + referral_commission)
        total_unsettled_commission = to_2dp(total_unsettled_commission + unsettled_commission)
        total_won_profit = to_2dp(total_won_profit + won_profit)
        ProfitDistributionEntry.objects.create(
            distribution=distribution,
            user=row["user"],
            investment=investment,
            active_principal=row["active_principal"],
            gross_profit=gross_profit,
            referral_commission=referral_commission,
            unsettled_commission=unsettled_commission,
            won_profit=won_profit,
            payout_amount=won_profit,
        )

    distribution.distributed_amount = distributed_amount
    distribution.remainder_amount = remainder_amount
    distribution.total_referral_commission = total_referral_commission
    distribution.total_unsettled_commission = total_unsettled_commission
    distribution.total_won_profit = total_won_profit
    distribution.save(
        update_fields=[
            "distributed_amount",
            "remainder_amount",
            "total_referral_commission",
            "total_unsettled_commission",
            "total_won_profit",
        ]
    )
    return distribution
