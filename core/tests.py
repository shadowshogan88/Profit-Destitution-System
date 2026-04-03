from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    CommissionLog,
    CommissionRate,
    EmailVerificationToken,
    InvestmentReturnRequest,
    WithdrawalOtpToken,
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
                CommissionRate(level=1, rate_percent=Decimal("10.00")),
                CommissionRate(level=2, rate_percent=Decimal("5.00")),
                CommissionRate(level=3, rate_percent=Decimal("3.00")),
                CommissionRate(level=4, rate_percent=Decimal("2.00")),
                CommissionRate(level=5, rate_percent=Decimal("1.00")),
                CommissionRate(level=6, rate_percent=Decimal("79.00")),
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

        self.assertEqual(u7.wallet.balance, Decimal("79.00"))  # Investor gets L6 own profit
        self.assertEqual(u6.wallet.balance, Decimal("10.00"))  # L1 10%
        self.assertEqual(u5.wallet.balance, Decimal("5.00"))  # L2 5%
        self.assertEqual(u4.wallet.balance, Decimal("3.00"))  # L3 3%
        self.assertEqual(u3.wallet.balance, Decimal("2.00"))  # L4 2%
        self.assertEqual(u2.wallet.balance, Decimal("1.00"))  # L5 1%
        self.assertEqual(u1.wallet.balance, Decimal("0.00"))  # No L6 payout

        self.assertEqual(CommissionLog.objects.count(), 5)

    def test_missing_uplines_go_to_unsettled_balance(self):
        u1 = User.objects.create_user(username="root", password="x")
        u2 = User.objects.create_user(username="child", password="x", referred_by=u1)

        inv = create_investment(u2, Decimal("1000.00"), from_wallet=False)
        realize_profit(inv, Decimal("100.00"))

        u1.refresh_from_db()
        u2.refresh_from_db()

        self.assertEqual(u1.wallet.balance, Decimal("10.00"))
        self.assertEqual(u2.wallet.balance, Decimal("79.00"))

        unsettled_account = UnsettledBalanceAccount.objects.get(name="Unsettled Balance")
        self.assertEqual(unsettled_account.balance, Decimal("11.00"))

        unsettled_entry = UnsettledBalanceEntry.objects.latest("created_at")
        self.assertEqual(unsettled_entry.amount, Decimal("11.00"))
        self.assertEqual(unsettled_entry.missing_from_level, 2)
        self.assertEqual(unsettled_entry.missing_to_level, 5)

    def test_upline_gets_commission_without_having_active_investment(self):
        u1 = User.objects.create_user(username="no_invest_upline", password="x")
        u2 = User.objects.create_user(username="earning_child", password="x", referred_by=u1)
        package = InvestmentPackage.objects.create(name="Commission-Pack", amount=Decimal("500.00"), duration_days=7)

        credit_wallet(u2, Decimal("500.00"), "Seed wallet")
        create_package_investment(u2, package, Decimal("500.00"))

        distribution = distribute_profit_to_active_investors(Decimal("100.00"))

        u1.refresh_from_db()
        u2.refresh_from_db()

        self.assertEqual(distribution.total_amount, Decimal("100.00"))
        self.assertEqual(u1.investments.count(), 0)
        self.assertEqual(u1.wallet.balance, Decimal("10.00"))
        self.assertEqual(u2.wallet.balance, Decimal("79.00"))

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
        updated = settle_matured_investments(user=user)
        self.assertEqual(updated, 1)

        user.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(user.wallet.balance, Decimal("500.00"))
        self.assertEqual(user.investment_wallet.balance, Decimal("500.00"))
        self.assertFalse(inv.principal_returned)

        req = InvestmentReturnRequest.objects.create(
            investment=inv,
            status=InvestmentReturnRequest.Status.PENDING,
            requested_at=timezone.now() - timedelta(days=2),
            scheduled_return_at=timezone.now() - timedelta(days=1),
        )
        processed = settle_matured_investments(user=user)
        self.assertEqual(processed, 0)

        req.refresh_from_db()
        user.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(req.status, InvestmentReturnRequest.Status.PROCESSED)
        self.assertEqual(user.wallet.balance, Decimal("1000.00"))
        self.assertEqual(user.investment_wallet.balance, Decimal("0.00"))
        self.assertTrue(inv.principal_returned)
        self.assertEqual(inv.status, inv.Status.COMPLETED)

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
        self.assertEqual(u1.wallet.balance, Decimal("7.90"))
        self.assertEqual(u2.wallet.balance, Decimal("23.70"))
        self.assertEqual(ProfitDistribution.objects.count(), 1)
        self.assertEqual(ProfitDistributionEntry.objects.count(), 2)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_OTP_EXPIRY_MINUTES=10,
)
class EmailVerificationTests(TestCase):
    def test_verify_email_activates_user(self):
        user = User.objects.create_user(
            username="verify_user",
            password="x",
            email="verify_user@example.com",
            is_active=False,
            email_verified=False,
        )
        token_obj = EmailVerificationToken.create_for_user(user=user, otp_valid_minutes=10)
        url = reverse("email-verify") + f"?token={token_obj.token}"
        resp = self.client.post(url, {"token": str(token_obj.token), "otp_code": token_obj.otp_code})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/user-dashboard/", resp["Location"])

        user.refresh_from_db()
        token_obj.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(token_obj.used_at)

    def test_verify_email_rejects_wrong_otp(self):
        user = User.objects.create_user(
            username="verify_user2",
            password="x",
            email="verify_user2@example.com",
            is_active=False,
            email_verified=False,
        )
        token_obj = EmailVerificationToken.create_for_user(user=user, otp_valid_minutes=10)
        url = reverse("email-verify") + f"?token={token_obj.token}"
        resp = self.client.post(url, {"token": str(token_obj.token), "otp_code": "000000"})
        self.assertEqual(resp.status_code, 200)

        user.refresh_from_db()
        token_obj.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(user.email_verified)
        self.assertIsNone(token_obj.used_at)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class WithdrawalOtpTests(TestCase):
    def test_withdrawal_requires_otp_verification(self):
        user = User.objects.create_user(
            username="w_user",
            password="x",
            email="w_user@example.com",
            is_active=True,
            email_verified=True,
        )
        credit_wallet(user, Decimal("100.00"), "Seed wallet")
        self.client.force_login(user)

        from .models import WithdrawalMethod

        method = WithdrawalMethod.objects.create(
            name="USDT TRC20",
            is_active=True,
            withdrawal_fee_percent=Decimal("0.00"),
        )

        resp = self.client.post(
            reverse("manual-withdrawal"),
            {"amount": "50", "withdrawal_method_id": method.id, "account_details": "TRC20:xxxx"},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        token = WithdrawalOtpToken.objects.first()
        self.assertIsNotNone(token)
        self.assertFalse(token.withdrawal_request.email_otp_verified)

        verify_url = reverse("withdrawal-otp-verify") + f"?token={token.token}"
        resp2 = self.client.post(verify_url, {"token": str(token.token), "otp_code": token.otp_code})
        self.assertEqual(resp2.status_code, 302)
        token.withdrawal_request.refresh_from_db()
        self.assertTrue(token.withdrawal_request.email_otp_verified)
