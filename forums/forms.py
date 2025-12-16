from django import forms
from .models import Topic, Post, Comment


class TopicForm(forms.ModelForm):
    """Form for creating/editing topics"""
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 8,
            'class': 'form-control',
            'placeholder': 'Describe your topic or share your initial thoughts...'
        }),
        help_text="This will be your initial post in the topic."
    )
    
    class Meta:
        model = Topic
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter topic title...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = 'Topic Title'
        self.fields['description'].label = 'Initial Post Content'


class PostForm(forms.ModelForm):
    """Form for creating posts/replies"""
    
    class Meta:
        model = Post
        fields = ['content', 'is_case_study', 'is_preparation_strategy']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 8,
                'class': 'form-control',
                'placeholder': 'Write your reply...'
            }),
            'is_case_study': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_preparation_strategy': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = 'Your Reply'
        self.fields['is_case_study'].label = 'Mark as Case Study'
        self.fields['is_preparation_strategy'].label = 'Mark as Preparation Strategy'


class CommentForm(forms.ModelForm):
    """Form for creating comments on posts"""
    
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Write a comment...',
                'maxlength': 1000
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = 'Comment'

