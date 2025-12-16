# forums/urls.py

from django.urls import path

from . import views

urlpatterns = [
    # Forum listing and detail
    path("", views.forum_list, name="forum_list"),
    path("<int:forum_id>/", views.forum_detail, name="forum_detail"),
    # Topic management
    path("<int:forum_id>/create-topic/", views.topic_create, name="topic_create"),
    path("topic/<int:topic_id>/", views.topic_detail, name="topic_detail"),
    # Post management (Reply to a Topic)
    path("topic/<int:topic_id>/reply/", views.post_create, name="post_create"),
    # Comment management
    path("post/<int:post_id>/comment/", views.comment_create, name="comment_create"),
    # Voting
    path("post/<int:post_id>/vote/", views.post_vote, name="post_vote"),
    # Special listings
    path("case-studies/", views.case_studies_list, name="case_studies_list"),
    path(
        "preparation-strategies/",
        views.preparation_strategies_list,
        name="preparation_strategies_list",
    ),
]
