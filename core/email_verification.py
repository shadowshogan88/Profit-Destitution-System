import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import EmailOTP, SystemConfiguration

OTP_EXPIRY_MINUTES = 10


def create_email_otp(*, user, purpose: str, email: str, payload: dict | None = None) -> EmailOTP:
    return EmailOTP.objects.create(
        user=user,
        purpose=purpose,
        email=email,
        code=f"{secrets.randbelow(900000) + 100000:06d}",
        token=secrets.token_urlsafe(32),
        payload=payload or {},
        expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )


def build_verification_url(request, email_otp: EmailOTP) -> str:
    route_name = {
        EmailOTP.Purpose.REGISTRATION: "register-email-link-verify",
        EmailOTP.Purpose.WITHDRAWAL: "withdrawal-email-link-verify",
    }[email_otp.purpose]
    return request.build_absolute_uri(reverse(route_name, args=[email_otp.token]))


def send_email_otp(request, email_otp: EmailOTP) -> None:
    system_config = SystemConfiguration.load()
    verify_url = build_verification_url(request, email_otp)
    subject = {
        EmailOTP.Purpose.REGISTRATION: "Verify your email address",
        EmailOTP.Purpose.WITHDRAWAL: "Confirm your withdrawal request",
    }[email_otp.purpose]
    title = {
        EmailOTP.Purpose.REGISTRATION: "Email Verification",
        EmailOTP.Purpose.WITHDRAWAL: "Withdrawal Verification",
    }[email_otp.purpose]

    context = {
        "user": email_otp.user,
        "email_otp": email_otp,
        "verify_url": verify_url,
        "title": title,
        "expires_minutes": OTP_EXPIRY_MINUTES,
    }
    text_body = render_to_string("emails/verification_email.txt", context)
    html_body = render_to_string("emails/verification_email.html", context)

    connection = get_connection(
        backend=system_config.email_backend or settings.EMAIL_BACKEND,
        host=system_config.email_host or settings.EMAIL_HOST,
        port=system_config.email_port or settings.EMAIL_PORT,
        username=system_config.email_host_user or settings.EMAIL_HOST_USER,
        password=system_config.email_host_password or settings.EMAIL_HOST_PASSWORD,
        use_tls=system_config.email_use_tls,
        use_ssl=system_config.email_use_ssl,
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=system_config.default_from_email or settings.DEFAULT_FROM_EMAIL,
        to=[email_otp.email],
        connection=connection,
    )
    message.attach_alternative(html_body, "text/html")
    message.send()
