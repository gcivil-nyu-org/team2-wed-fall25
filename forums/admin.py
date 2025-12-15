from django.contrib import admin
from .models import Post, Comment, Reaction


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'created_at', 'comment_count', 'reaction_count']
    list_filter = ['created_at']
    search_fields = ['title', 'content', 'author__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['post', 'author', 'created_at', 'reaction_count']
    list_filter = ['created_at']
    search_fields = ['content', 'author__username', 'post__title']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'post', 'comment', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'post__title']
    readonly_fields = ['created_at']
