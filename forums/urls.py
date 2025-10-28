from django.urls import path
from . import views

urlpatterns = [
    path('', views.forum_view, name='forum'),
]

