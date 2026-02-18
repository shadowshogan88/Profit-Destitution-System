from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.register_user, name="register-user"),
    path("wallet/deposit/", views.deposit_wallet, name="wallet-deposit"),
    path("investments/create/", views.create_user_investment, name="investment-create"),
    path("investments/realize-profit/", views.realize_investment_profit, name="investment-realize-profit"),
    path("users/<str:username>/summary/", views.user_summary, name="user-summary"),
]
