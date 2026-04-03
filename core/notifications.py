import logging
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend as SmtpEmailBackend
from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    EmailConfiguration,
    Investment,
    InvestmentReturnRequest,
    InvestmentTopUp,
    ManualPaymentRequest,
    ManualWithdrawalRequest,
)

logger = logging.getLogger(__name__)


def _get_connection():
    cfg = EmailConfiguration.get_active()
    if cfg.smtp_host:
        return SmtpEmailBackend(
            host=cfg.smtp_host,
            port=int(cfg.smtp_port or 587),
            username=cfg.smtp_username or None,
            password=cfg.smtp_password or None,
            use_tls=bool(cfg.smtp_use_tls),
            use_ssl=bool(cfg.smtp_use_ssl),
            fail_silently=False,
        )
    return mail.get_connection(fail_silently=False)


def _send_templated_email(
    *,
    to_email: str,
    subject: str,
    template_txt: str,
    template_html: str,
    context: dict,
) -> bool:
    to_email = (to_email or "").strip()
    if not to_email:
        return False

    cfg = EmailConfiguration.get_active()
    context = {
        "app_name": (cfg.app_name or getattr(settings, "EMAIL_APP_NAME", "Referral System")),
        "year": timezone.now().year,
        **(context or {}),
    }
    try:
        rendered_subject = Template(subject).render(Context(context)).strip()
    except Exception:
        rendered_subject = subject
    if not rendered_subject:
        rendered_subject = subject
    try:
        connection = _get_connection()
        text_body = render_to_string(template_txt, context)
        html_body = render_to_string(template_html, context)
        message = EmailMultiAlternatives(
            subject=rendered_subject,
            body=text_body,
            from_email=(cfg.default_from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None)),
            to=[to_email],
            connection=connection,
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Failed sending notification email subject=%s to=%s", subject, to_email)
        return False


def _admin_emails() -> list[str]:
    cfg = EmailConfiguration.get_active()
    if not cfg.notify_admin_events_enabled:
        return []
    raw = (cfg.admin_notification_emails or "").strip()
    if not raw:
        return []
    emails: list[str] = []
    for item in raw.replace(";", ",").split(","):
        email = item.strip()
        if email:
            emails.append(email)
    return emails


def _send_templated_email_to_admins(
    *,
    subject: str,
    template_txt: str,
    template_html: str,
    context: dict,
) -> int:
    sent = 0
    for email in _admin_emails():
        if _send_templated_email(
            to_email=email,
            subject=subject,
            template_txt=template_txt,
            template_html=template_html,
            context=context,
        ):
            sent += 1
    return sent


def send_admin_add_money_submitted(user, payment_req: ManualPaymentRequest) -> int:
    return _send_templated_email_to_admins(
        subject="{{ app_name }} - Add money submitted",
        template_txt="emails/admin_add_money_submitted.txt",
        template_html="emails/admin_add_money_submitted.html",
        context={
            "username": user.username,
            "request_code": payment_req.request_code,
            "amount": payment_req.amount,
            "payment_method": payment_req.payment_method,
            "reference": payment_req.transaction_reference,
            "created_at": payment_req.created_at,
        },
    )


def send_admin_investment_created(user, investment: Investment) -> int:
    return _send_templated_email_to_admins(
        subject="{{ app_name }} - New investment",
        template_txt="emails/admin_investment_created.txt",
        template_html="emails/admin_investment_created.html",
        context={
            "username": user.username,
            "investment_code": investment.investment_code,
            "amount": investment.principal_amount,
            "duration_days": investment.duration_days or (investment.package.duration_days if investment.package_id else 0),
            "package_name": (investment.package.name if investment.package_id else ""),
            "starts_at": investment.starts_at,
            "ends_at": investment.ends_at,
        },
    )


def send_admin_investment_topped_up(user, topup: InvestmentTopUp) -> int:
    inv = topup.investment
    return _send_templated_email_to_admins(
        subject="{{ app_name }} - Investment increased",
        template_txt="emails/admin_investment_topped_up.txt",
        template_html="emails/admin_investment_topped_up.html",
        context={
            "username": user.username,
            "investment_code": inv.investment_code,
            "topup_amount": topup.amount,
            "previous_principal": topup.previous_principal,
            "new_principal": topup.new_principal,
            "previous_ends_at": topup.previous_ends_at,
            "new_ends_at": topup.new_ends_at,
            "created_at": topup.created_at,
        },
    )


def send_admin_investment_return_requested(user, req: InvestmentReturnRequest) -> int:
    inv = req.investment
    return _send_templated_email_to_admins(
        subject="{{ app_name }} - Return requested",
        template_txt="emails/admin_investment_return_requested.txt",
        template_html="emails/admin_investment_return_requested.html",
        context={
            "username": user.username,
            "investment_code": inv.investment_code,
            "principal_amount": inv.principal_amount,
            "requested_at": req.requested_at,
            "scheduled_return_at": req.scheduled_return_at,
        },
    )


def send_admin_investment_return_canceled(user, req: InvestmentReturnRequest) -> int:
    inv = req.investment
    return _send_templated_email_to_admins(
        subject="{{ app_name }} - Return request canceled",
        template_txt="emails/admin_investment_return_canceled.txt",
        template_html="emails/admin_investment_return_canceled.html",
        context={
            "username": user.username,
            "investment_code": inv.investment_code,
            "principal_amount": inv.principal_amount,
            "requested_at": req.requested_at,
        },
    )


