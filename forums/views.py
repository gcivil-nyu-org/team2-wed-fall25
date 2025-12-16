# forums/views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from .forms import CommentForm, PostForm, TopicForm
from .models import Forum, MentorAssignment, Post, PostVote, Topic, Topic


def forum_list(request):
    """Display all available forums"""
    forums = (
        Forum.objects.filter(is_active=True)
        .annotate(
            topic_count_annotated=Count("topics"),
            post_count_annotated=Count("topics__posts"),
        )
        .order_by("name")
    )

    # Filter by user type if user is authenticated
    if request.user.is_authenticated:
        user_forums = forums.filter(
            Q(user_type=request.user.user_type) | Q(user_type__isnull=True)
        )
    else:
        user_forums = forums.filter(user_type__isnull=True)

    # Get user's mentored forums if they're a mentor
    mentored_forums = []
    if request.user.is_authenticated:
        mentored_forums = MentorAssignment.objects.filter(
            mentor=request.user, is_active=True
        ).values_list("forum_id", flat=True)

    context = {
        "forums": user_forums,
        "mentored_forums": mentored_forums,
    }
    return render(request, "forums/forum_list.html", context)


def forum_detail(request, forum_id):
    """Display topics within a forum"""
    forum = get_object_or_404(Forum, pk=forum_id, is_active=True)

    # Check if user has access
    if forum.user_type and request.user.is_authenticated:
        if request.user.user_type != forum.user_type:
            messages.error(request, "You don't have access to this forum.")
            return redirect("forum_list")
    elif forum.user_type and not request.user.is_authenticated:
        messages.error(request, "Please log in to access this forum.")
        return redirect("login")

    # Get topics with additional info
    # FIX APPLIED: Renamed annotation to 'num_replies' to avoid conflict with Topic model @property
    topics = forum.topics.annotate(
        num_replies=Count("posts") - 1, last_activity=Max("posts__created_at")
    ).order_by("-is_pinned", "-created_at")

    # Pagination
    paginator = Paginator(topics, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Check if user is a mentor
    is_mentor = False
    if request.user.is_authenticated:
        is_mentor = MentorAssignment.objects.filter(
            forum=forum, mentor=request.user, is_active=True
        ).exists()

    context = {
        "forum": forum,
        "page_obj": page_obj,
        "is_mentor": is_mentor,
    }
    return render(request, "forums/forum_detail.html", context)


@login_required
def topic_create(request, forum_id):
    """Create a new topic"""
    forum = get_object_or_404(Forum, pk=forum_id, is_active=True)

    # Check access
    if forum.user_type and request.user.user_type != forum.user_type:
        messages.error(request, "You don't have access to create topics in this forum.")
        return redirect("forum_detail", forum_id=forum_id)

    if request.method == "POST":
        form = TopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.forum = forum
            topic.author = request.user
            topic.save()

            # Logic to create initial Post would go here, if needed.
            
            messages.success(request, "Topic created successfully!")
            return redirect("topic_detail", topic_id=topic.pk)
    else:
        form = TopicForm()

    context = {
        "form": form,
        "forum": forum,
    }
    return render(request, "forums/topic_create.html", context)


def topic_detail(request, topic_id):
    """Display topic with all posts and comments"""
    topic = get_object_or_404(Topic, pk=topic_id)

    # Check access
    if topic.forum.user_type and request.user.is_authenticated:
        if request.user.user_type != topic.forum.user_type:
            messages.error(request, "You don't have access to this topic.")
            return redirect("forum_list")
    elif topic.forum.user_type and not request.user.is_authenticated:
        messages.error(request, "Please log in to view this topic.")
        return redirect("login")

    # Increment view count
    if request.user.is_authenticated:
        topic.increment_views()

    # Get all posts with comments
    posts = (
        topic.posts.select_related("author")
        .prefetch_related("comments__author")
        .order_by("created_at")
    )

    # Pagination for posts
    paginator = Paginator(posts, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "topic": topic,
        "page_obj": page_obj,
        "forum": topic.forum,
    }
    return render(request, "forums/topic_detail.html", context)


@login_required
def post_create(request, topic_id):
    """Create a new post/reply in a topic"""
    topic = get_object_or_404(Topic, pk=topic_id)

    # Check if topic is locked
    if topic.is_locked:
        messages.error(request, "This topic is locked. No new replies are allowed.")
        return redirect("topic_detail", topic_id=topic_id)

    # Check access
    if topic.forum.user_type and request.user.user_type != topic.forum.user_type:
        messages.error(request, "You don't have access to post in this topic.")
        return redirect("topic_detail", topic_id=topic_id)

    if request.method == "POST":
        form = PostForm(request.POST) 
        if form.is_valid():
            post = form.save(commit=False)
            post.topic = topic
            post.author = request.user
            post.save()
            messages.success(request, "Your reply has been posted!")
            return redirect("topic_detail", topic_id=topic_id)
    else:
        form = PostForm()

    context = {
        "form": form,
        "topic": topic,
        "forum": topic.forum,
    }
    return render(request, "forums/post_create.html", context)


@login_required
def comment_create(request, post_id):
    """Create a comment on a post"""
    post = get_object_or_404(Post, pk=post_id)

    # Check if topic is locked
    if post.topic.is_locked:
        messages.error(request, "This topic is locked. No new comments are allowed.")
        return redirect("topic_detail", topic_id=post.topic.pk)

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            messages.success(request, "Your comment has been added!")
            return redirect("topic_detail", topic_id=post.topic.pk)
    else:
        form = CommentForm()

    context = {
        "form": form,
        "post": post,
        "topic": post.topic,
    }
    return render(request, "forums/comment_create.html", context)


@login_required
def post_vote(request, post_id):
    """Handle upvote/downvote on posts"""
    post = get_object_or_404(Post, pk=post_id)
    vote_type = request.POST.get("vote_type")  # 'up' or 'down'

    if vote_type not in ["up", "down"]:
        return JsonResponse({"error": "Invalid vote type"}, status=400)

    # Check if user already voted
    existing_vote = PostVote.objects.filter(post=post, user=request.user).first()

    if existing_vote:
        # If same vote type, remove vote
        if existing_vote.vote_type == vote_type:
            if vote_type == "up":
                post.upvotes = max(0, post.upvotes - 1)
            else:
                post.downvotes = max(0, post.downvotes - 1)
            existing_vote.delete()
        else:
            # Change vote type
            if existing_vote.vote_type == "up":
                post.upvotes = max(0, post.upvotes - 1)
                post.downvotes += 1
            else:
                post.downvotes = max(0, post.downvotes - 1)
                post.upvotes += 1
            existing_vote.vote_type = vote_type
            existing_vote.save()
    else:
        # New vote
        PostVote.objects.create(post=post, user=request.user, vote_type=vote_type)
        if vote_type == "up":
            post.upvotes += 1
        else:
            post.downvotes += 1

    post.save()

    return JsonResponse(
        {
            "success": True,
            "upvotes": post.upvotes,
            "downvotes": post.downvotes,
            "score": post.score,
        }
    )


@login_required
def case_studies_list(request):
    """List all case studies across forums"""
    case_studies = (
        Post.objects.filter(is_case_study=True, topic__forum__is_active=True)
        .select_related("topic", "topic__forum", "author")
        .order_by("-created_at")
    )

    paginator = Paginator(case_studies, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "title": "Case Studies",
    }
    return render(request, "forums/case_studies_list.html", context)


@login_required
def preparation_strategies_list(request):
    """List all preparation strategies across forums"""
    strategies = (
        Post.objects.filter(is_preparation_strategy=True, topic__forum__is_active=True)
        .select_related("topic", "topic__forum", "author")
        .order_by("-created_at")
    )

    paginator = Paginator(strategies, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "title": "Preparation Strategies",
    }
    return render(request, "forums/preparation_strategies_list.html", context)
