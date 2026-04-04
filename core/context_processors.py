from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone


def admin_user_status_counts(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_staff:
        return {}

    User = get_user_model()
    cutoff = timezone.now() - timedelta(minutes=2)
    online = User.objects.filter(last_seen_at__gte=cutoff).count()
    offline = User.objects.filter(Q(last_seen_at__lt=cutoff) | Q(last_seen_at__isnull=True)).count()

    return {"admin_user_status_counts": {"online": online, "offline": offline}}

