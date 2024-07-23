from django.urls import path
from django.contrib.auth.decorators import login_required

from . import views

urlpatterns = [
    path('', views.squads, {'squad': None}, name='squads'),
    path('<uuid:squad>', views.squads, name='squads'),
    path('<uuid:squad>/expand_stats', views.squad_expanded_stats, name='squad_expanded_stats'),
    path('matches', views.matches, name='matches'),
    path('matches/<uuid:squad>', views.matches, name='matches'),
    path('matches/<int:last_timestamp>', views.matches, name='matches'),
    path('matches/<uuid:squad>/<int:last_timestamp>', views.matches, name='matches'),
]
