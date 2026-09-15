from django.http import HttpResponsePermanentRedirect

from catalog.models import Redirect


class RedirectFallbackMiddleware:
    """Для 404-ответов ищет путь в таблице Redirect и отдаёт 301."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response
        target = Redirect.objects.filter(old_path=request.path).values_list("new_path", flat=True).first()
        if target:
            return HttpResponsePermanentRedirect(target)
        return response
