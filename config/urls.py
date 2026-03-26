from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path("admin/profit-distribution/", core_views.admin_profit_distribution, name="admin-profit-distribution"),
    path("admin/pending-add-money/", core_views.admin_pending_add_money, name="admin-pending-add-money"),
    path("admin/pending-withdrawals/", core_views.admin_pending_withdrawals, name="admin-pending-withdrawals"),
    path("admin/investment-reports/", core_views.admin_investment_reports, name="admin-investment-reports"),
    path("admin/transaction-reports/", core_views.admin_transaction_reports, name="admin-transaction-reports"),
    path("admin/profit-reports/", core_views.admin_profit_distribution_reports, name="admin-profit-reports"),
    path("admin/profit-reports/details/", core_views.admin_profit_distribution_details, name="admin-profit-reports-details"),
    path("admin/unsettled-balance-reports/", core_views.admin_unsettled_balance_reports, name="admin-unsettled-balance-reports"),
    path("admin/", admin.site.urls),
    path("", include("core.web_urls")),
    path("api/", include("core.urls")),
]

handler404 = "core.views.custom_page_not_found"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
