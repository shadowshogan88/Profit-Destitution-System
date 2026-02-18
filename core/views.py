import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.hashers import make_password
from django.db.models import Avg
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Investment,
    InvestmentPackage,
    InvestmentWallet,
    ManualPaymentRequest,
    PaymentMethod,
    WalletTransaction,
)
from .services import (
    create_investment,
    create_package_investment,
    realize_profit,
    settle_matured_investments,
)

User = get_user_model()
MAX_REFERRAL_LEVEL = 5


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
    user_type = (data.get("user_type") or User.UserType.USER).strip().lower()
    referrer_code = (data.get("referrer_code") or "").strip().upper()

    if not username or not password or not referrer_code:
        return JsonResponse({"error": "username, password and referrer_code are required"}, status=400)

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
        referred_by=referred_by,
        user_type=user_type,
        is_staff=(user_type == User.UserType.ADMIN),
    )
    return JsonResponse({"id": user.id, "username": user.username, "user_type": user.user_type})


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


@login_required
def dashboard(request: HttpRequest):
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
            return redirect("dashboard")

    investments = user.investments.order_by("-created_at")
    won_investments = investments.filter(profit_realized__gt=Decimal("0.00"))
    wallet_transactions = WalletTransaction.objects.filter(user=user).order_by("-created_at")[:15]

    total_invested = sum((item.principal_amount for item in investments), Decimal("0.00"))
    total_profit_won = sum((item.profit_realized for item in won_investments), Decimal("0.00"))
    commission_total = sum(
        (item.commission_amount for item in user.commission_earnings.all()),
        Decimal("0.00"),
    )

    context = {
        "total_invested": total_invested,
        "total_profit_won": total_profit_won,
        "commission_total": commission_total,
        "investments": investments[:20],
        "won_investments": won_investments[:20],
        "wallet_transactions": wallet_transactions,
        "direct_downline_count": user.downlines.count(),
    }
    return render(request, "core/dashboard.html", context)


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
        user_type = (request.POST.get("user_type") or User.UserType.USER).strip().lower()
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""

        if not username or not password:
            messages.error(request, "Username and password are required.")
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
        if user_type not in {User.UserType.ADMIN, User.UserType.USER}:
            messages.error(request, "Invalid user type selected.")
            return redirect("register-with-referral")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            referred_by=referrer,
            user_type=user_type,
            is_staff=(user_type == User.UserType.ADMIN),
        )
        request.session.pop("signup_referrer_id", None)
        login(request, user)
        messages.success(request, "Registration successful.")
        return redirect("dashboard")

    return render(
        request,
        "registration/register_with_referral.html",
        {"referrer": referrer},
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

        ManualPaymentRequest.objects.create(
            user=request.user,
            amount=amount,
            payment_method=selected_method.name,
            transaction_reference=transaction_reference,
            details=details,
            proof_image=proof_image,
        )
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
def investment_page(request: HttpRequest):
    settle_matured_investments(user=request.user)
    investment_wallet, _ = InvestmentWallet.objects.get_or_create(user=request.user)
    if request.method == "POST":
        package_id = request.POST.get("package_id")
        package = InvestmentPackage.objects.filter(id=package_id, is_active=True).first()
        if not package:
            messages.error(request, "Invalid investment package selected.")
            return redirect("investment-page")

        try:
            investment = create_package_investment(request.user, package)
            messages.success(
                request,
                f"Investment #{investment.id} started for {package.duration_days} days.",
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("investment-page")

    packages = InvestmentPackage.objects.filter(is_active=True).order_by("name")
    active_investments = request.user.investments.filter(status=Investment.Status.ACTIVE).order_by("-created_at")
    completed_investments = request.user.investments.filter(status=Investment.Status.COMPLETED).order_by("-created_at")
    return_average = completed_investments.aggregate(avg=Avg("principal_amount"))["avg"] or Decimal("0.00")
    return render(
        request,
        "core/investment_page.html",
        {
            "packages": packages,
            "active_investments": active_investments,
            "completed_investments": completed_investments,
            "investment_wallet_balance": investment_wallet.balance,
            "return_average": return_average,
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
