from django.shortcuts import render

# Create your views here.

def forum_view(request):
    """Forum discussion page placeholder"""
    return render(request, 'forums/forum.html')
