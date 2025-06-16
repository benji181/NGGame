from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('game/levels/', views.game_levels, name='game_levels'),
    path('game/play/<str:difficulty>/', views.play_game, name='play_game'),
    path('game/reset/', views.reset_game, name='reset_game'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('profile/', views.profile, name='profile'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin-panel/delete-user/<str:uid>/', views.delete_user, name='delete_user'),
    path('contact/', views.contact, name='contact'),
    path('feedback/', views.feedback, name='feedback'),
]