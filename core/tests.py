from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import (
    CommissionLog,
    CommissionRate,
    InvestmentPackage,
    ProfitDistribution,
    ProfitDistributionEntry,
    UnsettledBalanceAccount,
    UnsettledBalanceEntry,
    User,
)
from .services import (
    create_investment,
    credit_wallet,
    create_package_investment,
    distribute_profit_to_active_investors,
    realize_profit,
    settle_matured_investments,
)


class ReferralCommissionTests(TestCase):
    def setUp(self):
        CommissionRate.objects.bulk_create(
            [
                CommissionRate(level=1, rate_percent=Decimal("3.00")),
                CommissionRate(level=2, rate_percent=Decimal("4.50")),
                CommissionRate(level=3, rate_percent=Decimal("6.00")),
                CommissionRate(level=4, rate_percent=Decimal("7.50")),
                CommissionRate(level=5, rate_percent=Decimal("9.00")),
                CommissionRate(level=6, rate_percent=Decimal("70.00")),
            ]
        )

    def test_commission_goes_upward_max_5_levels(self):
        u1 = User.objects.create_user(username="u1", password="x")
        u2 = User.objects.create_user(username="u2", password="x", referred_by=u1)
        u3 = User.objects.create_user(username="u3", password="x", referred_by=u2)
        u4 = User.objects.create_user(username="u4", password="x", referred_by=u3)
        u5 = User.objects.create_user(username="u5", password="x", referred_by=u4)
        u6 = User.objects.create_user(username="u6", password="x", referred_by=u5)
        u7 = User.objects.create_user(username="u7", password="x", referred_by=u6)

        inv = create_investment(u7, Decimal("1000.00"), from_wallet=False)
        realize_profit(inv, Decimal("100.00"))

        u1.refresh_from_db()
        u2.refresh_from_db()
        u3.refresh_from_db()
        u4.refresh_from_db()
        u5.refresh_from_db()
        u6.refresh_from_db()
        u7.refresh_from_db()

        self.assertEqual(u7.wallet.balance, Decimal("70.00"))  # Investor gets L6 own profit
        self.assertEqual(u6.wallet.balance, Decimal("3.00"))  # nearest gets L1
        self.assertEqual(u5.wallet.balance, Decimal("4.50"))  # next gets L2
        self.assertEqual(u4.wallet.balance, Decimal("6.00"))  # next gets L3
        self.assertEqual(u3.wallet.balance, Decimal("7.50"))  # next gets L4
        self.assertEqual(u2.wallet.balance, Decimal("9.00"))  # farthest gets L5
        self.assertEqual(u1.wallet.balance, Decimal("0.00"))  # No L6 payout

        self.assertEqual(CommissionLog.objects.count(), 5)

    def test_missing_uplines_go_to_unsettled_balance(self):
        u1 = User.objects.create_user(username="root", password="x")
        u2 = User.objects.create_user(username="child", password="x", referred_by=u1)

        inv = create_investment(u2, Decimal("1000.00"), from_wallet=False)
        realize_profit(inv, Decimal("100.00"))

        u1.refresh_from_db()
        u2.refresh_from_db()

        self.assertEqual(u1.wallet.balance, Decimal("3.00"))
        self.assertEqual(u2.wallet.balance, Decimal("70.00"))

        unsettled_account = UnsettledBalanceAccount.objects.get(name="Unsettled Balance")
        self.assertEqual(unsettled_account.balance, Decimal("27.00"))

        unsettled_entry = UnsettledBalanceEntry.objects.latest("created_at")
        self.assertEqual(unsettled_entry.amount, Decimal("27.00"))
        self.assertEqual(unsettled_entry.missing_from_level, 2)
        self.assertEqual(unsettled_entry.missing_to_level, 5)

    def test_upper_missing_levels_go_unsettled_after_paid_existing_uplines(self):
        u1 = User.objects.create_user(username="a1", password="x")
        u2 = User.objects.create_user(username="a2", password="x", referred_by=u1)
        u3 = User.objects.create_user(username="a3", password="x", referred_by=u2)
        investor = User.objects.create_user(username="a4", password="x", referred_by=u3)

        inv = create_investment(investor, Decimal("1000.00"), from_wallet=False)
        realize_profit(inv, Decimal("100.00"))

        u1.refresh_from_db()
        u2.refresh_from_db()
        u3.refresh_from_db()
        investor.refresh_from_db()

        self.assertEqual(u1.wallet.balance, Decimal("6.00"))  # farthest existing gets L3
        self.assertEqual(u2.wallet.balance, Decimal("4.50"))  # middle gets L2
        self.assertEqual(u3.wallet.balance, Decimal("3.00"))  # nearest gets L1
        self.assertEqual(investor.wallet.balance, Decimal("70.00"))

        unsettled_entry = UnsettledBalanceEntry.objects.latest("created_at")
        self.assertEqual(unsettled_entry.amount, Decimal("16.50"))
        self.assertEqual(unsettled_entry.missing_from_level, 4)
        self.assertEqual(unsettled_entry.missing_to_level, 5)

    def test_package_investment_locks_and_returns_principal(self):
        user = User.objects.create_user(username="investor", password="x")
        package = InvestmentPackage.objects.create(name="Starter-7D", amount=Decimal("500.00"), duration_days=7)

        credit_wallet(user, Decimal("1000.00"), "Seed wallet")
        self.assertEqual(user.wallet.balance, Decimal("1000.00"))
        self.assertEqual(user.investment_wallet.balance, Decimal("0.00"))

        inv = create_package_investment(user, package, Decimal("500.00"))
        user.refresh_from_db()
        self.assertEqual(user.wallet.balance, Decimal("500.00"))
        self.assertEqual(user.investment_wallet.balance, Decimal("500.00"))
        self.assertFalse(inv.principal_returned)

        inv.ends_at = timezone.now() - timedelta(days=1)
        inv.save(update_fields=["ends_at"])
        settled = settle_matured_investments(user=user)
        self.assertEqual(settled, 1)

        user.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(user.wallet.balance, Decimal("1000.00"))
        self.assertEqual(user.investment_wallet.balance, Decimal("0.00"))
        self.assertTrue(inv.principal_returned)

    def test_admin_distribution_spreads_profit_by_active_principal(self):
        u1 = User.objects.create_user(username="dist_u1", password="x")
        u2 = User.objects.create_user(username="dist_u2", password="x")
        p1 = InvestmentPackage.objects.create(name="Pack-100", amount=Decimal("100.00"), duration_days=7)
        p2 = InvestmentPackage.objects.create(name="Pack-300", amount=Decimal("300.00"), duration_days=7)

        credit_wallet(u1, Decimal("100.00"), "Seed")
        credit_wallet(u2, Decimal("300.00"), "Seed")
        create_package_investment(u1, p1, Decimal("100.00"))
        create_package_investment(u2, p2, Decimal("300.00"))

        distribution = distribute_profit_to_active_investors(Decimal("40.00"))
        u1.refresh_from_db()
        u2.refresh_from_db()

        self.assertEqual(distribution.total_active_principal, Decimal("400.00"))
        self.assertEqual(distribution.distributed_amount, Decimal("40.00"))
        self.assertEqual(distribution.remainder_amount, Decimal("0.00"))
        self.assertEqual(u1.wallet.balance, Decimal("7.00"))
        self.assertEqual(u2.wallet.balance, Decimal("21.00"))
        self.assertEqual(ProfitDistribution.objects.count(), 1)
        self.assertEqual(ProfitDistributionEntry.objects.count(), 2)
