from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.urls import path

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
    path("referral/", views.referral_info, name="referral-info"),
    path("manual-payment/", views.manual_payment, name="manual-payment"),
    path("manual-payment/method-info/", views.payment_method_info, name="payment-method-info"),
    path("investments/", views.investment_page, name="investment-page"),
    path("register/", views.referral_code_entry, name="referral-entry"),
    path("register/create/", views.register_with_referral, name="register-with-referral"),
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
