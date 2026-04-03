from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.urls import path

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("404/", views.custom_404_preview, name="custom-404-preview"),
    path("referral/", views.referral_info, name="referral-info"),
    path("users-referral/", views.users_referral, name="users-referral"),
    path("manual-payment/", views.manual_payment, name="manual-payment"),
    path("add-money/", views.add_money_page, name="add-money"),
    path("manual-withdrawal/", views.manual_withdrawal, name="manual-withdrawal"),
    path("manual-withdrawal/verify/", views.verify_withdrawal_otp, name="withdrawal-otp-verify"),
    path("manual-withdrawal/verify/resend/", views.resend_withdrawal_otp, name="withdrawal-otp-resend"),
    path("transactions/", views.payment_withdrawal_transaction, name="payment-withdrawal-transaction"),
    path("manual-payment/method-info/", views.payment_method_info, name="payment-method-info"),
    path("manual-withdrawal/method-info/", views.withdrawal_method_info, name="withdrawal-method-info"),
    path("investments/", views.investment_page, name="investment-page"),
    path("investments/packages/", views.investment_packages_page, name="investment-packages"),
    path("investments/topup/", views.investment_topup, name="investment-topup"),
    path("investments/return-request/", views.investment_return_request, name="investment-return-request"),
    path("investments/return-cancel/", views.investment_return_cancel, name="investment-return-cancel"),
    path("admin/profit-distribution/", views.admin_profit_distribution, name="admin-profit-distribution"),
    path("investment-reports/", views.investment_reports, name="investment-reports"),
    path("transaction-reports/", views.transaction_reports, name="transaction-reports"),
    path("register/", views.referral_code_entry, name="referral-entry"),
    path("register/create/", views.register_with_referral, name="register-with-referral"),
    path("verify-email/", views.verify_email, name="email-verify"),
    path("verify-email/resend/", views.resend_email_verification, name="email-verify-resend"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", views.logout_user, name="logout"),
    path("lock-screen/", views.lock_screen, name="lock-screen"),
    path("lock-screen/set/", views.set_lock_screen, name="lock-screen-set"),
    path("user-dashboard/", views.user_dashboard, name="user-dashboard"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.page_profile, name="page-profile"),
    path(
        "password-change/",
        views.DashboardPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password-change/done/",
        RedirectView.as_view(pattern_name="password_change", permanent=False),
        name="password_change_done",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url="/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url="/reset/done/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
