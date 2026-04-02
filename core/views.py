import json
from decimal import Decimal, InvalidOperation

import csv

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.core.exceptions import ValidationError
from django.core import mail
from django.core.mail.backends.smtp import EmailBackend as SmtpEmailBackend
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import (
    CommissionLog,
    EmailConfiguration,
    EmailVerificationToken,
    SystemConfiguration,
    WithdrawalOtpToken,
    Investment,
    InvestmentPackage,
    InvestmentWallet,
    ManualPaymentRequest,
    ManualWithdrawalRequest,
    PaymentMethod,
    ProfitDistribution,
    ProfitDistributionEntry,
    UnsettledBalanceAccount,
    UnsettledBalanceEntry,
    UserNominee,
    WithdrawalMethod,
    Wallet,
    WalletTransaction,
)
from .services import (
    create_investment,
    create_package_investment,
    distribute_profit_to_active_investors,
    realize_profit,
    settle_matured_investments,
)

User = get_user_model()
MAX_REFERRAL_LEVEL = 5


def _mask_email(value: str) -> str:
    value = (value or "").strip()
    if "@" not in value:
        return value
    local, domain = value.split("@", 1)
    if len(local) <= 2:
        local_masked = local[:1] + "*"
    else:
        local_masked = local[:2] + "*" * max(1, len(local) - 2)
    return f"{local_masked}@{domain}"


def _send_email_verification(request: HttpRequest, token_obj: EmailVerificationToken) -> None:
    email_cfg = EmailConfiguration.get_active()
    user = token_obj.user
    verify_url = request.build_absolute_uri(f"{reverse('email-verify')}?token={token_obj.token}")
    context = {
        "app_name": (email_cfg.app_name or getattr(settings, "EMAIL_APP_NAME", "Referral System")),
        "username": user.username,
        "otp_code": token_obj.otp_code,
        "otp_valid_minutes": int(email_cfg.otp_expiry_minutes or getattr(settings, "EMAIL_OTP_EXPIRY_MINUTES", 10)),
        "verify_url": verify_url,
        "year": timezone.now().year,
    }
    subject = "Verify your email address"
    text_body = render_to_string("emails/email_verification.txt", context)
    html_body = render_to_string("emails/email_verification.html", context)

    connection = None
    if email_cfg.smtp_host:
        connection = SmtpEmailBackend(
            host=email_cfg.smtp_host,
            port=int(email_cfg.smtp_port or 587),
            username=email_cfg.smtp_username or None,
            password=email_cfg.smtp_password or None,
            use_tls=bool(email_cfg.smtp_use_tls),
            use_ssl=bool(email_cfg.smtp_use_ssl),
            fail_silently=False,
        )
    else:
        connection = mail.get_connection(fail_silently=False)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=(email_cfg.default_from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None)),
        to=[user.email],
        connection=connection,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    token_obj.mark_sent()


def _send_withdrawal_otp(request: HttpRequest, token_obj: WithdrawalOtpToken) -> None:
    email_cfg = EmailConfiguration.get_active()
    withdrawal = token_obj.withdrawal_request
    user = withdrawal.user
    verify_url = request.build_absolute_uri(
        f"{reverse('withdrawal-otp-verify')}?token={token_obj.token}"
    )
    context = {
        "app_name": (email_cfg.app_name or getattr(settings, "EMAIL_APP_NAME", "Referral System")),
        "username": user.username,
        "otp_code": token_obj.otp_code,
        "otp_valid_minutes": int(email_cfg.otp_expiry_minutes or getattr(settings, "EMAIL_OTP_EXPIRY_MINUTES", 10)),
        "verify_url": verify_url,
        "year": timezone.now().year,
        "amount": withdrawal.amount,
        "net_amount": withdrawal.net_amount,
        "payment_method": withdrawal.payment_method,
    }
    subject = "Withdrawal OTP verification"
    text_body = render_to_string("emails/withdrawal_otp.txt", context)
    html_body = render_to_string("emails/withdrawal_otp.html", context)

    connection = None
    if email_cfg.smtp_host:
        connection = SmtpEmailBackend(
            host=email_cfg.smtp_host,
            port=int(email_cfg.smtp_port or 587),
            username=email_cfg.smtp_username or None,
            password=email_cfg.smtp_password or None,
            use_tls=bool(email_cfg.smtp_use_tls),
            use_ssl=bool(email_cfg.smtp_use_ssl),
            fail_silently=False,
        )
    else:
        connection = mail.get_connection(fail_silently=False)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=(email_cfg.default_from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None)),
        to=[user.email],
        connection=connection,
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    token_obj.mark_sent()


class DashboardPasswordChangeView(SuccessMessageMixin, auth_views.PasswordChangeView):
    template_name = "core/change_password.html"
    success_url = reverse_lazy("password_change")
    success_message = "Password updated successfully."


def _json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _decimal_or_error(raw: str):
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid decimal amount")


@csrf_exempt
def register_user(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = _json_body(request)
    username = data.get("username")
    password = data.get("password")
    email = (data.get("email") or "").strip()
    user_type = (data.get("user_type") or User.UserType.USER).strip().lower()
    referrer_code = (data.get("referrer_code") or "").strip().upper()

    if not username or not password or not referrer_code or not email:
        return JsonResponse(
            {"error": "username, password, email and referrer_code are required"},
            status=400,
        )

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "invalid email"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "username already exists"}, status=400)
    if user_type not in {User.UserType.ADMIN, User.UserType.USER}:
        return JsonResponse({"error": "invalid user_type"}, status=400)

    referred_by = User.objects.filter(referral_code=referrer_code).first()
    if not referred_by:
        return JsonResponse({"error": "invalid referrer_code"}, status=404)

    user = User.objects.create(
        username=username,
        password=make_password(password),
        email=email,
        referred_by=referred_by,
        user_type=user_type,
        is_staff=(user_type == User.UserType.ADMIN),
        is_active=False,
        email_verified=False,
    )
    token_obj = EmailVerificationToken.create_for_user(
        user=user,
        otp_valid_minutes=EmailConfiguration.get_active().otp_expiry_minutes,
    )
    try:
        _send_email_verification(request, token_obj)
    except Exception:
        return JsonResponse(
            {"error": "user created but verification email could not be sent"},
            status=500,
        )

    verify_url = request.build_absolute_uri(f"{reverse('email-verify')}?token={token_obj.token}")
    return JsonResponse(
        {
            "id": user.id,
            "username": user.username,
            "user_type": user.user_type,
            "email_verification_required": True,
            "verify_url": verify_url,
        }
    )


@csrf_exempt
def deposit_wallet(request: HttpRequest):
    return JsonResponse(
        {"error": "Direct wallet add fund is disabled. Submit manual payment request."},
        status=403,
    )


@csrf_exempt
def create_user_investment(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = _json_body(request)
    username = data.get("username")
    amount = data.get("amount")
    pay_from_wallet = bool(data.get("pay_from_wallet", False))

    user = User.objects.filter(username=username).first()
    if not user:
        return JsonResponse({"error": "user not found"}, status=404)

    try:
        amount_dec = _decimal_or_error(amount)
        investment = create_investment(user, amount_dec, from_wallet=pay_from_wallet)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "investment_id": investment.id,
            "principal_amount": str(investment.principal_amount),
            "wallet_balance": str(user.wallet.balance),
        }
    )


