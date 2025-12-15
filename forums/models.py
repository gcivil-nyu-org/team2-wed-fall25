from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_posts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def comment_count(self):
        return self.comments.count()
    
    @property
    def reaction_count(self):
        return self.reactions.count()
    
    def user_has_reacted(self, user):
        """Check if a user has reacted to this post"""
        if not user.is_authenticated:
            return False
        return self.reactions.filter(user=user).exists()


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"
    
    @property
    def reaction_count(self):
        return self.reactions.count()


class Reaction(models.Model):
    """Reactions (likes/upvotes) for posts and comments"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_reactions')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions', null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reactions', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['user', 'post'], ['user', 'comment']]
        ordering = ['-created_at']
    
    def __str__(self):
        if self.post:
            return f"{self.user.username} reacted to post: {self.post.title}"
        return f"{self.user.username} reacted to comment"
