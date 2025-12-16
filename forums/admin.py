from django.contrib import admin
from .models import Forum, Topic, Post, Comment, MentorAssignment, PostVote


@admin.register(Forum)
class ForumAdmin(admin.ModelAdmin):
    list_display = ['name', 'user_type', 'is_active', 'topic_count', 'post_count', 'created_at']
    list_filter = ['is_active', 'user_type', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {}
    
    def topic_count(self, obj):
        return obj.topics.count()
    topic_count.short_description = 'Topics'
    
    def post_count(self, obj):
        return Post.objects.filter(topic__forum=obj).count()
    post_count.short_description = 'Posts'


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['title', 'forum', 'author', 'is_pinned', 'is_locked', 'view_count', 'reply_count', 'created_at']
    list_filter = ['is_pinned', 'is_locked', 'forum', 'created_at']
    search_fields = ['title', 'description', 'author__username']
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    
    def reply_count(self, obj):
        return obj.posts.count() - 1
    reply_count.short_description = 'Replies'


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['id', 'topic', 'author', 'is_case_study', 'is_preparation_strategy', 'score', 'upvotes', 'downvotes', 'created_at']
    list_filter = ['is_case_study', 'is_preparation_strategy', 'created_at', 'topic__forum']
    search_fields = ['content', 'author__username', 'topic__title']
    readonly_fields = ['upvotes', 'downvotes', 'created_at', 'updated_at', 'edited_at']
    
    def score(self, obj):
        return obj.upvotes - obj.downvotes
    score.short_description = 'Score'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'author', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'author__username']


@admin.register(MentorAssignment)
class MentorAssignmentAdmin(admin.ModelAdmin):
    list_display = ['forum', 'mentor', 'is_active', 'assigned_at']
    list_filter = ['is_active', 'assigned_at', 'forum']
    search_fields = ['forum__name', 'mentor__username']


@admin.register(PostVote)
class PostVoteAdmin(admin.ModelAdmin):
    list_display = ['post', 'user', 'vote_type', 'created_at']
    list_filter = ['vote_type', 'created_at']
    search_fields = ['post__content', 'user__username']
