from django.urls import path

from orders import views

app_name = "orders"

urlpatterns = [
    path("", views.quote, name="quote"),
    path("thanks/", views.thanks, name="thanks"),
]