def send_admin_withdrawal_submitted(user, withdrawal_req: ManualWithdrawalRequest) -> int:
    return _send_templated_email_to_admins(
        subject="{{ app_name }} - Withdrawal submitted",
        template_txt="emails/admin_withdrawal_submitted.txt",
        template_html="emails/admin_withdrawal_submitted.html",
        context={
            "username": user.username,
            "request_code": withdrawal_req.request_code,
            "amount": withdrawal_req.amount,
            "net_amount": withdrawal_req.net_amount,
            "payment_method": withdrawal_req.payment_method,
            "created_at": withdrawal_req.created_at,
        },
    )


def send_admin_withdrawal_confirmed(user, withdrawal_req: ManualWithdrawalRequest) -> int:
    return _send_templated_email_to_admins(
        subject="{{ app_name }} - Withdrawal OTP verified",
        template_txt="emails/admin_withdrawal_confirmed.txt",
        template_html="emails/admin_withdrawal_confirmed.html",
        context={
            "username": user.username,
            "request_code": withdrawal_req.request_code,
            "amount": withdrawal_req.amount,
            "net_amount": withdrawal_req.net_amount,
            "payment_method": withdrawal_req.payment_method,
            "confirmed_at": withdrawal_req.email_otp_verified_at,
        },
    )


def send_investment_confirmed(user, investment: Investment) -> bool:
    if not getattr(user, "email", ""):
        return False
    cfg = EmailConfiguration.get_active()
    if not cfg.notify_investment_confirmed_enabled:
        return False
    return _send_templated_email(
        to_email=user.email,
        subject=(cfg.subject_investment_confirmed or "{{ app_name }} - Investment confirmed"),
        template_txt="emails/investment_confirmed.txt",
        template_html="emails/investment_confirmed.html",
        context={
            "username": user.username,
            "investment_code": investment.investment_code,
            "amount": investment.principal_amount,
            "duration_days": investment.duration_days or (investment.package.duration_days if investment.package_id else 0),
            "package_name": (investment.package.name if investment.package_id else ""),
            "starts_at": investment.starts_at,
            "ends_at": investment.ends_at,
        },
    )


def send_profit_received(user, *, amount: Decimal, note: str = "") -> bool:
    if not getattr(user, "email", ""):
        return False
    cfg = EmailConfiguration.get_active()
    if not cfg.notify_profit_received_enabled:
        return False
    return _send_templated_email(
        to_email=user.email,
        subject=(cfg.subject_profit_received or "{{ app_name }} - Profit received"),
        template_txt="emails/profit_received.txt",
        template_html="emails/profit_received.html",
        context={
            "username": user.username,
            "amount": amount,
            "note": note,
        },
    )


def send_add_money_submitted(user, payment_req: ManualPaymentRequest) -> bool:
    if not getattr(user, "email", ""):
        return False
    cfg = EmailConfiguration.get_active()
    if not cfg.notify_add_money_submitted_enabled:
        return False
    return _send_templated_email(
        to_email=user.email,
        subject=(cfg.subject_add_money_submitted or "{{ app_name }} - Add money request submitted"),
        template_txt="emails/add_money_submitted.txt",
        template_html="emails/add_money_submitted.html",
        context={
            "username": user.username,
            "request_code": payment_req.request_code,
            "amount": payment_req.amount,
            "payment_method": payment_req.payment_method,
            "reference": payment_req.transaction_reference,
            "created_at": payment_req.created_at,
        },
    )


def send_add_money_approved(user, payment_req: ManualPaymentRequest) -> bool:
    if not getattr(user, "email", ""):
        return False
    cfg = EmailConfiguration.get_active()
    if not cfg.notify_add_money_approved_enabled:
        return False
    return _send_templated_email(
        to_email=user.email,
        subject=(cfg.subject_add_money_approved or "{{ app_name }} - Add money approved"),
        template_txt="emails/add_money_approved.txt",
        template_html="emails/add_money_approved.html",
        context={
            "username": user.username,
            "request_code": payment_req.request_code,
            "amount": payment_req.amount,
            "payment_method": payment_req.payment_method,
            "credited_at": payment_req.credited_at,
        },
    )


def send_withdrawal_confirmed(user, withdrawal_req: ManualWithdrawalRequest) -> bool:
    if not getattr(user, "email", ""):
        return False
    cfg = EmailConfiguration.get_active()
    if not cfg.notify_withdrawal_confirmed_enabled:
        return False
    return _send_templated_email(
        to_email=user.email,
        subject=(cfg.subject_withdrawal_confirmed or "{{ app_name }} - Withdrawal request confirmed"),
        template_txt="emails/withdrawal_confirmed.txt",
        template_html="emails/withdrawal_confirmed.html",
        context={
            "username": user.username,
            "request_code": withdrawal_req.request_code,
            "amount": withdrawal_req.amount,
            "net_amount": withdrawal_req.net_amount,
            "payment_method": withdrawal_req.payment_method,
            "confirmed_at": withdrawal_req.email_otp_verified_at,
        },
    )


def send_withdrawal_approved(user, withdrawal_req: ManualWithdrawalRequest) -> bool:
    if not getattr(user, "email", ""):
        return False
    cfg = EmailConfiguration.get_active()
    if not cfg.notify_withdrawal_approved_enabled:
        return False
    return _send_templated_email(
        to_email=user.email,
        subject=(cfg.subject_withdrawal_approved or "{{ app_name }} - Withdrawal approved"),
        template_txt="emails/withdrawal_approved.txt",
        template_html="emails/withdrawal_approved.html",
        context={
            "username": user.username,
            "request_code": withdrawal_req.request_code,
            "amount": withdrawal_req.amount,
            "net_amount": withdrawal_req.net_amount,
            "payment_method": withdrawal_req.payment_method,
            "fee_amount": withdrawal_req.withdrawal_fee_amount,
            "approved_at": withdrawal_req.debited_at,
        },
    )
