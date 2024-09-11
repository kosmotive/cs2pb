from django.urls import path

from . import views

urlpatterns = [
    path('<str:encoded_url>/', views.do_redirect, name='redirect'),
]
