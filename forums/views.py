from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Post, Comment, Reaction


def forum_view(request):
    """Display all forum posts"""
    posts = Post.objects.all()
    return render(request, 'forums/forum.html', {'posts': posts})


@login_required
def create_post_view(request):
    """Create a new forum post"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        
        if title and content:
            post = Post.objects.create(
                title=title,
                content=content,
                author=request.user
            )
            messages.success(request, 'Post created successfully!')
            return redirect('forum')
        else:
            messages.error(request, 'Please provide both title and content.')
    
    return render(request, 'forums/create_post.html')


def post_detail_view(request, post_id):
    """Display a single post with its comments"""
    post = get_object_or_404(Post, id=post_id)
    comments = post.comments.all()
    
    # Check if user has reacted to post
    post_user_reacted = False
    if request.user.is_authenticated:
        post_user_reacted = post.reactions.filter(user=request.user).exists()
        # Add user_reacted attribute to each comment
        for comment in comments:
            comment.user_reacted = comment.reactions.filter(user=request.user).exists()
    else:
        # Set default value for unauthenticated users
        for comment in comments:
            comment.user_reacted = False
    
    if request.method == 'POST' and request.user.is_authenticated:
        # Check if it's a comment submission
        content = request.POST.get('content', '').strip()
        if content:
            Comment.objects.create(
                post=post,
                author=request.user,
                content=content
            )
            messages.success(request, 'Comment added successfully!')
            return redirect('post_detail', post_id=post.id)
        else:
            messages.error(request, 'Please provide comment content.')
    
    return render(request, 'forums/post_detail.html', {
        'post': post,
        'comments': comments,
        'post_user_reacted': post_user_reacted
    })


@login_required
def toggle_reaction_view(request, post_id=None, comment_id=None):
    """Toggle reaction (like/unlike) for a post or comment"""
    if post_id:
        obj = get_object_or_404(Post, id=post_id)
        reaction, created = Reaction.objects.get_or_create(
            user=request.user,
            post=obj,
            defaults={'comment': None}
        )
        if not created:
            reaction.delete()
            reacted = False
        else:
            reacted = True
        count = obj.reaction_count
    elif comment_id:
        obj = get_object_or_404(Comment, id=comment_id)
        reaction, created = Reaction.objects.get_or_create(
            user=request.user,
            comment=obj,
            defaults={'post': None}
        )
        if not created:
            reaction.delete()
            reacted = False
        else:
            reacted = True
        count = obj.reaction_count
    else:
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'reacted': reacted,
            'count': count
        })
    
    # Fallback for non-AJAX requests
    if post_id:
        return redirect('post_detail', post_id=post_id)
    return redirect('post_detail', post_id=obj.post.id)