@csrf_exempt
def realize_investment_profit(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = _json_body(request)
    investment_id = data.get("investment_id")
    profit = data.get("profit")

    try:
        investment = Investment.objects.get(id=investment_id)
    except Investment.DoesNotExist:
        return JsonResponse({"error": "investment not found"}, status=404)

    try:
        profit_dec = _decimal_or_error(profit)
        realize_profit(investment, profit_dec)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    investment.refresh_from_db()
    return JsonResponse(
        {
            "investment_id": investment.id,
            "total_profit_realized": str(investment.profit_realized),
            "investor_wallet_balance": str(investment.user.wallet.balance),
        }
    )


def user_summary(request: HttpRequest, username: str):
    user = User.objects.filter(username=username).first()
    if not user:
        return JsonResponse({"error": "user not found"}, status=404)

    uplines = []
    current = user.referred_by
    while current and len(uplines) < 5:
        uplines.append(current.username)
        current = current.referred_by

    downline_count = user.downlines.count()
    commission_total = sum(
        (item.commission_amount for item in user.commission_earnings.all()),
        Decimal("0.00"),
    )
    return JsonResponse(
        {
            "username": user.username,
            "referred_by": user.referred_by.username if user.referred_by else None,
            "uplines_up_to_5": uplines,
            "direct_downline_count": downline_count,
            "wallet_balance": str(user.wallet.balance),
            "commission_earned_total": str(commission_total),
        }
    )


def _dashboard_context(user):
    investments = user.investments.order_by("-created_at")
    won_investments = investments.filter(profit_realized__gt=Decimal("0.00"))
    wallet_transactions = WalletTransaction.objects.filter(user=user).order_by("-created_at")[:15]

    total_invested = sum((item.principal_amount for item in investments), Decimal("0.00"))
    total_profit_won = sum((item.profit_realized for item in won_investments), Decimal("0.00"))
    commission_total = sum(
        (item.commission_amount for item in user.commission_earnings.all()),
        Decimal("0.00"),
    )
    now = timezone.localtime()
    approved_monthly_payments = (
        ManualPaymentRequest.objects.filter(
            user=user,
            status=ManualPaymentRequest.Status.APPROVED,
            created_at__year=now.year,
            created_at__month=now.month,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    approved_monthly_withdrawals = (
        ManualWithdrawalRequest.objects.filter(
            user=user,
            status=ManualWithdrawalRequest.Status.APPROVED,
            created_at__year=now.year,
            created_at__month=now.month,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    monthly_won_profit = (
        ProfitDistributionEntry.objects.filter(
            user=user,
            created_at__year=now.year,
            created_at__month=now.month,
        ).aggregate(total=Sum("won_profit"))["total"]
        or Decimal("0.00")
    )
    monthly_commission = (
        user.commission_earnings.filter(
            created_at__year=now.year,
            created_at__month=now.month,
        ).aggregate(total=Sum("commission_amount"))["total"]
        or Decimal("0.00")
    )

    return {
        "total_invested": total_invested,
        "total_profit_won": total_profit_won,
        "commission_total": commission_total,
        "monthly_add_money": approved_monthly_payments,
        "monthly_withdrawals": approved_monthly_withdrawals,
        "monthly_won_profit": monthly_won_profit,
        "monthly_commission": monthly_commission,
        "now": now,
        "investments": investments[:20],
        "won_investments": won_investments[:20],
        "wallet_transactions": wallet_transactions,
        "direct_downline_count": user.downlines.count(),
    }


@login_required
def user_dashboard(request: HttpRequest):
    user = request.user
    settle_matured_investments(user=user)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_fund":
            messages.error(
                request,
                "Direct add fund is disabled. Use Manual Payment and wait for approval.",
            )
            return redirect("dashboard")

        if action == "new_investment":
            messages.error(
                request,
                "Use the Investment page to take a package with duration.",
            )
            return redirect("user-dashboard")

    context = _dashboard_context(user)
    context["page_title"] = "User Dashboard"
    return render(request, "core/user_dashboard.html", context)


@login_required
def dashboard(request: HttpRequest):
    return redirect("user-dashboard")


@login_required
def page_profile(request: HttpRequest):
    user = request.user
    settle_matured_investments(user=user)

    if request.method == "POST":
        form_type = (request.POST.get("form_type") or "profile").strip().lower()

        if form_type == "nominee":
            nominee, _ = UserNominee.objects.get_or_create(user=user)
            nominee.name = (request.POST.get("nominee_name") or "").strip()
            nominee.address = (request.POST.get("nominee_address") or "").strip()
            nominee.phone_number = (request.POST.get("nominee_phone_number") or "").strip()

            nominee_identity_type = (request.POST.get("nominee_identity_type") or "").strip()
            valid_identity_types = {c[0] for c in User.IdentityType.choices}
            nominee.identity_type = nominee_identity_type if nominee_identity_type in valid_identity_types else ""
            nominee.identity_number = (request.POST.get("nominee_identity_number") or "").strip()

            nominee_identity_image = request.FILES.get("nominee_identity_image")
            remove_nominee_identity_image = request.POST.get("remove_nominee_identity_image") == "1"
            if remove_nominee_identity_image and nominee.identity_image:
                nominee.identity_image = None
            elif nominee_identity_image:
                nominee.identity_image = nominee_identity_image

            nominee.save()
            messages.success(request, "Nominee information updated successfully.")
            return redirect("page-profile")

        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone_number = (request.POST.get("phone_number") or "").strip()
        address = (request.POST.get("address") or "").strip()

        identity_type = (request.POST.get("identity_type") or "").strip()
        valid_identity_types = {c[0] for c in User.IdentityType.choices}
        if identity_type and identity_type not in valid_identity_types:
            identity_type = ""
        identity_number = (request.POST.get("identity_number") or "").strip()

        profile_picture = request.FILES.get("profile_picture")
        identity_image = request.FILES.get("identity_image")
        remove_profile_picture = request.POST.get("remove_profile_picture") == "1"
        remove_identity_image = request.POST.get("remove_identity_image") == "1"

        user.first_name = first_name
        user.last_name = last_name
        user.phone_number = phone_number
        user.address = address
        user.identity_type = identity_type
        user.identity_number = identity_number

        existing_email = (user.email or "").strip()
        if not email:
            email = existing_email

        if email and email.lower() != existing_email.lower():
            if User.objects.exclude(pk=user.pk).filter(email__iexact=email).exists():
                messages.error(request, "This email is already used by another account.")
                return redirect("page-profile")
            user.email = email

        update_fields = [
            "first_name",
            "last_name",
            "phone_number",
            "address",
            "identity_type",
            "identity_number",
        ]
        if user.email != existing_email:
            update_fields.append("email")
        if remove_profile_picture and user.profile_picture:
            user.profile_picture = None
            update_fields.append("profile_picture")
        elif profile_picture:
            user.profile_picture = profile_picture
            update_fields.append("profile_picture")
        if remove_identity_image and user.identity_image:
            user.identity_image = None
            update_fields.append("identity_image")
        elif identity_image:
            user.identity_image = identity_image
            update_fields.append("identity_image")

        user.save(update_fields=update_fields)
        messages.success(request, "Profile updated successfully.")
        return redirect("page-profile")

    wallet, _ = Wallet.objects.get_or_create(user=user)
    investment_wallet, _ = InvestmentWallet.objects.get_or_create(user=user)
    total_commission = user.commission_earnings.aggregate(total=Sum("commission_amount"))["total"] or Decimal("0.00")
    total_add_money = user.manual_payment_requests.count()
    total_withdrawals = user.manual_withdrawal_requests.count()
    pending_add_money = user.manual_payment_requests.filter(status=ManualPaymentRequest.Status.PENDING).count()
    pending_withdrawals = user.manual_withdrawal_requests.filter(
        status=ManualWithdrawalRequest.Status.PENDING
    ).count()

    recent_wallet_transactions = user.wallet_transactions.order_by("-created_at")[:10]
    nominee = UserNominee.objects.filter(user=user).first()

    context = {
        "page_title": "My Profile",
        "wallet_balance": wallet.balance,
        "investment_wallet_balance": investment_wallet.balance,
        "active_investments_count": user.investments.filter(status=Investment.Status.ACTIVE).count(),
        "total_investments_count": user.investments.count(),
        "total_referrals": user.downlines.count(),
        "total_commission": total_commission,
        "total_add_money": total_add_money,
        "total_withdrawals": total_withdrawals,
        "pending_add_money": pending_add_money,
        "pending_withdrawals": pending_withdrawals,
        "recent_wallet_transactions": recent_wallet_transactions,
        "full_name": user.get_full_name() or user.username,
        "identity_type_choices": User.IdentityType.choices,
        "nominee": nominee,
    }
    return render(request, "core/page_profile.html", context)


def custom_page_not_found(request: HttpRequest, exception=None):
    return render(request, "404.html", status=404)


def custom_404_preview(request: HttpRequest):
    return render(request, "404.html", status=404)


def referral_code_entry(request: HttpRequest):
    if request.user.is_authenticated:
        return redirect("dashboard")

    query_code = (request.GET.get("code") or "").strip().upper()
    if query_code:
        referrer_from_link = User.objects.filter(referral_code=query_code).first()
        if referrer_from_link:
            request.session["signup_referrer_id"] = referrer_from_link.id
            return redirect("register-with-referral")

    if request.method == "POST":
        code = (request.POST.get("referral_code") or "").strip().upper()
        referrer = User.objects.filter(referral_code=code).first()
        if not referrer:
            messages.error(request, "Invalid referral code.")
            return redirect("referral-entry")
        request.session["signup_referrer_id"] = referrer.id
        return redirect("register-with-referral")
    return render(request, "registration/referral_code_entry.html", {"prefill_code": query_code})


def register_with_referral(request: HttpRequest):
    if request.user.is_authenticated:
        return redirect("dashboard")

    referrer_id = request.session.get("signup_referrer_id")
    if not referrer_id:
        messages.error(request, "Please submit a referral code first.")
        return redirect("referral-entry")

    referrer = User.objects.filter(id=referrer_id).first()
    if not referrer:
        request.session.pop("signup_referrer_id", None)
        messages.error(request, "Referral source not found. Try again.")
        return redirect("referral-entry")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        user_type = User.UserType.USER
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("register-with-referral")
        if not email:
            messages.error(request, "Email is required.")
            return redirect("register-with-referral")
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            return redirect("register-with-referral")
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("register-with-referral")
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register-with-referral")
        if len(password) < 4:
            messages.error(request, "Password must be at least 4 characters.")
            return redirect("register-with-referral")
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            referred_by=referrer,
            user_type=user_type,
            is_staff=False,
            is_active=False,
            email_verified=False,
        )
        request.session.pop("signup_referrer_id", None)
        token_obj = EmailVerificationToken.create_for_user(
            user=user,
            otp_valid_minutes=EmailConfiguration.get_active().otp_expiry_minutes,
        )
        try:
            _send_email_verification(request, token_obj)
        except Exception:
            messages.error(request, "Account created, but we couldn't send verification email. Contact support.")
            return redirect("login")
        messages.success(request, "Registration successful. Please verify your email to activate your account.")
        return redirect(f"{reverse('email-verify')}?token={token_obj.token}")

    return render(
        request,
        "registration/register_with_referral.html",
        {"referrer": referrer},
    )


def verify_email(request: HttpRequest):
    token_raw = (request.GET.get("token") or request.POST.get("token") or "").strip()
    try:
        token_obj = EmailVerificationToken.objects.select_related("user").get(token=token_raw)
    except EmailVerificationToken.DoesNotExist:
        messages.error(request, "Invalid verification link.")
        return redirect("login")

    user = token_obj.user
    if token_obj.is_used:
        if user.is_active and user.email_verified:
            login(request, user)
            messages.success(request, "Your email is already verified.")
            return redirect("user-dashboard")
        messages.success(request, "Your email is already verified. You can sign in now.")
        return redirect("login")
    if token_obj.is_expired:
        messages.error(request, "Your OTP has expired. Please resend OTP.")
        return render(
            request,
            "registration/verify_email.html",
            {"token": str(token_obj.token), "masked_email": _mask_email(user.email)},
        )

    if request.method == "POST":
        otp = (request.POST.get("otp_code") or "").strip()
        if not otp:
            messages.error(request, "OTP is required.")
        elif otp != token_obj.otp_code:
            messages.error(request, "Invalid OTP.")
        else:
            user.email_verified = True
            user.is_active = True
            user.save(update_fields=["email_verified", "is_active"])
            token_obj.used_at = timezone.now()
            token_obj.save(update_fields=["used_at"])
            login(request, user)
            messages.success(request, "Email verified successfully.")
            return redirect("user-dashboard")

    return render(
        request,
        "registration/verify_email.html",
        {"token": str(token_obj.token), "masked_email": _mask_email(user.email)},
    )


def resend_email_verification(request: HttpRequest):
    if request.method != "POST":
        return redirect("login")

    token_raw = (request.POST.get("token") or "").strip()
    try:
        token_obj = EmailVerificationToken.objects.select_related("user").get(token=token_raw)
    except EmailVerificationToken.DoesNotExist:
        messages.error(request, "Invalid verification request.")
        return redirect("login")

    if token_obj.is_used:
        messages.success(request, "Your email is already verified. You can sign in now.")
        return redirect("login")

    cooldown = int(
        EmailConfiguration.get_active().resend_cooldown_seconds
        or getattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)
    )
    if token_obj.last_sent_at and (timezone.now() - token_obj.last_sent_at).total_seconds() < cooldown:
        messages.error(request, "Please wait a moment before requesting another OTP.")
        return redirect(f"{reverse('email-verify')}?token={token_obj.token}")

    new_token = EmailVerificationToken.create_for_user(
        user=token_obj.user,
        otp_valid_minutes=EmailConfiguration.get_active().otp_expiry_minutes,
    )
    try:
        _send_email_verification(request, new_token)
    except Exception:
        messages.error(request, "Could not send OTP. Please try again later.")
        return redirect(f"{reverse('email-verify')}?token={token_obj.token}")

    messages.success(request, "A new OTP has been sent to your email.")
    return redirect(f"{reverse('email-verify')}?token={new_token.token}")


@login_required
def verify_withdrawal_otp(request: HttpRequest):
    token_raw = (request.GET.get("token") or request.POST.get("token") or "").strip()
    try:
        token_obj = (
            WithdrawalOtpToken.objects.select_related("withdrawal_request", "withdrawal_request__user")
            .get(token=token_raw)
        )
    except WithdrawalOtpToken.DoesNotExist:
        messages.error(request, "Invalid withdrawal verification link.")
        return redirect("manual-withdrawal")

    withdrawal = token_obj.withdrawal_request
    if withdrawal.user_id != request.user.id:
        messages.error(request, "This verification link is not for your account.")
        return redirect("manual-withdrawal")

    if withdrawal.email_otp_verified:
        messages.success(request, "Your withdrawal request is already verified.")
        return redirect(f"{reverse('manual-withdrawal')}?submitted=1")

    if token_obj.is_used:
        messages.error(request, "This OTP token has already been used. Please resend OTP.")
    if token_obj.is_expired:
        messages.error(request, "Your OTP has expired. Please resend OTP.")

    if request.method == "POST":
        otp = (request.POST.get("otp_code") or "").strip()
        if token_obj.is_expired:
            messages.error(request, "Your OTP has expired. Please resend OTP.")
        elif not otp:
            messages.error(request, "OTP is required.")
        elif otp != token_obj.otp_code:
            messages.error(request, "Invalid OTP.")
        else:
            withdrawal.email_otp_verified = True
            withdrawal.email_otp_verified_at = timezone.now()
            withdrawal.save(update_fields=["email_otp_verified", "email_otp_verified_at"])
            token_obj.used_at = timezone.now()
            token_obj.save(update_fields=["used_at"])
            try:
                from . import notifications

                transaction.on_commit(
                    lambda: notifications.send_withdrawal_confirmed(request.user, withdrawal)
                )
            except Exception:
                pass
            messages.success(request, "Withdrawal request verified successfully.")
            return redirect(f"{reverse('manual-withdrawal')}?submitted=1")

    return render(
        request,
        "core/verify_withdrawal_otp.html",
        {
            "token": str(token_obj.token),
            "masked_email": _mask_email(request.user.email),
            "withdrawal": withdrawal,
        },
    )


@login_required
def resend_withdrawal_otp(request: HttpRequest):
    if request.method != "POST":
        return redirect("manual-withdrawal")

    token_raw = (request.POST.get("token") or "").strip()
    try:
        token_obj = (
            WithdrawalOtpToken.objects.select_related("withdrawal_request", "withdrawal_request__user")
            .get(token=token_raw)
        )
    except WithdrawalOtpToken.DoesNotExist:
        messages.error(request, "Invalid withdrawal verification request.")
        return redirect("manual-withdrawal")

    withdrawal = token_obj.withdrawal_request
    if withdrawal.user_id != request.user.id:
        messages.error(request, "This verification request is not for your account.")
        return redirect("manual-withdrawal")

    if withdrawal.email_otp_verified:
        messages.success(request, "Your withdrawal request is already verified.")
        return redirect(f"{reverse('manual-withdrawal')}?submitted=1")

    cooldown = int(
        EmailConfiguration.get_active().resend_cooldown_seconds
        or getattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)
    )
    if token_obj.last_sent_at and (timezone.now() - token_obj.last_sent_at).total_seconds() < cooldown:
        messages.error(request, "Please wait a moment before requesting another OTP.")
        return redirect(f"{reverse('withdrawal-otp-verify')}?token={token_obj.token}")

    new_token = WithdrawalOtpToken.create_for_request(
        withdrawal_request=withdrawal,
        otp_valid_minutes=EmailConfiguration.get_active().otp_expiry_minutes,
    )
    try:
        _send_withdrawal_otp(request, new_token)
    except Exception:
        messages.error(request, "Could not send OTP. Please try again later.")
        return redirect(f"{reverse('withdrawal-otp-verify')}?token={token_obj.token}")

    messages.success(request, "A new OTP has been sent to your email.")
    return redirect(f"{reverse('withdrawal-otp-verify')}?token={new_token.token}")


def logout_user(request: HttpRequest):
    request.session.pop("is_locked", None)
    request.session.pop("lock_next", None)
    logout(request)
    return render(request, "registration/logout.html")


@login_required
def set_lock_screen(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        request.session["lock_next"] = next_url
    request.session["is_locked"] = True
    return JsonResponse({"ok": True})


@login_required
def lock_screen(request: HttpRequest):
    request.session["is_locked"] = True
    referer_path = ""
    referer = request.META.get("HTTP_REFERER") or ""
    if referer:
        try:
            referer_path = referer.split(request.build_absolute_uri("/").rstrip("/"), 1)[-1]
            if not referer_path.startswith("/"):
                referer_path = ""
        except Exception:
            referer_path = ""

    raw_next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.session.get("lock_next")
        or referer_path
        or reverse("dashboard")
    )
    if url_has_allowed_host_and_scheme(
        url=raw_next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = raw_next_url
    else:
        next_url = reverse("dashboard")

    if request.method == "POST":
        password = request.POST.get("password") or ""
        if request.user.check_password(password):
            request.session["is_locked"] = False
            request.session.pop("lock_next", None)
            messages.success(request, "Screen unlocked.")
            return redirect(next_url)
        messages.error(request, "Invalid password. Try again.")

    return render(
        request,
        "core/lockscreen.html",
        {
            "next_url": next_url,
        },
    )


@login_required
def referral_info(request: HttpRequest):
    direct_link = request.build_absolute_uri(f"/register/?code={request.user.referral_code}")
    level_users = []
    parent_ids = [request.user.id]

    for level in range(1, MAX_REFERRAL_LEVEL + 1):
        raw_users = list(
            User.objects.filter(referred_by_id__in=parent_ids)
            .order_by("date_joined")
            .only("id", "username", "date_joined")
            .prefetch_related("investments", "commission_earnings")
        )
        users = []
        for item in raw_users:
            invest_current_amount = sum(
                (inv.principal_amount for inv in item.investments.all()),
                Decimal("0.00"),
            )
            commission_amount = sum(
                (cm.commission_amount for cm in item.commission_earnings.all()),
                Decimal("0.00"),
            )
            users.append(
                {
                    "id": item.id,
                    "username": item.username,
                    "date_joined": item.date_joined,
                    "invest_current_amount": invest_current_amount,
                    "commission_amount": commission_amount,
                }
            )

        level_users.append({"level": level, "users": users})
        parent_ids = [item["id"] for item in users]
        if not parent_ids:
            for next_level in range(level + 1, MAX_REFERRAL_LEVEL + 1):
                level_users.append({"level": next_level, "users": []})
            break

    return render(
        request,
        "core/referral_info.html",
        {"direct_link": direct_link, "level_users": level_users},
    )


@login_required
def users_referral(request: HttpRequest):
    def build_tree(node, depth=1):
        children = (
            node.downlines.all()
            .order_by("date_joined")
            .only("id", "username", "referral_code", "date_joined")
        )
        if depth >= MAX_REFERRAL_LEVEL:
            child_nodes = []
        else:
            child_nodes = [build_tree(child, depth + 1) for child in children]
        return {
            "id": node.id,
            "username": node.username,
            "referral_code": node.referral_code,
            "joined": node.date_joined,
            "children": child_nodes,
        }

    tree = build_tree(request.user)
    level_rows = []
    parent_ids = [request.user.id]
    serial = 1
    now = timezone.now()

    for level in range(1, MAX_REFERRAL_LEVEL + 1):
        users = list(
            User.objects.filter(referred_by_id__in=parent_ids)
            .select_related("referred_by")
            .order_by("date_joined")
            .only("id", "username", "referral_code", "date_joined", "referred_by__username")
        )
        if not users:
            break

        user_ids = [user.id for user in users]
        active_invest_map = {
            row["user_id"]: row
            for row in (
                Investment.objects.filter(user_id__in=user_ids, status=Investment.Status.ACTIVE)
                .values("user_id")
                .annotate(
                    total_amount=Sum("principal_amount"),
                    total_count=Count("id"),
                )
            )
        }
        monthly_commission_map = {
            row["beneficiary_id"]: row["total_amount"]
            for row in (
                CommissionLog.objects.filter(
                    beneficiary_id__in=user_ids,
                    created_at__year=now.year,
                    created_at__month=now.month,
                )
                .values("beneficiary_id")
                .annotate(total_amount=Sum("commission_amount"))
            )
        }

        for user in users:
            active_invest = active_invest_map.get(user.id, {})
            level_rows.append(
                {
                    "serial": serial,
                    "level": level,
                    "username": user.username,
                    "referral_code": user.referral_code,
                    "referred_by": user.referred_by.username if user.referred_by else "-",
                    "joined": user.date_joined,
                    "active_invest_count": active_invest.get("total_count", 0),
                    "active_invest_amount": active_invest.get("total_amount", Decimal("0.00")),
                    "running_month_commission": monthly_commission_map.get(user.id, Decimal("0.00")),
                }
            )
            serial += 1

        parent_ids = [user.id for user in users]

    return render(
        request,
        "core/users_referral.html",
        {
            "page_title": "Users Referral",
            "tree": tree,
            "level_rows": level_rows,
        },
    )


@login_required
def add_money_page(request: HttpRequest):
    settle_matured_investments(user=request.user)
    payment_methods = PaymentMethod.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        amount_raw = request.POST.get("amount")
        payment_method_id = request.POST.get("payment_method_id")
        transaction_reference = (request.POST.get("transaction_reference") or "").strip()
        details = (request.POST.get("details") or "").strip()
        proof_image = request.FILES.get("proof_image")

        try:
            amount = _decimal_or_error(amount_raw)
            if amount <= 0:
                raise ValueError("Amount must be greater than zero.")
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("add-money")

        selected_method = payment_methods.filter(id=payment_method_id).first()
        if not selected_method:
            messages.error(request, "Please select a valid payment method.")
            return redirect("add-money")
        if not details:
            messages.error(request, "Payment details are required.")
            return redirect("add-money")

        payment_req = ManualPaymentRequest.objects.create(
            user=request.user,
            amount=amount,
            payment_method=selected_method.name,
            transaction_reference=transaction_reference,
            details=details,
            proof_image=proof_image,
        )
        try:
            from . import notifications

            transaction.on_commit(
                lambda: notifications.send_add_money_submitted(request.user, payment_req)
            )
        except Exception:
            pass
        messages.success(request, "Payment request submitted successfully.")
        return redirect(f"{reverse('add-money')}?submitted=1")

    payment_requests = ManualPaymentRequest.objects.filter(user=request.user).order_by("-created_at")

    return render(
        request,
        "core/add_money.html",
        {
            "page_title": "Add Money",
            "payment_methods": payment_methods,
            "payment_submitted": request.GET.get("submitted") == "1",
            "payment_requests": payment_requests,
        },
    )


@login_required
def manual_payment(request: HttpRequest):
    settle_matured_investments(user=request.user)
    payment_methods = PaymentMethod.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        amount_raw = request.POST.get("amount")
        payment_method_id = request.POST.get("payment_method_id")
        transaction_reference = (request.POST.get("transaction_reference") or "").strip()
        details = (request.POST.get("details") or "").strip()
        proof_image = request.FILES.get("proof_image")

        try:
            amount = _decimal_or_error(amount_raw)
            if amount <= 0:
                raise ValueError("Amount must be greater than zero.")
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("manual-payment")

        selected_method = payment_methods.filter(id=payment_method_id).first()
        if not selected_method:
            messages.error(request, "Please select a valid payment method.")
            return redirect("manual-payment")
        if not details:
            messages.error(request, "Payment details are required.")
            return redirect("manual-payment")

        payment_req = ManualPaymentRequest.objects.create(
            user=request.user,
            amount=amount,
            payment_method=selected_method.name,
            transaction_reference=transaction_reference,
            details=details,
            proof_image=proof_image,
        )
        try:
            from . import notifications

            transaction.on_commit(
                lambda: notifications.send_add_money_submitted(request.user, payment_req)
            )
        except Exception:
            pass
        messages.success(request, "Payment request submitted successfully.")
        return redirect("manual-payment")

    payment_requests = ManualPaymentRequest.objects.filter(user=request.user).order_by("-created_at")
    return render(
        request,
        "core/manual_payment.html",
        {
            "payment_requests": payment_requests,
            "payment_methods": payment_methods,
        },
    )


@login_required
def manual_withdrawal(request: HttpRequest):
    settle_matured_investments(user=request.user)
    withdrawal_methods = WithdrawalMethod.objects.filter(is_active=True).order_by("name")
    system_cfg = SystemConfiguration.get_solo()
    min_withdrawal_amount = system_cfg.min_withdrawal_amount

    if request.method == "POST":
        if not request.user.email:
            messages.error(request, "Please add an email to your account before making a withdrawal request.")
            return redirect("manual-withdrawal")
        if not request.user.email_verified:
            token_obj = EmailVerificationToken.create_for_user(
                user=request.user,
                otp_valid_minutes=EmailConfiguration.get_active().otp_expiry_minutes,
            )
            try:
                _send_email_verification(request, token_obj)
            except Exception:
                messages.error(
                    request,
                    "Your email is not verified, and we could not send a verification OTP. Please contact support.",
                )
                return redirect("manual-withdrawal")
            messages.error(request, "Please verify your email first. We sent you a new OTP.")
            return redirect(f"{reverse('email-verify')}?token={token_obj.token}")

        amount_raw = request.POST.get("amount")
        withdrawal_method_id = request.POST.get("withdrawal_method_id")
        account_details = (request.POST.get("account_details") or "").strip()

        try:
            amount = _decimal_or_error(amount_raw)
            if amount <= 0:
                raise ValueError("Amount must be greater than zero.")
            if amount < min_withdrawal_amount:
                raise ValueError(f"Minimum withdrawal amount is USDT {min_withdrawal_amount}")
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("manual-withdrawal")

        selected_method = withdrawal_methods.filter(id=withdrawal_method_id).first()
        if not selected_method:
            messages.error(request, "Please select a valid payment method.")
            return redirect("manual-withdrawal")
        if not account_details:
            messages.error(request, "Account details are required.")
            return redirect("manual-withdrawal")
        if request.user.wallet.balance < amount:
            messages.error(request, "Insufficient wallet balance.")
            return redirect("manual-withdrawal")

        fee_percent = selected_method.withdrawal_fee_percent
        fee_fixed = selected_method.withdrawal_fee_fixed
        if fee_percent > 0:
            fee_amount = (amount * fee_percent / Decimal("100")).quantize(Decimal("0.01"))
        else:
            fee_amount = fee_fixed.quantize(Decimal("0.01"))
        net_amount = (amount - fee_amount).quantize(Decimal("0.01"))
        if net_amount < 0:
            net_amount = Decimal("0.00")

        withdrawal = ManualWithdrawalRequest.objects.create(
            user=request.user,
            amount=amount,
            withdrawal_method=selected_method,
            payment_method=selected_method.name,
            withdrawal_fee_percent=fee_percent,
            withdrawal_fee_fixed=fee_fixed,
            withdrawal_fee_amount=fee_amount,
            net_amount=net_amount,
            account_details=account_details,
        )
        token_obj = WithdrawalOtpToken.create_for_request(
            withdrawal_request=withdrawal,
            otp_valid_minutes=EmailConfiguration.get_active().otp_expiry_minutes,
        )
        try:
            _send_withdrawal_otp(request, token_obj)
        except Exception:
            messages.error(request, "Withdrawal request created, but we couldn't send OTP. Please try resend.")
            return redirect(f"{reverse('withdrawal-otp-verify')}?token={token_obj.token}")

        messages.success(request, "OTP sent. Please verify to confirm your withdrawal request.")
        return redirect(f"{reverse('withdrawal-otp-verify')}?token={token_obj.token}")

    withdrawal_requests = ManualWithdrawalRequest.objects.filter(user=request.user).order_by("-created_at")

    return render(
        request,
        "core/withdrawal.html",
        {
            "page_title": "Withdraw Money",
            "withdrawal_requests": withdrawal_requests,
            "withdrawal_methods": withdrawal_methods,
            "withdrawal_submitted": request.GET.get("submitted") == "1",
            "min_withdrawal_amount": min_withdrawal_amount,
        },
    )


@login_required
def payment_withdrawal_transaction(request: HttpRequest):
    settle_matured_investments(user=request.user)

    payment_requests = list(
        ManualPaymentRequest.objects.filter(user=request.user).order_by("created_at", "id")
    )
    withdrawal_requests = list(
        ManualWithdrawalRequest.objects.filter(user=request.user).order_by("created_at", "id")
    )

    transactions = []

    for item in payment_requests:
        transactions.append(
            {
                "created_at": item.created_at,
                "type": "add_money",
                "request_id": item.id,
                "request_code": item.request_code,
                "amount": item.amount,
                "method": item.payment_method,
                "reference": item.transaction_reference,
                "status": item.status,
                "fee": Decimal("0.00"),
                "net": item.amount,
                "note": item.details,
            }
        )

    for item in withdrawal_requests:
        transactions.append(
            {
                "created_at": item.created_at,
                "type": "withdrawal",
                "request_id": item.id,
                "request_code": item.request_code,
                "amount": item.amount,
                "method": item.payment_method,
                "reference": item.account_details,
                "status": item.status,
                "fee": item.withdrawal_fee_amount,
                "net": item.net_amount,
                "note": item.admin_note,
            }
        )

    transactions.sort(key=lambda row: row["created_at"], reverse=True)
    for index, row in enumerate(transactions, start=1):
        row["serial"] = index

    return render(
        request,
        "core/payment_withdrawal_transaction.html",
        {
            "page_title": "Payment & Withdrawal Transactions",
            "transactions": transactions,
        },
    )


def _build_investment_page_context(user):
    investment_wallet, _ = InvestmentWallet.objects.get_or_create(user=user)
    system_cfg = SystemConfiguration.get_solo()
    packages = InvestmentPackage.objects.filter(is_active=True).order_by("name")
    active_investments_qs = user.investments.select_related("package").filter(
        status=Investment.Status.ACTIVE
    ).order_by("-created_at")
    completed_investments_qs = user.investments.select_related("package").filter(
        status=Investment.Status.COMPLETED
    ).order_by("-created_at")
    active_investments = list(active_investments_qs)
    completed_investments = list(completed_investments_qs)

    return_average = completed_investments_qs.aggregate(avg=Avg("principal_amount"))["avg"] or Decimal("0.00")
    return {
        "packages": packages,
        "active_investments": active_investments,
        "completed_investments": completed_investments,
        "investment_wallet_balance": investment_wallet.balance,
        "return_average": return_average,
        "min_investment_amount": system_cfg.min_investment_amount,
    }


def _handle_investment_package_purchase(request: HttpRequest, redirect_name: str):
    if request.method != "POST":
        return None

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    package_id = request.POST.get("package_id")
    amount_raw = request.POST.get("amount")
    package = InvestmentPackage.objects.filter(id=package_id, is_active=True).first()
    if not package:
        message = "Invalid investment package selected."
        if is_ajax:
            return JsonResponse({"ok": False, "error": message}, status=400)
        messages.error(request, message)
        return redirect(redirect_name)

    try:
        amount = _decimal_or_error(amount_raw)
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        investment = create_package_investment(request.user, package, amount)
        try:
            from . import notifications

            transaction.on_commit(
                lambda: notifications.send_investment_confirmed(request.user, investment)
            )
        except Exception:
            pass
        success_message = (
            f"Investment {investment.investment_code} started for USDT {amount} "
            f"and {package.duration_days} days."
        )
        if is_ajax:
            return JsonResponse(
                {
                    "ok": True,
                    "message": success_message,
                    "redirect": reverse("investment-page"),
                }
            )
        messages.success(request, success_message)
        return redirect("investment-page")
    except ValueError as exc:
        if is_ajax:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, str(exc))
    return redirect(redirect_name)


@login_required
def investment_page(request: HttpRequest):
    settle_matured_investments(user=request.user)
    post_response = _handle_investment_package_purchase(request, "investment-page")
    if post_response:
        return post_response

    return render(
        request,
        "core/investment.html",
        _build_investment_page_context(request.user),
    )


@login_required
def investment_packages_page(request: HttpRequest):
    settle_matured_investments(user=request.user)
    post_response = _handle_investment_package_purchase(request, "investment-packages")
    if post_response:
        return post_response

    return render(
        request,
        "core/package.html",
        _build_investment_page_context(request.user),
    )


@login_required
def admin_profit_distribution(request: HttpRequest):
    if not request.user.is_staff:
        return redirect("user-dashboard")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "distribute_profit":
            amount_raw = request.POST.get("total_amount")
            note = (request.POST.get("note") or "").strip()
            try:
                amount = _decimal_or_error(amount_raw)
                if amount <= 0:
                    raise ValueError("Amount must be greater than zero.")
                distribution = distribute_profit_to_active_investors(
                    total_amount=amount,
                    created_by=request.user,
                    note=note,
                )
                if distribution.distributed_amount > 0:
                    messages.success(
                        request,
                        f"Distribution #{distribution.pk} completed. "
                        f"Gross {distribution.distributed_amount}, "
                        f"referral {distribution.total_referral_commission}, "
                        f"unsettled {distribution.total_unsettled_commission}, "
                        f"won profit {distribution.total_won_profit}.",
                    )
                else:
                    messages.warning(
                        request,
                        f"Distribution #{distribution.pk} saved, but no active running package found.",
                    )
            except ValueError as exc:
                messages.error(request, str(exc))

        elif action in {"approve_payment", "reject_payment"}:
            request_id = request.POST.get("payment_request_id")
            admin_note = (request.POST.get("admin_note") or "").strip()
            try:
                with transaction.atomic():
                    payment_req = (
                        ManualPaymentRequest.objects.select_for_update()
                        .select_related("user")
                        .get(pk=request_id)
                    )
                    if payment_req.status != ManualPaymentRequest.Status.PENDING:
                        messages.error(request, "This add money request is not pending.")
                    else:
                        payment_req.admin_note = admin_note
                        if action == "approve_payment":
                            payment_req.status = ManualPaymentRequest.Status.APPROVED
                            payment_req.save(update_fields=["status", "admin_note", "updated_at"])
                            messages.success(
                                request,
                                f"Add money request #{payment_req.pk} approved.",
                            )
                        else:
                            payment_req.status = ManualPaymentRequest.Status.REJECTED
                            payment_req.save(update_fields=["status", "admin_note", "updated_at"])
                            messages.success(
                                request,
                                f"Add money request #{payment_req.pk} rejected.",
                            )
            except ManualPaymentRequest.DoesNotExist:
                messages.error(request, "Add money request not found.")

        elif action in {"approve_withdrawal", "reject_withdrawal"}:
            request_id = request.POST.get("withdrawal_request_id")
            admin_note = (request.POST.get("admin_note") or "").strip()
            try:
                with transaction.atomic():
                    withdrawal_req = (
                        ManualWithdrawalRequest.objects.select_for_update()
                        .select_related("user")
                        .get(pk=request_id)
                    )
                    if withdrawal_req.status != ManualWithdrawalRequest.Status.PENDING:
                        messages.error(request, "This withdrawal request is not pending.")
                    elif action == "reject_withdrawal":
                        if withdrawal_req.wallet_debited:
                            messages.error(
                                request,
                                "This withdrawal was already debited. Reject is not allowed.",
                            )
                        else:
                            withdrawal_req.status = ManualWithdrawalRequest.Status.REJECTED
                            withdrawal_req.admin_note = admin_note
                            withdrawal_req.save(update_fields=["status", "admin_note", "updated_at"])
                            messages.success(
                                request,
                                f"Withdrawal request #{withdrawal_req.pk} rejected.",
                            )
                    else:
                        if withdrawal_req.wallet_debited:
                            messages.error(
                                request,
                                "This withdrawal request was already approved.",
                            )
                        elif not withdrawal_req.email_otp_verified:
                            messages.error(
                                request,
                                "Cannot approve: withdrawal is not OTP-verified by email.",
                            )
                        else:
                            wallet, _ = Wallet.objects.select_for_update().get_or_create(
                                user=withdrawal_req.user
                            )
                            if wallet.balance < withdrawal_req.amount:
                                messages.error(
                                    request,
                                    f"Insufficient wallet balance for {withdrawal_req.user.username}.",
                                )
                            else:
                                wallet.balance = wallet.balance - withdrawal_req.amount
                                wallet.save(update_fields=["balance", "updated_at"])
                                WalletTransaction.objects.create(
                                    user=withdrawal_req.user,
                                    tx_type=WalletTransaction.TxType.DEBIT,
                                    amount=withdrawal_req.amount,
                                    description=(
                                        f"Manual withdrawal approved (Request #{withdrawal_req.pk}, "
                                        f"fee {withdrawal_req.withdrawal_fee_amount}, "
                                        f"net {withdrawal_req.net_amount})"
                                    ),
                                )
                                withdrawal_req.status = ManualWithdrawalRequest.Status.APPROVED
                                withdrawal_req.wallet_debited = True
                                withdrawal_req.debited_at = timezone.now()
                                withdrawal_req.admin_note = admin_note
                                withdrawal_req.save(
                                    update_fields=[
                                        "status",
                                        "wallet_debited",
                                        "debited_at",
                                        "admin_note",
                                        "updated_at",
                                    ]
                                )
                                try:
                                    from . import notifications

                                    transaction.on_commit(
                                        lambda: notifications.send_withdrawal_approved(
                                            withdrawal_req.user, withdrawal_req
                                        )
                                    )
                                except Exception:
                                    pass
                                messages.success(
                                    request,
                                    f"Withdrawal request #{withdrawal_req.pk} approved.",
                                )
            except ManualWithdrawalRequest.DoesNotExist:
                messages.error(request, "Withdrawal request not found.")

    current_total_invested = Investment.objects.aggregate(total=Sum("principal_amount"))["total"] or Decimal("0.00")

    return render(
        request,
        "core/admin_profit_distribution.html",
        {
            "page_title": "Admin Profit Distribution",
            "current_total_invested": current_total_invested,
        },
    )


@login_required
def admin_pending_add_money(request: HttpRequest):
    if not request.user.is_staff:
        return redirect("user-dashboard")

    if request.method == "POST":
        action = request.POST.get("action")
        if action in {"approve_payment", "reject_payment"}:
            request_id = request.POST.get("payment_request_id")
            admin_note = (request.POST.get("admin_note") or "").strip()
            try:
                with transaction.atomic():
                    payment_req = (
                        ManualPaymentRequest.objects.select_for_update()
                        .select_related("user")
                        .get(pk=request_id)
                    )
                    if payment_req.status != ManualPaymentRequest.Status.PENDING:
                        messages.error(request, "This add money request is not pending.")
                    else:
                        payment_req.admin_note = admin_note
                        if action == "approve_payment":
                            payment_req.status = ManualPaymentRequest.Status.APPROVED
                            payment_req.save(update_fields=["status", "admin_note", "updated_at"])
                            messages.success(
                                request,
                                f"Add money request #{payment_req.pk} approved.",
                            )
                        else:
                            payment_req.status = ManualPaymentRequest.Status.REJECTED
                            payment_req.save(update_fields=["status", "admin_note", "updated_at"])
                            messages.success(
                                request,
                                f"Add money request #{payment_req.pk} rejected.",
                            )
            except ManualPaymentRequest.DoesNotExist:
                messages.error(request, "Add money request not found.")

    pending_add_money = ManualPaymentRequest.objects.filter(
        status=ManualPaymentRequest.Status.PENDING
    ).select_related("user").order_by("created_at", "id")

    return render(
        request,
        "core/admin_pending_add_money.html",
        {
            "page_title": "Pending Add Money Requests",
            "pending_add_money": pending_add_money,
        },
    )


@login_required
def admin_pending_withdrawals(request: HttpRequest):
    if not request.user.is_staff:
        return redirect("user-dashboard")

    if request.method == "POST":
        action = request.POST.get("action")
        if action in {"approve_withdrawal", "reject_withdrawal"}:
            request_id = request.POST.get("withdrawal_request_id")
            admin_note = (request.POST.get("admin_note") or "").strip()
            try:
                with transaction.atomic():
                    withdrawal_req = (
                        ManualWithdrawalRequest.objects.select_for_update()
                        .select_related("user")
                        .get(pk=request_id)
                    )
                    if withdrawal_req.status != ManualWithdrawalRequest.Status.PENDING:
                        messages.error(request, "This withdrawal request is not pending.")
                    elif action == "reject_withdrawal":
                        if withdrawal_req.wallet_debited:
                            messages.error(
                                request,
                                "This withdrawal was already debited. Reject is not allowed.",
                            )
                        else:
                            withdrawal_req.status = ManualWithdrawalRequest.Status.REJECTED
                            withdrawal_req.admin_note = admin_note
                            withdrawal_req.save(update_fields=["status", "admin_note", "updated_at"])
                            messages.success(
                                request,
                                f"Withdrawal request #{withdrawal_req.pk} rejected.",
                            )
                    else:
                        if withdrawal_req.wallet_debited:
                            messages.error(
                                request,
                                "This withdrawal request was already approved.",
                            )
                        elif not withdrawal_req.email_otp_verified:
                            messages.error(
                                request,
                                "Cannot approve: withdrawal is not OTP-verified by email.",
                            )
                        else:
                            wallet, _ = Wallet.objects.select_for_update().get_or_create(
                                user=withdrawal_req.user
                            )
                            if wallet.balance < withdrawal_req.amount:
                                messages.error(
                                    request,
                                    f"Insufficient wallet balance for {withdrawal_req.user.username}.",
                                )
                            else:
                                wallet.balance = wallet.balance - withdrawal_req.amount
                                wallet.save(update_fields=["balance", "updated_at"])
                                WalletTransaction.objects.create(
                                    user=withdrawal_req.user,
                                    tx_type=WalletTransaction.TxType.DEBIT,
                                    amount=withdrawal_req.amount,
                                    description=(
                                        f"Manual withdrawal approved (Request #{withdrawal_req.pk}, "
                                        f"fee {withdrawal_req.withdrawal_fee_amount}, "
                                        f"net {withdrawal_req.net_amount})"
                                    ),
                                )
                                withdrawal_req.status = ManualWithdrawalRequest.Status.APPROVED
                                withdrawal_req.wallet_debited = True
                                withdrawal_req.debited_at = timezone.now()
                                withdrawal_req.admin_note = admin_note
                                withdrawal_req.save(
                                    update_fields=[
                                        "status",
                                        "wallet_debited",
                                        "debited_at",
                                        "admin_note",
                                        "updated_at",
                                    ]
                                )
                                try:
                                    from . import notifications

                                    transaction.on_commit(
                                        lambda: notifications.send_withdrawal_approved(
                                            withdrawal_req.user, withdrawal_req
                                        )
                                    )
                                except Exception:
                                    pass
                                messages.success(
                                    request,
                                    f"Withdrawal request #{withdrawal_req.pk} approved.",
                                )
            except ManualWithdrawalRequest.DoesNotExist:
                messages.error(request, "Withdrawal request not found.")

    pending_withdrawals = ManualWithdrawalRequest.objects.filter(
        status=ManualWithdrawalRequest.Status.PENDING
    ).select_related("user").order_by("created_at", "id")

    return render(
        request,
        "core/admin_pending_withdrawals.html",
        {
            "page_title": "Pending Withdrawal Requests",
            "pending_withdrawals": pending_withdrawals,
        },
    )


@login_required
def investment_reports(request: HttpRequest):
    if request.user.is_staff:
        return redirect("admin-investment-reports")

    investments = Investment.objects.select_related("package").filter(user=request.user)
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    if date_from:
        investments = investments.filter(created_at__date__gte=date_from)
    if date_to:
        investments = investments.filter(created_at__date__lte=date_to)
    investments = investments.order_by("-created_at")
    return render(
        request,
        "core/investment_reports.html",
        {
            "page_title": "Investment Reports",
            "investments": investments,
            "is_admin_view": False,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
def admin_investment_reports(request: HttpRequest):
    if not request.user.is_staff:
        return redirect("investment-reports")

    investments = Investment.objects.select_related("package", "user")
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    if date_from:
        investments = investments.filter(created_at__date__gte=date_from)
    if date_to:
        investments = investments.filter(created_at__date__lte=date_to)
    investments = investments.order_by("-created_at")
    return render(
        request,
        "core/investment_reports.html",
        {
            "page_title": "Investment Reports",
            "investments": investments,
            "is_admin_view": True,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
def transaction_reports(request: HttpRequest):
    if request.user.is_staff:
        return redirect("admin-transaction-reports")

    wallet_transactions = WalletTransaction.objects.filter(user=request.user)
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    if date_from:
        wallet_transactions = wallet_transactions.filter(created_at__date__gte=date_from)
    if date_to:
        wallet_transactions = wallet_transactions.filter(created_at__date__lte=date_to)
    wallet_transactions = wallet_transactions.order_by("-created_at")
    return render(
        request,
        "core/transaction_reports.html",
        {
            "page_title": "Transaction Reports",
            "wallet_transactions": wallet_transactions,
            "is_admin_view": False,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
def admin_transaction_reports(request: HttpRequest):
    if not request.user.is_staff:
        return redirect("transaction-reports")

    payments = ManualPaymentRequest.objects.all()
    withdrawals = ManualWithdrawalRequest.objects.all()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    if date_from:
        payments = payments.filter(created_at__date__gte=date_from)
        withdrawals = withdrawals.filter(created_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(created_at__date__lte=date_to)
        withdrawals = withdrawals.filter(created_at__date__lte=date_to)

    rows = []
    for item in payments.select_related("user"):
        rows.append(
            {
                "created_at": item.created_at,
                "type": "Add Money",
                "request_code": item.request_code,
                "username": item.user.username,
                "amount": item.amount,
                "method": item.payment_method,
                "reference": item.transaction_reference,
                "status": item.status,
                "fee": Decimal("0.00"),
                "net": item.amount,
                "note": item.details,
            }
        )
    for item in withdrawals.select_related("user"):
        rows.append(
            {
                "created_at": item.created_at,
                "type": "Withdrawal",
                "request_code": item.request_code,
                "username": item.user.username,
                "amount": item.amount,
                "method": item.payment_method,
                "reference": item.account_details,
                "status": item.status,
                "fee": item.withdrawal_fee_amount,
                "net": item.net_amount,
                "note": item.admin_note,
            }
        )

    rows.sort(key=lambda row: row["created_at"], reverse=True)
    return render(
        request,
        "core/transaction_reports.html",
        {
            "page_title": "Transaction Reports",
            "rows": rows,
            "is_admin_view": True,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
def admin_profit_distribution_reports(request: HttpRequest):
    if not request.user.is_staff:
        return redirect("dashboard")

    reports = ProfitDistribution.objects.select_related("created_by")
    unsettled_account = UnsettledBalanceAccount.objects.filter(name="Unsettled Balance").first()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    if date_from:
        reports = reports.filter(created_at__date__gte=date_from)
    if date_to:
        reports = reports.filter(created_at__date__lte=date_to)
    reports = reports.order_by("-created_at")
    unsettled_total = reports.aggregate(total=Sum("total_unsettled_commission"))["total"] or Decimal("0.00")

    return render(
        request,
        "core/profit_distribution_reports.html",
        {
            "page_title": "Profit Distribution Reports",
            "reports": reports,
            "date_from": date_from,
            "date_to": date_to,
            "unsettled_account_balance": unsettled_account.balance if unsettled_account else Decimal("0.00"),
            "filtered_unsettled_total": unsettled_total,
        },
    )


@login_required
def admin_profit_distribution_details(request: HttpRequest):
    if not request.user.is_staff:
        return redirect("dashboard")

    entries = ProfitDistributionEntry.objects.select_related(
        "distribution",
        "user",
        "investment",
    )
    unsettled_entries = UnsettledBalanceEntry.objects.select_related(
        "source_user",
        "investment",
        "distribution",
    )
    unsettled_account = UnsettledBalanceAccount.objects.filter(name="Unsettled Balance").first()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    if date_from:
        entries = entries.filter(created_at__date__gte=date_from)
        unsettled_entries = unsettled_entries.filter(created_at__date__gte=date_from)
    if date_to:
        entries = entries.filter(created_at__date__lte=date_to)
        unsettled_entries = unsettled_entries.filter(created_at__date__lte=date_to)
    entries = entries.order_by("-created_at")
    unsettled_entries = unsettled_entries.order_by("-created_at")
    unsettled_total = unsettled_entries.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    return render(
        request,
        "core/profit_distribution_details.html",
        {
            "page_title": "Profit Distribution Details",
            "entries": entries,
            "date_from": date_from,
            "date_to": date_to,
            "unsettled_entries": unsettled_entries,
            "unsettled_total": unsettled_total,
            "unsettled_account_balance": unsettled_account.balance if unsettled_account else Decimal("0.00"),
        },
    )


@login_required
def admin_unsettled_balance_reports(request: HttpRequest):
    if not request.user.is_staff:
        return redirect("dashboard")

    entries = UnsettledBalanceEntry.objects.select_related(
        "source_user",
        "investment",
        "distribution",
    )
    unsettled_account = UnsettledBalanceAccount.objects.filter(name="Unsettled Balance").first()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    distribution_id = (request.GET.get("distribution_id") or "").strip()
    export = (request.GET.get("export") or "").strip().lower()
    if date_from:
        entries = entries.filter(created_at__date__gte=date_from)
    if date_to:
        entries = entries.filter(created_at__date__lte=date_to)
    if distribution_id:
        entries = entries.filter(distribution_id=distribution_id)
    entries = entries.order_by("-created_at")
    filtered_total = entries.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    distribution_choices = (
        UnsettledBalanceEntry.objects.exclude(distribution_id__isnull=True)
        .values_list("distribution_id", flat=True)
        .distinct()
        .order_by("-distribution_id")
    )

    if export == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="unsettled_balance_reports.csv"'
        writer = csv.writer(response)
        writer.writerow(
            ["#", "Distribution", "Source User", "Investment", "Amount", "Missing Levels", "Description", "Date"]
        )
        for index, item in enumerate(entries, start=1):
            writer.writerow(
                [
                    index,
                    item.distribution_id or "-",
                    item.source_user.username if item.source_user else "-",
                    item.investment.investment_code if item.investment else "-",
                    item.amount,
                    (
                        f"L{item.missing_from_level} to L{item.missing_to_level}"
                        if item.missing_from_level and item.missing_to_level
                        else "-"
                    ),
                    item.description,
                    timezone.localtime(item.created_at).strftime("%d %b %Y, %I:%M %p"),
                ]
            )
        return response

    return render(
        request,
        "core/unsettled_balance_reports.html",
        {
            "page_title": "Unsettled Balance Reports",
            "entries": entries,
            "date_from": date_from,
            "date_to": date_to,
            "distribution_id": distribution_id,
            "distribution_choices": distribution_choices,
            "unsettled_account_balance": unsettled_account.balance if unsettled_account else Decimal("0.00"),
            "filtered_total": filtered_total,
        },
    )


@login_required
def payment_method_info(request: HttpRequest):
    method_id = request.GET.get("id")
    method = PaymentMethod.objects.filter(id=method_id, is_active=True).first()
    if not method:
        return JsonResponse({"ok": False, "error": "Invalid payment method"}, status=404)

    return JsonResponse(
        {
            "ok": True,
            "name": method.name,
            "account_details": method.account_details or "",
            "instruction": method.instruction or "",
        }
    )


@login_required
def withdrawal_method_info(request: HttpRequest):
    method_id = request.GET.get("id")
    method = WithdrawalMethod.objects.filter(id=method_id, is_active=True).first()
    if not method:
        return JsonResponse({"ok": False, "error": "Invalid withdrawal method"}, status=404)

    return JsonResponse(
        {
            "ok": True,
            "name": method.name,
            "account_details": method.account_details or "",
            "instruction": method.instruction or "",
            "withdrawal_fee_percent": str(method.withdrawal_fee_percent),
            "withdrawal_fee_fixed": str(method.withdrawal_fee_fixed),
        }
    )


