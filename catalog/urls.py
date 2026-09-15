from django.urls import path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog_index, name="index"),
    path("catalog/<slug:slug>/", views.category_detail, name="category"),
    path("catalog/<slug:category_slug>/<slug:slug>/", views.product_detail, name="product"),
    path("contacts/", views.contacts, name="contacts"),
]
