from django.contrib.auth.decorators import login_required
from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('join/<uuid:uuid>', views.join, name='join'),
    path('invite/<uuid:squadid>/<int:steamid>', login_required(views.invite), name='invite'),
    path('settings', login_required(views.settings), name='settings'),
    path('csv/<int:steamid>', views.export_csv, name='csv'),
    path('create_notebook/<int:steamid>', views.create_notebook, name='notebook'),
]
