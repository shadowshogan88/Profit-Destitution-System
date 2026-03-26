from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse


class LockScreenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        static_prefix = f"/{settings.STATIC_URL.lstrip('/')}"
        media_prefix = f"/{settings.MEDIA_URL.lstrip('/')}"
        path = request.path

        if path.startswith(static_prefix) or path.startswith(media_prefix):
            return self.get_response(request)

        if request.user.is_authenticated and request.session.get("is_locked", False):
            try:
                current_name = resolve(path).url_name
            except Resolver404:
                current_name = None

            allowed_names = {
                "lock-screen",
                "lock-screen-set",
                "logout",
                "login",
                "password_reset",
                "password_reset_done",
                "password_reset_confirm",
                "password_reset_complete",
            }

            if current_name not in allowed_names:
                next_url = request.get_full_path()
                request.session["lock_next"] = next_url
                lock_url = reverse("lock-screen")
                return redirect(f"{lock_url}?next={next_url}")

        return self.get_response(request)
