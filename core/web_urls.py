from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.urls import path

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("user-dashboard/", views.user_dashboard, name="user-dashboard"),
    path("profile/", views.page_profile, name="page-profile"),
    path("referral/", views.referral_info, name="referral-info"),
    path("users-referral/", views.users_referral, name="users-referral"),
    path("add-money/", views.add_money_page, name="add-money"),
    path("manual-payment/", views.manual_payment, name="manual-payment"),
    path("manual-payment/method-info/", views.payment_method_info, name="payment-method-info"),
    path("manual-withdrawal/", views.manual_withdrawal, name="manual-withdrawal"),
    path("manual-withdrawal/method-info/", views.withdrawal_method_info, name="withdrawal-method-info"),
    path("manual-withdrawal/verify/", views.withdrawal_email_verify, name="withdrawal-email-verify"),
    path(
        "manual-withdrawal/verify/<str:token>/",
        views.withdrawal_email_link_verify,
        name="withdrawal-email-link-verify",
    ),
    path("investments/", views.investment_page, name="investment-page"),
    path("investments/packages/", views.investment_packages_page, name="investment-packages"),
    path(
        "transactions/payment-withdrawal/",
        views.payment_withdrawal_transaction,
        name="payment-withdrawal-transaction",
    ),
    path("reports/investments/", views.investment_reports, name="investment-reports"),
    path("reports/transactions/", views.transaction_reports, name="transaction-reports"),
    path("register/", views.referral_code_entry, name="referral-entry"),
    path("register/create/", views.register_with_referral, name="register-with-referral"),
    path("register/verify/", views.register_email_verify, name="register-email-verify"),
    path(
        "register/verify/<str:token>/",
        views.register_email_link_verify,
        name="register-email-link-verify",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("lock-screen/", views.lock_screen, name="lock-screen"),
    path("lock-screen/set/", views.set_lock_screen, name="lock-screen-set"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html"
        ),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
