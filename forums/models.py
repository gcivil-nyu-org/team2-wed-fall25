from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


class Forum(models.Model):
    """Main forum category for different discussion areas"""

    name = models.CharField(max_length=200)
    description = models.TextField(
        help_text="Brief description of what this forum is about"
    )
    icon = models.CharField(
        max_length=50,
        default="fa-comments",
        help_text="Font Awesome icon class (e.g., 'fa-comments', 'fa-code', 'fa-lightbulb')",
    )
    user_type = models.CharField(
        max_length=10,
        choices=User.USER_TYPES,
        null=True,
        blank=True,
        help_text="If specified, only users of this type can access. Leave blank for all users.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Forums"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("forum_detail", kwargs={"forum_id": self.pk})

    @property
    def topic_count(self):
        return self.topics.count()

    @property
    def post_count(self):
        return Post.objects.filter(topic__forum=self).count()

    @property
    def latest_activity(self):
        latest_post = (
            Post.objects.filter(topic__forum=self).order_by("-created_at").first()
        )
        if latest_post:
            return latest_post.created_at
        latest_topic = self.topics.order_by("-created_at").first()
        if latest_topic:
            return latest_topic.created_at
        return self.created_at


class Topic(models.Model):
    """Discussion topic within a forum"""

    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="topics")
    title = models.CharField(max_length=300)
    description = models.TextField(
        help_text="Initial post content or topic description"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="topics_created"
    )
    is_pinned = models.BooleanField(
        default=False, help_text="Pin important topics to the top"
    )
    is_locked = models.BooleanField(
        default=False, help_text="Lock to prevent new replies"
    )
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        verbose_name_plural = "Topics"

    def __str__(self):
        return f"{self.title} - {self.forum.name}"

    def get_absolute_url(self):
        return reverse("topic_detail", kwargs={"topic_id": self.pk})

    @property
    def reply_count(self):
        return self.posts.count() - 1  # Exclude the initial post

    @property
    def last_activity(self):
        last_post = self.posts.order_by("-created_at").first()
        if last_post:
            return last_post.created_at
        return self.created_at

    def increment_views(self):
        self.view_count += 1
        self.save(update_fields=["view_count"])


class Post(models.Model):
    """Individual post/reply in a topic"""

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    content = models.TextField()
    is_case_study = models.BooleanField(
        default=False, help_text="Mark as a case study for easy filtering"
    )
    is_preparation_strategy = models.BooleanField(
        default=False, help_text="Mark as a preparation strategy tip"
    )
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Post by {self.author.username} in {self.topic.title}"

    @property
    def score(self):
        return self.upvotes - self.downvotes

    @property
    def is_initial_post(self):
        return self.topic.posts.first() == self

    def mark_as_edited(self):
        self.edited_at = timezone.now()
        self.save(update_fields=["edited_at"])


class Comment(models.Model):
    """Comments on posts (nested replies)"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    content = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.username} on post {self.post.id}"


class MentorAssignment(models.Model):
    """Assign mentors to forums for expert guidance"""

    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="mentors")
    mentor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="mentored_forums"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["forum", "mentor"]
        verbose_name_plural = "Mentor Assignments"

    def __str__(self):
        return f"{self.mentor.username} - {self.forum.name}"


class PostVote(models.Model):
    """Track user votes on posts to prevent duplicate voting"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_votes")
    vote_type = models.CharField(
        max_length=10, choices=[("up", "Upvote"), ("down", "Downvote")]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["post", "user"]

    def __str__(self):
        return f"{self.user.username} {self.vote_type} on post {self.post.id}"
