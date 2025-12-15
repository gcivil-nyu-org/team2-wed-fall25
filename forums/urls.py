from django.urls import path
from . import views

urlpatterns = [
    path('', views.forum_view, name='forum'),
    path('create/', views.create_post_view, name='create_post'),
    path('<int:post_id>/', views.post_detail_view, name='post_detail'),
    path('post/<int:post_id>/react/', views.toggle_reaction_view, name='react_post'),
    path('comment/<int:comment_id>/react/', views.toggle_reaction_view, name='react_comment'),
]

