from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import User
import os

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    user_type = forms.ChoiceField(choices=User.USER_TYPES, required=True)
    resume = forms.FileField(
        required=False,
        help_text='Upload your resume (PDF only, max 5MB)',
        widget=forms.FileInput(attrs={'accept': '.pdf'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'user_type', 'resume', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to form fields
        for field_name, field in self.fields.items():
            if field_name in ['user_type']:
                field.widget.attrs.update({'class': 'form-select'})
            elif field_name in ['resume']:
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
        
        # Add placeholders
        self.fields['username'].widget.attrs.update({'placeholder': 'Choose a username'})
        self.fields['email'].widget.attrs.update({'placeholder': 'your.email@example.com'})
        self.fields['first_name'].widget.attrs.update({'placeholder': 'First Name'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Last Name'})
        self.fields['password1'].widget.attrs.update({'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Confirm Password'})

    def clean_resume(self):
        resume = self.cleaned_data.get('resume')
        if resume:
            # Check file size (5MB limit)
            if resume.size > 5 * 1024 * 1024:
                raise ValidationError('File size must be under 5MB.')
            
            # Check file extension
            ext = os.path.splitext(resume.name)[1].lower()
            if ext != '.pdf':
                raise ValidationError('Only PDF files are allowed.')
            
            # Check MIME type
            content_type = getattr(resume, 'content_type', '')
            if content_type and content_type != 'application/pdf':
                raise ValidationError('Invalid file type; PDF required.')
        
        return resume

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            # Handle resume upload after user is saved
            if self.cleaned_data.get('resume'):
                user.resume = self.cleaned_data['resume']
                user.save()
        return user

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username or Email'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password'
        })

class ResumeUpdateForm(forms.ModelForm):
    """Form for updating user's resume"""
    resume = forms.FileField(
        required=True,
        help_text='Upload your resume (PDF only, max 5MB)',
        widget=forms.FileInput(attrs={'accept': '.pdf', 'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['resume']
    
    def clean_resume(self):
        resume = self.cleaned_data.get('resume')
        if resume:
            # Check file size (5MB limit)
            if resume.size > 5 * 1024 * 1024:
                raise ValidationError('File size must be under 5MB.')
            
            # Check file extension
            ext = os.path.splitext(resume.name)[1].lower()
            if ext != '.pdf':
                raise ValidationError('Only PDF files are allowed.')
            
            # Check MIME type
            content_type = getattr(resume, 'content_type', '')
            if content_type and content_type != 'application/pdf':
                raise ValidationError('Invalid file type; PDF required.')
        
        return resume
